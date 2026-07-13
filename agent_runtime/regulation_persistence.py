"""Encrypted, restart-safe persistence for Regulation sessions and rules.

The event envelope exposes only event type and operational metadata. Every
owner-authored value, including identifiers used by tombstones, is encrypted.
Private check-ins deliberately remain memory-only.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from .emotional_regulation import (
    Action,
    ConfirmationState,
    Emotion,
    EmotionLabel,
    Fact,
    Interpretation,
    Outcome,
    PersonalRegulationRule,
    RuleStrength,
    SafetyCategory,
    SafetyState,
    SessionState,
    TriggerSession,
    Urge,
)
from .encryption import KeyManager
from .event_envelope import Domain, EventEnvelope, Sensitivity
from .stores import RegulationStore


SESSION_SNAPSHOT = "regulation_session_snapshot"
SESSION_DELETED = "regulation_session_deleted"
ALL_SESSIONS_DELETED = "regulation_all_sessions_deleted"
RULE_SNAPSHOT = "regulation_rule_snapshot"


class EncryptedRegulationPersistence:
    """Append encrypted snapshots and deterministically rebuild current state."""

    def __init__(
        self,
        store: RegulationStore,
        keys: KeyManager,
        *,
        owner_id: str,
    ) -> None:
        self._store = store
        self._keys = keys
        self._owner_id = owner_id

    def load(
        self,
    ) -> Tuple[Dict[str, TriggerSession], Dict[str, PersonalRegulationRule]]:
        sessions: Dict[str, TriggerSession] = {}
        rules: Dict[str, PersonalRegulationRule] = {}
        for event in self._store.replay():
            if event.owner_id != self._owner_id:
                continue
            if event.event_type not in {
                SESSION_SNAPSHOT,
                SESSION_DELETED,
                ALL_SESSIONS_DELETED,
                RULE_SNAPSHOT,
            }:
                continue

            payload = self._keys.decrypt_payload(event.payload)
            if event.event_type == SESSION_SNAPSHOT:
                session = _session_from_dict(payload["session"])
                sessions[session.session_id] = session
            elif event.event_type == SESSION_DELETED:
                sessions.pop(str(payload["session_id"]), None)
            elif event.event_type == ALL_SESSIONS_DELETED:
                sessions.clear()
            elif event.event_type == RULE_SNAPSHOT:
                rule = _rule_from_dict(payload["rule"])
                rules[rule.rule_id] = rule
        return sessions, rules

    def save_session(self, session: TriggerSession) -> None:
        if session.is_private:
            return
        self._append(SESSION_SNAPSHOT, {"session": _session_to_dict(session)})

    def save_rule(self, rule: PersonalRegulationRule) -> None:
        self._append(RULE_SNAPSHOT, {"rule": _rule_to_dict(rule)})

    def delete_session(self, session_id: str) -> None:
        self._append(SESSION_DELETED, {"session_id": session_id})

    def delete_all_sessions(self) -> None:
        self._append(ALL_SESSIONS_DELETED, {"scope": "all"})

    def _append(self, event_type: str, payload: Dict[str, Any]) -> None:
        self._store.append(
            EventEnvelope.create(
                owner_id=self._owner_id,
                domain=Domain.REGULATION,
                event_type=event_type,
                schema_version=1,
                sensitivity=Sensitivity.RESTRICTED,
                provenance={"source": "regulation_api"},
                payload=self._keys.encrypt_payload(payload),
            )
        )


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
