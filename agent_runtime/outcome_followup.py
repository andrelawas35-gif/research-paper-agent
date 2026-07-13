"""Outcome follow-up — S3 from implementation-plan-regulation-pkm.md.

ADR 0087: Regulation Sessions Support Permissioned Pending Outcomes.
ADR 0080: Tier Proactive Companion Reminders by Permission.

Permissioned Pending Outcomes with user-configurable follow-up timing,
expiry, and acted/not-acted distinction. No unsolicited intimate
reminders; follow-up can be disabled and deleted.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import USER_MODEL_DIR, ensure_dirs, now_iso


# ── Domain types ─────────────────────────────────────────────────────


class OutcomeStatus(str, Enum):
    """Status of a pending outcome."""
    PENDING = "pending"       # awaiting follow-up
    FOLLOWED_UP = "followed_up"  # follow-up has been sent
    ACTED = "acted"           # user confirmed action was taken
    NOT_ACTED = "not_acted"   # user confirmed action was NOT taken
    EXPIRED = "expired"       # past expiry without follow-up
    DISABLED = "disabled"     # user turned off follow-up for this outcome
    DELETED = "deleted"       # user deleted the outcome


class FollowUpPermission(str, Enum):
    """Permission level for follow-up on a pending outcome.

    ADR 0080: Contextual Reminders by default, Event-Driven Check-Ins
    require permission, Scheduled Reflections opt-in only.
    """
    NONE = "none"             # no follow-up allowed
    CONTEXTUAL = "contextual"  # may follow up when contextually relevant
    SCHEDULED = "scheduled"   # user set a specific follow-up time
    EVENT_DRIVEN = "event_driven"  # follow-up on next relevant event


@dataclass
class PendingOutcome:
    """A Regulation Session outcome awaiting follow-up.

    ADR 0087: A Regulation Session may close with a Pending Outcome
    when the result of its Deliberate Action is not yet known.
    Follow-up occurs only with explicit permission.

    ADR 0087: Outcome Review distinguishes action completion, later
    facts, uncertainty, feared outcomes, value/boundary alignment,
    situation impact, and tactic friction. Calmness alone is not
    treated as success.
    """

    outcome_id: str
    session_id: str  # the Regulation session that created this
    description: str  # what action was decided
    created_at: str
    permission: FollowUpPermission = FollowUpPermission.NONE
    follow_up_at: Optional[str] = None  # ISO timestamp for scheduled follow-up
    expires_at: Optional[str] = None    # ISO timestamp when this expires
    status: OutcomeStatus = OutcomeStatus.PENDING
    # Outcome dimensions (ADR 0087)
    action_completed: Optional[bool] = None
    later_facts: str = ""            # what became known later
    uncertainty: str = ""            # what remains uncertain
    feared_outcome: str = ""         # what was feared (and whether it happened)
    value_alignment: str = ""        # how this aligned with values/boundaries
    situation_impact: str = ""       # impact on the situation
    tactic_friction: str = ""        # friction experienced with the tactic
    # Metadata
    domain_tags: List[str] = field(default_factory=list)
    updated_at: str = ""


# ── Persistence ──────────────────────────────────────────────────────

OUTCOMES_PATH: Path = USER_MODEL_DIR / "pending_outcomes.jsonl"


def _outcome_to_dict(outcome: PendingOutcome) -> Dict[str, Any]:
    """Serialize a PendingOutcome to a dictionary."""
    return {
        "outcome_id": outcome.outcome_id,
        "session_id": outcome.session_id,
        "description": outcome.description,
        "created_at": outcome.created_at,
        "permission": outcome.permission.value,
        "follow_up_at": outcome.follow_up_at,
        "expires_at": outcome.expires_at,
        "status": outcome.status.value,
        "action_completed": outcome.action_completed,
        "later_facts": outcome.later_facts,
        "uncertainty": outcome.uncertainty,
        "feared_outcome": outcome.feared_outcome,
        "value_alignment": outcome.value_alignment,
        "situation_impact": outcome.situation_impact,
        "tactic_friction": outcome.tactic_friction,
        "domain_tags": outcome.domain_tags,
        "updated_at": outcome.updated_at,
    }


def _dict_to_outcome(d: Dict[str, Any]) -> PendingOutcome:
    """Deserialize a dictionary to a PendingOutcome."""
    return PendingOutcome(
        outcome_id=d["outcome_id"],
        session_id=d["session_id"],
        description=d["description"],
        created_at=d["created_at"],
        permission=FollowUpPermission(d.get("permission", "none")),
        follow_up_at=d.get("follow_up_at"),
        expires_at=d.get("expires_at"),
        status=OutcomeStatus(d.get("status", "pending")),
        action_completed=d.get("action_completed"),
        later_facts=d.get("later_facts", ""),
        uncertainty=d.get("uncertainty", ""),
        feared_outcome=d.get("feared_outcome", ""),
        value_alignment=d.get("value_alignment", ""),
        situation_impact=d.get("situation_impact", ""),
        tactic_friction=d.get("tactic_friction", ""),
        domain_tags=d.get("domain_tags", []),
        updated_at=d.get("updated_at", ""),
    )


def save_outcome(outcome: PendingOutcome) -> None:
    """Save or update a pending outcome. Uses outcome_id as key."""
    ensure_dirs()

    # Load existing, replace if same ID
    outcomes = _load_all_outcomes()
    updated = False
    for i, existing in enumerate(outcomes):
        if existing.outcome_id == outcome.outcome_id:
            outcomes[i] = outcome
            updated = True
            break
    if not updated:
        outcomes.append(outcome)

    # Rewrite file
    with OUTCOMES_PATH.open("w", encoding="utf-8") as handle:
        for o in outcomes:
            handle.write(json.dumps(_outcome_to_dict(o)) + "\n")


def _load_all_outcomes() -> List[PendingOutcome]:
    """Load all outcomes from the persistence file."""
    if not OUTCOMES_PATH.exists():
        return []
    outcomes: List[PendingOutcome] = []
    with OUTCOMES_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                outcomes.append(_dict_to_outcome(json.loads(line)))
            except (json.JSONDecodeError, KeyError):
                continue
    return outcomes


def load_outcomes(
    status: Optional[OutcomeStatus] = None,
    permission: Optional[FollowUpPermission] = None,
) -> List[PendingOutcome]:
    """Load outcomes, optionally filtered by status or permission."""
    outcomes = _load_all_outcomes()
    if status is not None:
        outcomes = [o for o in outcomes if o.status == status]
    if permission is not None:
        outcomes = [o for o in outcomes if o.permission == permission]
    return outcomes


def get_outcome(outcome_id: str) -> Optional[PendingOutcome]:
    """Get a single outcome by ID."""
    for outcome in _load_all_outcomes():
        if outcome.outcome_id == outcome_id:
            return outcome
    return None


def delete_outcome(outcome_id: str) -> bool:
    """Permanently delete a pending outcome."""
    outcomes = _load_all_outcomes()
    new_outcomes = [o for o in outcomes if o.outcome_id != outcome_id]
    if len(new_outcomes) == len(outcomes):
        return False  # not found
    with OUTCOMES_PATH.open("w", encoding="utf-8") as handle:
        for o in new_outcomes:
            handle.write(json.dumps(_outcome_to_dict(o)) + "\n")
    return True


# ── Outcome lifecycle ────────────────────────────────────────────────


def create_pending_outcome(
    session_id: str,
    description: str,
    *,
    permission: FollowUpPermission = FollowUpPermission.NONE,
    follow_up_at: Optional[str] = None,
    expires_at: Optional[str] = None,
    domain_tags: Optional[List[str]] = None,
) -> PendingOutcome:
    """Create a new pending outcome from a Regulation session.

    ADR 0087: Follow-up occurs only with explicit permission.
    ADR 0080: No unsolicited intimate reminders.
    """
    now = now_iso()

    # Validate: scheduled permission requires follow_up_at
    if permission == FollowUpPermission.SCHEDULED and follow_up_at is None:
        raise ValueError("Scheduled follow-up requires follow_up_at timestamp")

    # Default expiry: 7 days if not specified
    if expires_at is None:
        expires_dt = datetime.now(timezone.utc) + timedelta(days=7)
        expires_at = expires_dt.isoformat(timespec="seconds")

    outcome = PendingOutcome(
        outcome_id=str(uuid.uuid4()),
        session_id=session_id,
        description=description,
        created_at=now,
        permission=permission,
        follow_up_at=follow_up_at,
        expires_at=expires_at,
        status=OutcomeStatus.PENDING,
        domain_tags=domain_tags or [],
        updated_at=now,
    )
    save_outcome(outcome)
    return outcome


def record_follow_up(outcome_id: str) -> Optional[PendingOutcome]:
    """Record that a follow-up has been delivered for this outcome.

    ADR 0087: Follow-up only occurs with explicit permission.
    """
    outcome = get_outcome(outcome_id)
    if outcome is None:
        return None

    if outcome.permission == FollowUpPermission.NONE:
        return None  # cannot follow up without permission

    if outcome.status != OutcomeStatus.PENDING:
        return None  # already handled

    outcome.status = OutcomeStatus.FOLLOWED_UP
    outcome.updated_at = now_iso()
    save_outcome(outcome)
    return outcome


def record_acted(
    outcome_id: str,
    *,
    action_completed: Optional[bool] = None,
    later_facts: str = "",
    uncertainty: str = "",
    feared_outcome: str = "",
    value_alignment: str = "",
    situation_impact: str = "",
    tactic_friction: str = "",
) -> Optional[PendingOutcome]:
    """Record that the user has acted (or not) on the outcome.

    ADR 0087: Outcome Review distinguishes action completion, later
    facts, uncertainty, feared outcomes, value/boundary alignment,
    situation impact, and tactic friction.
    """
    outcome = get_outcome(outcome_id)
    if outcome is None:
        return None

    if outcome.status in (OutcomeStatus.EXPIRED, OutcomeStatus.DELETED):
        return None

    outcome.status = OutcomeStatus.ACTED
    outcome.action_completed = action_completed
    outcome.later_facts = later_facts
    outcome.uncertainty = uncertainty
    outcome.feared_outcome = feared_outcome
    outcome.value_alignment = value_alignment
    outcome.situation_impact = situation_impact
    outcome.tactic_friction = tactic_friction
    outcome.updated_at = now_iso()
    save_outcome(outcome)
    return outcome


def record_not_acted(
    outcome_id: str,
    reason: str = "",
) -> Optional[PendingOutcome]:
    """Record that the user explicitly chose not to act."""
    outcome = get_outcome(outcome_id)
    if outcome is None:
        return None

    if outcome.status in (OutcomeStatus.EXPIRED, OutcomeStatus.DELETED):
        return None

    outcome.status = OutcomeStatus.NOT_ACTED
    outcome.later_facts = reason
    outcome.updated_at = now_iso()
    save_outcome(outcome)
    return outcome


def update_permission(
    outcome_id: str,
    permission: FollowUpPermission,
    follow_up_at: Optional[str] = None,
) -> Optional[PendingOutcome]:
    """Update the follow-up permission for an outcome.

    User-configurable: can change from NONE to SCHEDULED, etc.
    Can also disable follow-up entirely.
    """
    outcome = get_outcome(outcome_id)
    if outcome is None:
        return None

    if outcome.status in (OutcomeStatus.EXPIRED, OutcomeStatus.DELETED):
        return None

    outcome.permission = permission
    if follow_up_at is not None:
        outcome.follow_up_at = follow_up_at
    if permission == FollowUpPermission.NONE:
        outcome.follow_up_at = None

    outcome.updated_at = now_iso()
    save_outcome(outcome)
    return outcome


def expire_stale_outcomes(
    *,
    reference_time: Optional[datetime] = None,
) -> int:
    """Expire pending outcomes past their expiry time.

    Returns the count of expired outcomes.
    """
    now = reference_time or datetime.now(timezone.utc)
    now_iso_str = now.isoformat(timespec="seconds")
    outcomes = _load_all_outcomes()
    expired_count = 0

    for outcome in outcomes:
        if outcome.status != OutcomeStatus.PENDING:
            continue
        if outcome.expires_at is None:
            continue
        if outcome.expires_at < now_iso_str:
            outcome.status = OutcomeStatus.EXPIRED
            outcome.updated_at = now_iso_str
            expired_count += 1

    if expired_count > 0:
        with OUTCOMES_PATH.open("w", encoding="utf-8") as handle:
            for o in outcomes:
                handle.write(json.dumps(_outcome_to_dict(o)) + "\n")

    return expired_count


def disable_follow_up(outcome_id: str) -> Optional[PendingOutcome]:
    """Disable follow-up for a specific outcome.

    ADR 0080: Follow-up can be disabled and deleted.
    """
    outcome = get_outcome(outcome_id)
    if outcome is None:
        return None

    outcome.permission = FollowUpPermission.NONE
    outcome.follow_up_at = None
    outcome.status = OutcomeStatus.DISABLED
    outcome.updated_at = now_iso()
    save_outcome(outcome)
    return outcome


def get_due_follow_ups(
    *,
    reference_time: Optional[datetime] = None,
) -> List[PendingOutcome]:
    """Get outcomes that are due for follow-up.

    Returns outcomes where:
    - status is PENDING
    - permission is SCHEDULED or EVENT_DRIVEN
    - follow_up_at is in the past or not set (for event-driven)
    - not expired
    """
    now = reference_time or datetime.now(timezone.utc)
    now_iso_str = now.isoformat(timespec="seconds")

    outcomes = _load_all_outcomes()
    due: List[PendingOutcome] = []

    for outcome in outcomes:
        if outcome.status != OutcomeStatus.PENDING:
            continue
        if outcome.permission not in (
            FollowUpPermission.SCHEDULED,
            FollowUpPermission.EVENT_DRIVEN,
            FollowUpPermission.CONTEXTUAL,
        ):
            continue
        # Check expiry
        if outcome.expires_at and outcome.expires_at < now_iso_str:
            continue  # expired, not due
        # For scheduled: check follow_up_at
        if outcome.permission == FollowUpPermission.SCHEDULED:
            if outcome.follow_up_at and outcome.follow_up_at <= now_iso_str:
                due.append(outcome)
        else:
            # Contextual or event-driven: always eligible
            due.append(outcome)

    return due


def count_by_status() -> Dict[str, int]:
    """Count outcomes by status for summary display."""
    outcomes = _load_all_outcomes()
    counts: Dict[str, int] = {}
    for outcome in outcomes:
        key = outcome.status.value
        counts[key] = counts.get(key, 0) + 1
    return counts
