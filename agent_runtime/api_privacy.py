"""Data & Privacy Center API — U3 from implementation-plan-regulation-pkm.md.

ADR 0093: Regulation Retention Is Tiered and Deletion Is Cryptographic.
ADR 0095: Web App Is Primary and Discord Is Rapid Entry.
ADR 0096: Single-Owner Private Access and Explicit Channel Linking.
ADR 0115: Production Observability Excludes Personal Content by Default.

Provides:
- Inspect: list and view Regulation sessions
- Correct: update personal rules (confirm/retire)
- Export: JSON export of all Regulation data
- Delete: per-session and bulk deletion with verification
- Retention: retention policy info and expiration tracking
- Consent: consent management endpoints
- Access audit: metadata-only access log

The current persistence slice performs verified logical deletion from active
replay. Per-record key destruction remains a daily-use launch gate, so this API
must not describe logical deletion as cryptographic erasure.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from .emotional_regulation import (
    ConfirmationState,
    PersonalRegulationRule,
    TriggerSession,
    SafetyCategory,
    SessionState,
)
from .stores import StoreRegistry

if TYPE_CHECKING:
    from .regulation_persistence import EncryptedRegulationPersistence

# ═══════════════════════════════════════════════════════════════════════
# Shared state (imported from api_regulation at runtime to avoid circular
# imports — both modules share the same in-memory stores)
# ═══════════════════════════════════════════════════════════════════════

# Default retention: 365 days for durable sessions, 24 hours for private
DEFAULT_RETENTION_DAYS = 365
PRIVATE_CHECKIN_RETENTION_HOURS = 24


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _retention_expiry(session: TriggerSession) -> str:
    """Calculate when a session expires based on its retention policy."""
    from datetime import timedelta

    if session.is_private:
        delta = timedelta(hours=PRIVATE_CHECKIN_RETENTION_HOURS)
    else:
        delta = timedelta(days=session.retention_days)

    created = datetime.fromisoformat(session.created_at.replace("Z", "+00:00"))
    return (created + delta).isoformat(timespec="seconds")


# ═══════════════════════════════════════════════════════════════════════
# Router factory
# ═══════════════════════════════════════════════════════════════════════


def create_privacy_router(
    *,
    store_registry: StoreRegistry,
    owner_id: str = "default",
    sessions_dict: Optional[Dict[str, TriggerSession]] = None,
    rules_dict: Optional[Dict[str, PersonalRegulationRule]] = None,
    persistence: Optional["EncryptedRegulationPersistence"] = None,
    auth_dependency: Any = None,
) -> APIRouter:
    """Create the Privacy Center API router.

    Args:
        store_registry: Store registry for audit/event access.
        owner_id: The owner identifier.
        sessions_dict: Shared in-memory sessions dict (same as in api_regulation).
        rules_dict: Shared in-memory rules dict (same as in api_regulation).

    Returns:
        Configured APIRouter with all Privacy endpoints.
    """
    dependencies = [Depends(auth_dependency)] if auth_dependency is not None else []
    router = APIRouter(
        prefix="/api/privacy", tags=["privacy"], dependencies=dependencies
    )
    _sessions = sessions_dict if sessions_dict is not None else {}
    _rules = rules_dict if rules_dict is not None else {}

    # ── Summary ──────────────────────────────────────────────────────

    @router.get("/summary")
    async def privacy_summary(request: Request) -> Dict[str, Any]:
        """Get a summary of Regulation data counts.

        Returns counts only — no content or sensitive data.
        """
        durable = [
            s for s in _sessions.values()
            if not s.is_private and s.state == SessionState.COMPLETED
        ]
        private_sessions = [
            s for s in _sessions.values()
            if s.is_private
        ]
        all_rules = list(_rules.values())

        return {
            "session_count": len(_sessions),
            "durable_sessions": len(durable),
            "private_sessions": len(private_sessions),
            "rule_count": len(all_rules),
            "confirmed_rules": len([
                r for r in all_rules
                if r.confirmation == ConfirmationState.CONFIRMED
            ]),
            "owner_id": owner_id,
        }

    # ── Session listing and inspection ───────────────────────────────

    @router.get("/sessions")
    async def list_sessions(request: Request) -> Dict[str, Any]:
        """List all Regulation sessions (summary only, no content)."""
        all_sessions = sorted(
            _sessions.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "state": s.state.value,
                    "trigger_event": s.trigger_event,
                    "is_private": s.is_private,
                    "created_at": s.created_at,
                    "completed_at": s.completed_at,
                    "safety_active": s.is_safety_active(),
                    "emotion_count": len(s.emotions),
                    "fact_count": len(s.facts),
                    "action_count": len(s.actions),
                    "outcome_count": len(s.outcomes),
                    "expires_at": _retention_expiry(s),
                }
                for s in all_sessions
            ],
        }

    @router.get("/sessions/{session_id}")
    async def inspect_session(
        request: Request, session_id: str
    ) -> Dict[str, Any]:
        """Inspect a single Regulation session with full content.

        Returns the complete session data including facts, interpretations,
        emotions, urges, actions, and outcomes.
        """
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session.session_id,
            "owner_id": session.owner_id,
            "state": session.state.value,
            "is_private": session.is_private,
            "trigger_event": session.trigger_event,
            "facts": [
                {
                    "text": f.text,
                    "certainty": f.certainty,
                    "source": f.source,
                    "captured_at": f.captured_at,
                }
                for f in session.facts
            ],
            "interpretations": [
                {
                    "text": i.text,
                    "plausibility": i.plausibility,
                    "evidence_for": i.evidence_for,
                    "evidence_against": i.evidence_against,
                }
                for i in session.interpretations
            ],
            "emotions": [
                {
                    "label": e.label.value,
                    "intensity": e.intensity,
                    "description": e.description,
                }
                for e in session.emotions
            ],
            "urges": [
                {"text": u.text, "strength": u.strength}
                for u in session.urges
            ],
            "actions": [
                {
                    "text": a.text,
                    "reversible": a.reversible,
                    "waiting_period_minutes": a.waiting_period_minutes,
                }
                for a in session.actions
            ],
            "outcomes": [
                {
                    "text": o.text,
                    "was_helpful": o.was_helpful,
                }
                for o in session.outcomes
            ],
            "safety_state": {
                "category": session.safety_state.category.value,
                "is_active": session.safety_state.is_active,
            },
            "sensitivity": session.sensitivity.value,
            "retention_days": session.retention_days,
            "created_at": session.created_at,
            "completed_at": session.completed_at,
            "expires_at": _retention_expiry(session),
            "version": session.version,
        }

    # ── Deletion ─────────────────────────────────────────────────────

    @router.delete("/sessions/{session_id}")
    async def delete_session(
        request: Request, session_id: str
    ) -> Dict[str, Any]:
        """Delete a single Regulation session.

        Deletion is verified: the session must exist and is removed from active
        replay. Historical encrypted snapshots remain until storage and backup
        retention removes them.
        """
        session = _sessions.pop(session_id, None)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if persistence is not None and not session.is_private:
            persistence.delete_session(session_id)
        return {
            "session_id": session_id,
            "deleted": True,
            "deleted_at": _now_iso(),
        }

    @router.delete("/sessions")
    async def delete_all_sessions(request: Request) -> Dict[str, Any]:
        """Delete all Regulation sessions.

        This is a bulk operation. Private check-ins are also removed from
        memory. Durable historical ciphertext remains subject to storage and
        backup retention.
        """
        count = len(_sessions)
        _sessions.clear()
        if persistence is not None:
            persistence.delete_all_sessions()

        return {
            "deleted_count": count,
            "deleted_at": _now_iso(),
        }

    # ── Export ───────────────────────────────────────────────────────

    @router.post("/export")
    async def export_data(request: Request) -> Dict[str, Any]:
        """Export all Regulation data as JSON.

        The export includes:
        - All durable sessions (not private check-ins by default)
        - All personal regulation rules
        - Metadata (export ID, timestamp, scope)

        Sensitive content is included in the export since the Owner
        is explicitly requesting it. The export is downloaded client-side
        and not stored on the server.
        """
        body = await request.json() if await request.body() else {}
        scope = body.get("scope", "all")

        export_sessions = []
        for s in _sessions.values():
            if s.is_private:
                continue
            export_sessions.append({
                "session_id": s.session_id,
                "state": s.state.value,
                "is_private": s.is_private,
                "trigger_event": s.trigger_event,
                "facts": [
                    {"text": f.text, "certainty": f.certainty, "source": f.source}
                    for f in s.facts
                ],
                "interpretations": [
                    {"text": i.text, "plausibility": i.plausibility}
                    for i in s.interpretations
                ],
                "emotions": [
                    {"label": e.label.value, "intensity": e.intensity}
                    for e in s.emotions
                ],
                "urges": [
                    {"text": u.text, "strength": u.strength}
                    for u in s.urges
                ],
                "actions": [
                    {"text": a.text, "reversible": a.reversible}
                    for a in s.actions
                ],
                "outcomes": [
                    {"text": o.text, "was_helpful": o.was_helpful}
                    for o in s.outcomes
                ],
                "safety_category": s.safety_state.category.value,
                "created_at": s.created_at,
                "completed_at": s.completed_at,
            })

        export_rules = [
            {
                "rule_id": r.rule_id,
                "text": r.text,
                "strength": r.strength.value,
                "confirmation": r.confirmation.value,
                "exceptions": r.exceptions,
                "created_at": r.created_at,
            }
            for r in _rules.values()
        ]

        export_id = str(uuid.uuid4())
        return {
            "export_id": export_id,
            "scope": scope,
            "generated_at": _now_iso(),
            "owner_id": owner_id,
            "session_count": len(export_sessions),
            "rule_count": len(export_rules),
            "sessions": export_sessions,
            "rules": export_rules,
        }

    # ── Audit log ────────────────────────────────────────────────────

    @router.get("/audit")
    async def audit_log(request: Request) -> Dict[str, Any]:
        """Get the access audit log (metadata only).

        Reuses the audit store from the main API if available.
        """
        entries: List[Dict[str, Any]] = []
        try:
            events = store_registry.operational.replay()
            for e in events:
                if e.payload.get("endpoint", "").startswith("/api/regulation"):
                    entries.append({
                        "timestamp": e.timestamp,
                        "endpoint": e.payload.get("endpoint"),
                        "method": e.payload.get("method"),
                        "status_code": e.payload.get("status_code"),
                        "correlation_id": e.correlation_id,
                    })
        except Exception:
            pass

        return {
            "count": len(entries),
            "entries": entries[-50:],  # Last 50 regulation-related entries
        }

    # ── Retention ────────────────────────────────────────────────────

    @router.get("/retention")
    async def retention_info(request: Request) -> Dict[str, Any]:
        """Get retention policy and session expiry information."""
        now = datetime.now(timezone.utc)
        expiring = []

        for s in _sessions.values():
            expiry_str = _retention_expiry(s)
            try:
                expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                if expiry < now:
                    continue  # already expired
            except (ValueError, TypeError):
                continue
            expiring.append({
                "session_id": s.session_id,
                "expires_at": expiry_str,
                "is_private": s.is_private,
            })

        # Sort by expiry soonest first
        expiring.sort(key=lambda x: x["expires_at"])

        return {
            "default_retention_days": DEFAULT_RETENTION_DAYS,
            "private_checkin_retention_hours": PRIVATE_CHECKIN_RETENTION_HOURS,
            "sessions": expiring[:20],
        }

    # ── Consent ──────────────────────────────────────────────────────

    @router.put("/consent")
    async def update_consent(request: Request) -> Dict[str, Any]:
        """Update a consent setting.

        Request body:
            consent_type: str — e.g., "model_assisted_regulation",
                "pattern_extraction", "historical_backfill"
            granted: bool

        In production, this would persist to the operational store.
        Currently returns the updated consent state.
        """
        body = await request.json()
        consent_type = body.get("consent_type", "").strip()
        if not consent_type:
            raise HTTPException(status_code=400, detail="consent_type is required")

        granted = body.get("granted", False)
        if not isinstance(granted, bool):
            raise HTTPException(status_code=400, detail="granted must be a boolean")

        # In production: persist consent to operational store
        return {
            "consent_type": consent_type,
            "granted": granted,
            "updated_at": _now_iso(),
        }

    return router
