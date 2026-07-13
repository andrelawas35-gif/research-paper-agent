"""Tests for S3: Outcome follow-up."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Override conftest autouse fixture
@pytest.fixture(autouse=True)
def _isolate_paths(monkeypatch) -> None:
    """Redirect outcome paths to temporary file."""
    import agent_runtime.outcome_followup as mod

    fd, tmp = tempfile.mkstemp(suffix=".jsonl")
    Path(tmp).unlink()  # Fresh file

    monkeypatch.setattr(mod, "OUTCOMES_PATH", Path(tmp))
    yield
    try:
        Path(tmp).unlink()
    except FileNotFoundError:
        pass


from agent_runtime.outcome_followup import (
    FollowUpPermission,
    OutcomeStatus,
    PendingOutcome,
    _dict_to_outcome,
    _outcome_to_dict,
    count_by_status,
    create_pending_outcome,
    delete_outcome,
    disable_follow_up,
    expire_stale_outcomes,
    get_due_follow_ups,
    get_outcome,
    load_outcomes,
    record_acted,
    record_follow_up,
    record_not_acted,
    save_outcome,
    update_permission,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _future_iso(days: int = 3) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=days)
    return dt.isoformat(timespec="seconds")


def _past_iso(days: int = 3) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.isoformat(timespec="seconds")


# ── Creation tests ───────────────────────────────────────────────────


class TestCreatePendingOutcome:
    def test_creates_with_defaults(self):
        outcome = create_pending_outcome("session-1", "Try walking for 10 minutes")
        assert outcome.session_id == "session-1"
        assert outcome.description == "Try walking for 10 minutes"
        assert outcome.permission == FollowUpPermission.NONE
        assert outcome.status == OutcomeStatus.PENDING
        assert outcome.expires_at is not None  # default 7-day expiry

    def test_creates_with_scheduled_permission(self):
        follow_up = _future_iso(2)
        outcome = create_pending_outcome(
            "session-1",
            "Review progress",
            permission=FollowUpPermission.SCHEDULED,
            follow_up_at=follow_up,
        )
        assert outcome.permission == FollowUpPermission.SCHEDULED
        assert outcome.follow_up_at == follow_up

    def test_scheduled_requires_follow_up_at(self):
        with pytest.raises(ValueError, match="follow_up_at"):
            create_pending_outcome(
                "session-1",
                "Review progress",
                permission=FollowUpPermission.SCHEDULED,
            )

    def test_creates_with_domain_tags(self):
        outcome = create_pending_outcome(
            "session-1", "Test action",
            domain_tags=["anxiety", "work"],
        )
        assert "anxiety" in outcome.domain_tags
        assert "work" in outcome.domain_tags

    def test_creates_with_custom_expiry(self):
        expiry = _future_iso(14)
        outcome = create_pending_outcome(
            "session-1", "Test",
            expires_at=expiry,
        )
        assert outcome.expires_at == expiry


# ── Permission tests ─────────────────────────────────────────────────


class TestPermissionUpdate:
    def test_update_to_scheduled(self):
        outcome = create_pending_outcome("s1", "Test")
        assert outcome.permission == FollowUpPermission.NONE

        follow_up = _future_iso(3)
        updated = update_permission(
            outcome.outcome_id,
            FollowUpPermission.SCHEDULED,
            follow_up_at=follow_up,
        )
        assert updated is not None
        assert updated.permission == FollowUpPermission.SCHEDULED
        assert updated.follow_up_at == follow_up

    def test_disable_clears_follow_up_at(self):
        follow_up = _future_iso(2)
        outcome = create_pending_outcome(
            "s1", "Test",
            permission=FollowUpPermission.SCHEDULED,
            follow_up_at=follow_up,
        )
        updated = update_permission(outcome.outcome_id, FollowUpPermission.NONE)
        assert updated is not None
        assert updated.permission == FollowUpPermission.NONE
        assert updated.follow_up_at is None

    def test_update_nonexistent_returns_none(self):
        result = update_permission("nonexistent", FollowUpPermission.SCHEDULED)
        assert result is None

    def test_cannot_update_expired_outcome(self):
        outcome = create_pending_outcome("s1", "Test")
        outcome.status = OutcomeStatus.EXPIRED
        save_outcome(outcome)
        result = update_permission(outcome.outcome_id, FollowUpPermission.SCHEDULED)
        assert result is None


# ── Follow-up recording tests ────────────────────────────────────────


class TestRecordFollowUp:
    def test_records_follow_up(self):
        outcome = create_pending_outcome(
            "s1", "Test",
            permission=FollowUpPermission.CONTEXTUAL,
        )
        updated = record_follow_up(outcome.outcome_id)
        assert updated is not None
        assert updated.status == OutcomeStatus.FOLLOWED_UP

    def test_cannot_follow_up_without_permission(self):
        outcome = create_pending_outcome("s1", "Test")  # NONE permission
        result = record_follow_up(outcome.outcome_id)
        assert result is None

    def test_cannot_follow_up_twice(self):
        outcome = create_pending_outcome(
            "s1", "Test",
            permission=FollowUpPermission.CONTEXTUAL,
        )
        record_follow_up(outcome.outcome_id)
        result = record_follow_up(outcome.outcome_id)
        assert result is None  # already FOLLOWED_UP


# ── Acted/Not-acted tests ────────────────────────────────────────────


class TestRecordActed:
    def test_records_acted_with_details(self):
        outcome = create_pending_outcome("s1", "Test action")
        updated = record_acted(
            outcome.outcome_id,
            action_completed=True,
            later_facts="It helped reduce tension",
            uncertainty="Not sure if it was the walk or the time",
            feared_outcome="I worried it wouldn't help",
            value_alignment="Aligned with my health goal",
            situation_impact="Situation improved noticeably",
            tactic_friction="Hard to start, but easy once moving",
        )
        assert updated is not None
        assert updated.status == OutcomeStatus.ACTED
        assert updated.action_completed is True
        assert updated.later_facts == "It helped reduce tension"
        assert updated.uncertainty == "Not sure if it was the walk or the time"
        assert updated.feared_outcome == "I worried it wouldn't help"
        assert updated.value_alignment == "Aligned with my health goal"
        assert updated.situation_impact == "Situation improved noticeably"
        assert updated.tactic_friction == "Hard to start, but easy once moving"

    def test_records_acted_without_details(self):
        outcome = create_pending_outcome("s1", "Test")
        updated = record_acted(outcome.outcome_id)
        assert updated is not None
        assert updated.status == OutcomeStatus.ACTED

    def test_cannot_act_on_expired(self):
        outcome = create_pending_outcome("s1", "Test")
        outcome.status = OutcomeStatus.EXPIRED
        save_outcome(outcome)
        result = record_acted(outcome.outcome_id)
        assert result is None


class TestRecordNotActed:
    def test_records_not_acted(self):
        outcome = create_pending_outcome("s1", "Test")
        updated = record_not_acted(outcome.outcome_id, reason="Didn't feel ready")
        assert updated is not None
        assert updated.status == OutcomeStatus.NOT_ACTED
        assert updated.later_facts == "Didn't feel ready"

    def test_cannot_mark_not_acted_on_expired(self):
        outcome = create_pending_outcome("s1", "Test")
        outcome.status = OutcomeStatus.EXPIRED
        save_outcome(outcome)
        result = record_not_acted(outcome.outcome_id)
        assert result is None


# ── Expiry tests ─────────────────────────────────────────────────────


class TestExpireStaleOutcomes:
    def test_expires_past_expiry(self):
        past_expiry = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(timespec="seconds")
        outcome = create_pending_outcome("s1", "Test", expires_at=past_expiry)
        expired = expire_stale_outcomes()
        assert expired >= 1

        updated = get_outcome(outcome.outcome_id)
        assert updated is not None
        assert updated.status == OutcomeStatus.EXPIRED

    def test_does_not_expire_future_expiry(self):
        outcome = create_pending_outcome("s1", "Test")  # default 7-day expiry
        expired = expire_stale_outcomes()
        assert expired == 0

        updated = get_outcome(outcome.outcome_id)
        assert updated is not None
        assert updated.status == OutcomeStatus.PENDING

    def test_does_not_expire_non_pending(self):
        outcome = create_pending_outcome("s1", "Test")
        outcome.status = OutcomeStatus.ACTED
        save_outcome(outcome)
        expired = expire_stale_outcomes()
        assert expired == 0


# ── Disable/delete tests ─────────────────────────────────────────────


class TestDisableFollowUp:
    def test_disables_follow_up(self):
        outcome = create_pending_outcome(
            "s1", "Test",
            permission=FollowUpPermission.SCHEDULED,
            follow_up_at=_future_iso(2),
        )
        disabled = disable_follow_up(outcome.outcome_id)
        assert disabled is not None
        assert disabled.status == OutcomeStatus.DISABLED
        assert disabled.permission == FollowUpPermission.NONE
        assert disabled.follow_up_at is None

    def test_disable_nonexistent_returns_none(self):
        assert disable_follow_up("nonexistent") is None


class TestDeleteOutcome:
    def test_deletes_outcome(self):
        outcome = create_pending_outcome("s1", "Test")
        assert delete_outcome(outcome.outcome_id) is True
        assert get_outcome(outcome.outcome_id) is None

    def test_delete_nonexistent_returns_false(self):
        assert delete_outcome("nonexistent") is False


# ── Query tests ──────────────────────────────────────────────────────


class TestLoadOutcomes:
    def test_load_all(self):
        create_pending_outcome("s1", "Outcome 1")
        create_pending_outcome("s2", "Outcome 2")
        all_outcomes = load_outcomes()
        assert len(all_outcomes) == 2

    def test_load_by_status(self):
        create_pending_outcome("s1", "P1")
        o2 = create_pending_outcome("s2", "P2")
        record_acted(o2.outcome_id)

        pending = load_outcomes(status=OutcomeStatus.PENDING)
        acted = load_outcomes(status=OutcomeStatus.ACTED)
        assert len(pending) == 1
        assert len(acted) == 1

    def test_load_by_permission(self):
        create_pending_outcome("s1", "P1")  # NONE
        create_pending_outcome(
            "s2", "P2",
            permission=FollowUpPermission.CONTEXTUAL,
        )
        create_pending_outcome(
            "s3", "P3",
            permission=FollowUpPermission.SCHEDULED,
            follow_up_at=_future_iso(5),
        )
        none_outcomes = load_outcomes(permission=FollowUpPermission.NONE)
        contextual = load_outcomes(permission=FollowUpPermission.CONTEXTUAL)
        assert len(none_outcomes) == 1
        assert len(contextual) == 1


class TestGetDueFollowUps:
    def test_returns_scheduled_due(self):
        past_follow_up = _past_iso(1)  # 1 day ago
        create_pending_outcome(
            "s1", "Test",
            permission=FollowUpPermission.SCHEDULED,
            follow_up_at=past_follow_up,
        )
        due = get_due_follow_ups()
        assert len(due) == 1

    def test_does_not_return_future_scheduled(self):
        future_follow_up = _future_iso(5)
        create_pending_outcome(
            "s1", "Test",
            permission=FollowUpPermission.SCHEDULED,
            follow_up_at=future_follow_up,
        )
        due = get_due_follow_ups()
        assert len(due) == 0

    def test_returns_contextual(self):
        create_pending_outcome(
            "s1", "Test",
            permission=FollowUpPermission.CONTEXTUAL,
        )
        due = get_due_follow_ups()
        assert len(due) == 1

    def test_does_not_return_none_permission(self):
        create_pending_outcome("s1", "Test")  # NONE
        due = get_due_follow_ups()
        assert len(due) == 0

    def test_does_not_return_expired(self):
        past_expiry = _past_iso(10)
        create_pending_outcome(
            "s1", "Test",
            permission=FollowUpPermission.SCHEDULED,
            follow_up_at=_past_iso(1),
            expires_at=past_expiry,
        )
        # Manually expire
        expire_stale_outcomes()
        due = get_due_follow_ups()
        assert len(due) == 0

    def test_does_not_return_already_followed_up(self):
        outcome = create_pending_outcome(
            "s1", "Test",
            permission=FollowUpPermission.SCHEDULED,
            follow_up_at=_past_iso(1),
        )
        record_follow_up(outcome.outcome_id)
        due = get_due_follow_ups()
        assert len(due) == 0


# ── Count tests ──────────────────────────────────────────────────────


class TestCountByStatus:
    def test_counts_all_statuses(self):
        o1 = create_pending_outcome("s1", "P")
        o2 = create_pending_outcome("s2", "P")
        record_acted(o1.outcome_id)
        record_not_acted(o2.outcome_id)

        counts = count_by_status()
        assert counts.get("acted", 0) == 1
        assert counts.get("not_acted", 0) == 1

    def test_empty_returns_empty_dict(self):
        counts = count_by_status()
        assert counts == {}


# ── Serialization tests ──────────────────────────────────────────────


class TestSerialization:
    def test_round_trip(self):
        outcome = PendingOutcome(
            outcome_id="test-id",
            session_id="session-1",
            description="Test outcome",
            created_at=_now_iso(),
            permission=FollowUpPermission.SCHEDULED,
            follow_up_at=_future_iso(2),
            expires_at=_future_iso(7),
            status=OutcomeStatus.PENDING,
            domain_tags=["anxiety", "health"],
            updated_at=_now_iso(),
        )
        d = _outcome_to_dict(outcome)
        restored = _dict_to_outcome(d)
        assert restored.outcome_id == "test-id"
        assert restored.session_id == "session-1"
        assert restored.description == "Test outcome"
        assert restored.permission == FollowUpPermission.SCHEDULED
        assert restored.domain_tags == ["anxiety", "health"]

    def test_dict_excludes_none_fields_properly(self):
        d = _outcome_to_dict(PendingOutcome(
            outcome_id="test-id",
            session_id="s1",
            description="Test",
            created_at=_now_iso(),
        ))
        assert d["action_completed"] is None
        assert d["later_facts"] == ""


# ── Safety tests ─────────────────────────────────────────────────────


class TestSafetyConstraints:
    def test_no_unsolicited_follow_up(self):
        """ADR 0080: No unsolicited intimate reminders."""
        # Default permission is NONE — no follow-up without explicit opt-in
        outcome = create_pending_outcome("s1", "Test intimate topic")
        due = get_due_follow_ups()
        # Should not appear in due follow-ups (permission is NONE)
        ids = [o.outcome_id for o in due]
        assert outcome.outcome_id not in ids

    def test_follow_up_can_be_disabled(self):
        """ADR 0080: Follow-up can be disabled."""
        outcome = create_pending_outcome(
            "s1", "Test",
            permission=FollowUpPermission.SCHEDULED,
            follow_up_at=_future_iso(2),
        )
        disabled = disable_follow_up(outcome.outcome_id)
        assert disabled is not None
        assert disabled.status == OutcomeStatus.DISABLED
        # Should not appear in due follow-ups
        due = get_due_follow_ups()
        ids = [o.outcome_id for o in due]
        assert outcome.outcome_id not in ids

    def test_follow_up_can_be_deleted(self):
        """ADR 0080: Follow-up can be deleted."""
        outcome = create_pending_outcome("s1", "Test")
        assert delete_outcome(outcome.outcome_id) is True
        assert get_outcome(outcome.outcome_id) is None

    def test_calmness_not_treated_as_success(self):
        """ADR 0087: Calmness alone is not treated as success."""
        outcome = create_pending_outcome("s1", "Test")
        # Record acted but without action_completed
        updated = record_acted(outcome.outcome_id)
        # The outcome dimensions are captured, but calmness isn't an implicit success
        assert updated is not None
        # action_completed is None, not True (not assumed)
        assert updated.action_completed is None
