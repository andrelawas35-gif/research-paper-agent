"""Encrypted, restart-safe persistence for Regulation sessions and rules.

The event envelope exposes only event type and operational metadata. Every
owner-authored value, including identifiers used by tombstones, is encrypted.
Private check-ins deliberately remain memory-only.
"""

from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path
from typing import Any, Dict, Tuple
from datetime import datetime, timedelta, timezone

from .emotional_regulation import (
    Action,
    ConfirmationState,
    Emotion,
    EmotionLabel,
    Fact,
    Interpretation,
    Outcome,
    PersonalRegulationRule,
    RegulationRecord,
    RuleStrength,
    SafetyCategory,
    SafetyState,
    SessionState,
    TriggerSession,
    Urge,
    compact_regulation_record,
)
from .encryption import (
    KeyManager,
    KeyNotFoundError,
    decrypt_sensitive_payload,
    encrypt,
)
from .event_envelope import Domain, EventEnvelope, Sensitivity
from .stores import RegulationStore
from .record_keys import FileRecordKeyProvider, RecordKeyProvider


SESSION_SNAPSHOT = "regulation_session_snapshot"
SESSION_RECORD = "regulation_record_snapshot"
SESSION_TERMINAL = "regulation_terminal_snapshot"
SESSION_DELETED = "regulation_session_deleted"
ALL_SESSIONS_DELETED = "regulation_all_sessions_deleted"
RULE_SNAPSHOT = "regulation_rule_snapshot"
KEY_DESTROYED = "regulation_key_destroyed"


class EncryptedRegulationPersistence:
    """Append encrypted snapshots and deterministically rebuild current state."""

    def __init__(
        self,
        store: RegulationStore,
        keys: KeyManager | None,
        *,
        owner_id: str,
        record_keys: RecordKeyProvider | None = None,
        allow_legacy: bool = True,
    ) -> None:
        self._store = store
        self._keys = keys
        self._owner_id = owner_id
        self._record_keys = record_keys or FileRecordKeyProvider(
            Path(os.getenv("REGULATION_RECORD_KEY_DIR", "data/regulation-record-keys"))
        )
        self._allow_legacy = allow_legacy

    def load(
        self,
    ) -> Tuple[Dict[str, TriggerSession], Dict[str, PersonalRegulationRule]]:
        sessions: Dict[str, TriggerSession] = {}
        rules: Dict[str, PersonalRegulationRule] = {}
        events = [
            event for event in self._store.replay()
            if event.owner_id == self._owner_id
        ]
        intentionally_destroyed = {
            digest
            for event in events
            if event.event_type == KEY_DESTROYED
            for digest in event.payload.get("key_digests", [])
        }
        for event in events:
            if event.owner_id != self._owner_id:
                continue
            if event.event_type not in {
                SESSION_SNAPSHOT,
                SESSION_RECORD,
                SESSION_TERMINAL,
                SESSION_DELETED,
                ALL_SESSIONS_DELETED,
                RULE_SNAPSHOT,
            }:
                continue

            try:
                payload = self._decrypt_event_payload(event.payload)
            except KeyNotFoundError:
                key_id = str(event.payload.get("key_id", ""))
                if (
                    _key_digest(key_id) in intentionally_destroyed
                    or self._record_keys.was_destroyed(key_id)
                ):
                    continue
                raise
            if event.event_type == SESSION_SNAPSHOT:
                session = _session_from_dict(payload["session"])
                sessions[session.session_id] = session
            elif event.event_type == SESSION_RECORD:
                session = _session_from_record(payload["record"])
                sessions[session.session_id] = session
            elif event.event_type == SESSION_TERMINAL:
                session = _terminal_session_from_dict(payload["session"])
                sessions[session.session_id] = session
            elif event.event_type == SESSION_DELETED:
                if payload.get("session_id") is not None:
                    sessions.pop(str(payload["session_id"]), None)
            elif event.event_type == ALL_SESSIONS_DELETED:
                sessions.clear()
            elif event.event_type == RULE_SNAPSHOT:
                rule = _rule_from_dict(payload["rule"])
                rules[rule.rule_id] = rule
        return sessions, rules

    def purge_expired_sessions(
        self, sessions: Dict[str, TriggerSession], *, now: datetime | None = None
    ) -> int:
        """Destroy expired session keys and remove their in-memory projections."""
        reference = now or datetime.now(timezone.utc)
        expired = [
            session for session in sessions.values()
            if _session_expired(session, reference)
        ]
        for session in expired:
            key_id = (
                f"record:{session.session_id}"
                if session.state in (
                    SessionState.COMPLETED,
                    SessionState.SAFETY_BRANCH,
                    SessionState.EXPIRED,
                )
                else f"session:{session.session_id}"
            )
            self._record_keys.destroy(key_id)
            self._record_key_destruction([key_id], reason="retention_expired")
            sessions.pop(session.session_id, None)
        return len(expired)

    def save_session(self, session: TriggerSession) -> TriggerSession:
        if session.is_private:
            return session
        if session.state == SessionState.COMPLETED:
            record = compact_regulation_record(session)
            self._append(
                SESSION_RECORD,
                {"record": _record_to_dict(record)},
                record_key_id=f"record:{session.session_id}",
            )
            self._record_keys.destroy(f"session:{session.session_id}")
            self._record_key_destruction(
                [f"session:{session.session_id}"], reason="compacted"
            )
            return _session_from_record(_record_to_dict(record))
        if session.state in (SessionState.SAFETY_BRANCH, SessionState.EXPIRED):
            safe = _terminal_session_projection(session)
            self._append(
                SESSION_TERMINAL,
                {"session": _terminal_session_to_dict(safe)},
                record_key_id=f"record:{session.session_id}",
            )
            self._record_keys.destroy(f"session:{session.session_id}")
            self._record_key_destruction(
                [f"session:{session.session_id}"], reason="terminal_minimization"
            )
            return safe
        self._append(
            SESSION_SNAPSHOT,
            {"session": _session_to_dict(session)},
            record_key_id=f"session:{session.session_id}",
        )
        return session

    def save_rule(self, rule: PersonalRegulationRule) -> None:
        self._append(
            RULE_SNAPSHOT,
            {"rule": _rule_to_dict(rule)},
            record_key_id=f"rule:{rule.rule_id}",
        )

    def delete_session(self, session_id: str) -> None:
        key_ids = [f"session:{session_id}", f"record:{session_id}"]
        for key_id in key_ids:
            self._record_keys.destroy(key_id)
        self._record_key_destruction(key_ids, reason="owner_deleted")
        self._append(
            SESSION_DELETED,
            {"cryptographic_deletion": True},
            plaintext_metadata=True,
        )

    def delete_all_sessions(self) -> None:
        destroyed: list[str] = []
        for event in self._store.replay():
            key_id = str(event.payload.get("key_id", ""))
            if key_id.startswith(("session:", "record:")):
                self._record_keys.destroy(key_id)
                destroyed.append(key_id)
        self._record_key_destruction(destroyed, reason="owner_deleted_all")
        self._append(
            ALL_SESSIONS_DELETED,
            {"scope": "all", "cryptographic_deletion": True},
            plaintext_metadata=True,
        )

    def _record_key_destruction(self, key_ids: list[str], *, reason: str) -> None:
        unique = sorted({_key_digest(key_id) for key_id in key_ids if key_id})
        if not unique:
            return
        self._append(
            KEY_DESTROYED,
            {"key_digests": unique, "reason": reason},
            plaintext_metadata=True,
        )

    def _append(
        self,
        event_type: str,
        payload: Dict[str, Any],
        *,
        record_key_id: str | None = None,
        plaintext_metadata: bool = False,
    ) -> None:
        if plaintext_metadata:
            encrypted_payload = payload
        elif record_key_id is None:
            if self._keys is None:
                raise RuntimeError("Legacy Regulation master key is unavailable")
            encrypted_payload = self._keys.encrypt_payload(payload)
        else:
            record_key = self._record_keys.get_or_create(record_key_id)
            plaintext = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            encrypted_payload = encrypt(
                plaintext,
                key=record_key,
                key_id=record_key_id,
            ).to_dict()
        self._store.append(
            EventEnvelope.create(
                owner_id=self._owner_id,
                domain=Domain.REGULATION,
                event_type=event_type,
                schema_version=1,
                sensitivity=Sensitivity.RESTRICTED,
                provenance={"source": "regulation_api"},
                payload=encrypted_payload,
            )
        )

    def _decrypt_event_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if "ciphertext_b64" not in payload:
            return payload
        key_id = str(payload.get("key_id", ""))
        if key_id.startswith(("session:", "record:", "rule:")):
            key = self._record_keys.get(key_id)
            return decrypt_sensitive_payload(payload, key=key)
        if self._keys is None:
            raise RuntimeError(
                "Legacy Regulation events require a migration master key"
            )
        if not self._allow_legacy:
            raise RuntimeError(
                "Legacy Regulation event detected; complete explicit rekey migration"
            )
        return self._keys.decrypt_payload(payload)


def _session_to_dict(session: TriggerSession) -> Dict[str, Any]:
    return {
        "session_id": session.session_id,
        "owner_id": session.owner_id,
        "state": session.state.value,
        "is_private": session.is_private,
        "trigger_event": session.trigger_event,
        "facts": [vars(item) for item in session.facts],
        "interpretations": [vars(item) for item in session.interpretations],
        "emotions": [
            {**vars(item), "label": item.label.value} for item in session.emotions
        ],
        "urges": [vars(item) for item in session.urges],
        "actions": [vars(item) for item in session.actions],
        "outcomes": [vars(item) for item in session.outcomes],
        "safety_state": {
            **vars(session.safety_state),
            "category": session.safety_state.category.value,
        },
        "sensitivity": session.sensitivity.value,
        "retention_days": session.retention_days,
        "created_at": session.created_at,
        "completed_at": session.completed_at,
        "correlation_id": session.correlation_id,
        "version": session.version,
    }


def _session_from_dict(data: Dict[str, Any]) -> TriggerSession:
    safety = data.get("safety_state", {})
    return TriggerSession(
        session_id=data["session_id"],
        owner_id=data["owner_id"],
        state=SessionState(data["state"]),
        is_private=bool(data.get("is_private", False)),
        trigger_event=data.get("trigger_event"),
        facts=[Fact(**item) for item in data.get("facts", [])],
        interpretations=[
            Interpretation(**item) for item in data.get("interpretations", [])
        ],
        emotions=[
            Emotion(**{**item, "label": EmotionLabel(item["label"])})
            for item in data.get("emotions", [])
        ],
        urges=[Urge(**item) for item in data.get("urges", [])],
        actions=[Action(**item) for item in data.get("actions", [])],
        outcomes=[Outcome(**item) for item in data.get("outcomes", [])],
        safety_state=SafetyState(
            category=SafetyCategory(safety.get("category", "none")),
            is_active=bool(safety.get("is_active", False)),
            resources_provided=bool(safety.get("resources_provided", False)),
            escalation_instructions_given=bool(
                safety.get("escalation_instructions_given", False)
            ),
            captured_at=safety.get("captured_at", data["created_at"]),
        ),
        sensitivity=Sensitivity(data.get("sensitivity", "restricted")),
        retention_days=int(data.get("retention_days", 365)),
        created_at=data["created_at"],
        completed_at=data.get("completed_at"),
        correlation_id=data.get("correlation_id"),
        version=int(data.get("version", 1)),
    )


def _record_to_dict(record: RegulationRecord) -> Dict[str, Any]:
    return {
        "session_id": record.session_id,
        "owner_id": record.owner_id,
        "emotion_labels": [label.value for label in record.emotion_labels],
        "peak_emotion_intensity": record.peak_emotion_intensity,
        "action_count": record.action_count,
        "reversible_action_count": record.reversible_action_count,
        "longest_wait_minutes": record.longest_wait_minutes,
        "helpful_outcome_count": record.helpful_outcome_count,
        "unhelpful_outcome_count": record.unhelpful_outcome_count,
        "safety_category": record.safety_category.value,
        "safety_resources_provided": record.safety_resources_provided,
        "created_at": record.created_at,
        "completed_at": record.completed_at,
        "retention_days": record.retention_days,
        "source_session_version": record.source_session_version,
    }


def _session_from_record(data: Dict[str, Any]) -> TriggerSession:
    peak = int(data.get("peak_emotion_intensity", 0))
    emotions = [
        Emotion(label=EmotionLabel(label), intensity=max(1, peak))
        for label in data.get("emotion_labels", [])
    ]
    safety_category = SafetyCategory(data.get("safety_category", "none"))
    record = _record_from_dict(data)
    return TriggerSession(
        session_id=data["session_id"],
        owner_id=data["owner_id"],
        state=SessionState.COMPLETED,
        trigger_event=None,
        emotions=emotions,
        safety_state=SafetyState(
            category=safety_category,
            is_active=False,
            resources_provided=bool(data.get("safety_resources_provided", False)),
            captured_at=data["completed_at"],
        ),
        retention_days=int(data.get("retention_days", 365)),
        created_at=data["created_at"],
        completed_at=data["completed_at"],
        version=int(data.get("source_session_version", 1)),
        compact_record=record,
    )


def _record_from_dict(data: Dict[str, Any]) -> RegulationRecord:
    return RegulationRecord(
        session_id=data["session_id"],
        owner_id=data["owner_id"],
        emotion_labels=tuple(
            EmotionLabel(label) for label in data.get("emotion_labels", [])
        ),
        peak_emotion_intensity=int(data.get("peak_emotion_intensity", 0)),
        action_count=int(data.get("action_count", 0)),
        reversible_action_count=int(data.get("reversible_action_count", 0)),
        longest_wait_minutes=int(data.get("longest_wait_minutes", 0)),
        helpful_outcome_count=int(data.get("helpful_outcome_count", 0)),
        unhelpful_outcome_count=int(data.get("unhelpful_outcome_count", 0)),
        safety_category=SafetyCategory(data.get("safety_category", "none")),
        safety_resources_provided=bool(data.get("safety_resources_provided", False)),
        created_at=data["created_at"],
        completed_at=data["completed_at"],
        retention_days=int(data.get("retention_days", 365)),
        source_session_version=int(data.get("source_session_version", 1)),
    )


def _terminal_session_projection(session: TriggerSession) -> TriggerSession:
    return TriggerSession(
        session_id=session.session_id,
        owner_id=session.owner_id,
        state=session.state,
        is_private=False,
        trigger_event=None,
        safety_state=session.safety_state,
        sensitivity=session.sensitivity,
        retention_days=session.retention_days,
        created_at=session.created_at,
        completed_at=session.completed_at,
        correlation_id=session.correlation_id,
        version=session.version,
    )


def _terminal_session_to_dict(session: TriggerSession) -> Dict[str, Any]:
    return {
        "session_id": session.session_id,
        "owner_id": session.owner_id,
        "state": session.state.value,
        "safety_category": session.safety_state.category.value,
        "resources_provided": session.safety_state.resources_provided,
        "escalation_instructions_given": (
            session.safety_state.escalation_instructions_given
        ),
        "retention_days": session.retention_days,
        "created_at": session.created_at,
        "completed_at": session.completed_at,
        "version": session.version,
    }


def _terminal_session_from_dict(data: Dict[str, Any]) -> TriggerSession:
    category = SafetyCategory(data.get("safety_category", "none"))
    return TriggerSession(
        session_id=data["session_id"],
        owner_id=data["owner_id"],
        state=SessionState(data["state"]),
        safety_state=SafetyState(
            category=category,
            is_active=(
                category != SafetyCategory.NONE
                and data["state"] == SessionState.SAFETY_BRANCH.value
            ),
            resources_provided=bool(data.get("resources_provided", False)),
            escalation_instructions_given=bool(
                data.get("escalation_instructions_given", False)
            ),
            captured_at=data["completed_at"] or data["created_at"],
        ),
        retention_days=int(data.get("retention_days", 365)),
        created_at=data["created_at"],
        completed_at=data.get("completed_at"),
        version=int(data.get("version", 1)),
    )


def _rule_to_dict(rule: PersonalRegulationRule) -> Dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "text": rule.text,
        "strength": rule.strength.value,
        "confirmation": rule.confirmation.value,
        "exceptions": rule.exceptions,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "review_after_outcomes": rule.review_after_outcomes,
    }


def _rule_from_dict(data: Dict[str, Any]) -> PersonalRegulationRule:
    return PersonalRegulationRule(
        rule_id=data["rule_id"],
        text=data["text"],
        strength=RuleStrength(data["strength"]),
        confirmation=ConfirmationState(data["confirmation"]),
        exceptions=list(data.get("exceptions", [])),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        review_after_outcomes=int(data.get("review_after_outcomes", 5)),
    )


def _key_digest(key_id: str) -> str:
    return hashlib.sha256(key_id.encode("utf-8")).hexdigest()


def _session_expired(session: TriggerSession, now: datetime) -> bool:
    try:
        created = datetime.fromisoformat(session.created_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return created + timedelta(days=session.retention_days) <= now
