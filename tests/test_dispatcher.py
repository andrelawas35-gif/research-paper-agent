"""Tests for S1: SQLite-backed idempotent dispatcher."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

# Override conftest autouse fixture — dispatcher is self-contained
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    """No-op: dispatcher tests manage their own database path."""
    import agent_runtime.dispatcher as mod

    old_path = mod.DISPATCHER_DB_PATH
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    mod.DISPATCHER_DB_PATH = Path(tmp)
    mod._reset_conn()
    yield
    mod._reset_conn()
    mod.DISPATCHER_DB_PATH = old_path
    try:
        Path(tmp).unlink()
    except FileNotFoundError:
        pass


from agent_runtime.dispatcher import (
    DeliveryEvent,
    DispatcherJob,
    JobStatus,
    JobType,
    _is_quiet_hours,
    cancel_job,
    claim_due_jobs,
    delete_job,
    expire_stale_jobs,
    get_delivery_events,
    get_failed_count,
    get_job,
    get_jobs_by_status,
    get_pending_count,
    record_delivery,
    record_failure,
    schedule_job,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _future_iso(minutes: int = 5) -> str:
    dt = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return dt.isoformat(timespec="seconds")


def _past_iso(minutes: int = 5) -> str:
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return dt.isoformat(timespec="seconds")


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


# ── Schedule tests ───────────────────────────────────────────────────


class TestScheduleJob:
    def test_schedule_creates_pending_job(self):
        job = schedule_job(
            JobType.REMINDER,
            {"message": "test"},
            _future_iso(10),
        )
        assert job.status == JobStatus.PENDING
        assert job.job_type == JobType.REMINDER
        assert job.payload == {"message": "test"}
        assert job.delivery_count == 0

    def test_idempotency_key_prevents_duplicate(self):
        key = "unique-key-001"
        j1 = schedule_job(
            JobType.CHECK_IN,
            {"msg": "first"},
            _future_iso(10),
            idempotency_key=key,
        )
        j2 = schedule_job(
            JobType.CHECK_IN,
            {"msg": "second"},
            _future_iso(20),
            idempotency_key=key,
        )
        # j2 should return the same job as j1
        assert j2.job_id == j1.job_id
        assert j2.payload == {"msg": "first"}

    def test_schedule_without_key_generates_one(self):
        job = schedule_job(JobType.REVIEW, {}, _future_iso(10))
        assert job.idempotency_key is not None
        assert len(job.idempotency_key) > 0

    def test_schedule_defaults_no_quiet_hours(self):
        job = schedule_job(JobType.REMINDER, {}, _future_iso(10))
        assert job.quiet_hours_start is None
        assert job.quiet_hours_end is None

    def test_schedule_custom_quiet_hours(self):
        job = schedule_job(
            JobType.REMINDER, {},
            _future_iso(10),
            quiet_hours_start="23:00",
            quiet_hours_end="06:00",
        )
        assert job.quiet_hours_start == "23:00"
        assert job.quiet_hours_end == "06:00"

    def test_schedule_default_max_retries(self):
        job = schedule_job(JobType.REMINDER, {}, _future_iso(10))
        assert job.max_retries == 3

    def test_schedule_custom_max_retries(self):
        job = schedule_job(
            JobType.REMINDER, {}, _future_iso(10), max_retries=5
        )
        assert job.max_retries == 5


# ── Quiet hours tests ────────────────────────────────────────────────


class TestQuietHours:
    def test_not_quiet_during_day(self):
        job = DispatcherJob(
            job_id="j1",
            idempotency_key="k1",
            job_type=JobType.REMINDER,
            payload={},
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            scheduled_at=_future_iso(),
            created_at=_future_iso(),
            updated_at=_future_iso(),
        )
        # 12:00 UTC is not in quiet hours
        ref = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
        assert not _is_quiet_hours(job, ref)

    def test_quiet_during_night(self):
        job = DispatcherJob(
            job_id="j1",
            idempotency_key="k1",
            job_type=JobType.REMINDER,
            payload={},
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            scheduled_at=_future_iso(),
            created_at=_future_iso(),
            updated_at=_future_iso(),
        )
        # 23:00 UTC is in quiet hours (wrapped range)
        ref = datetime(2026, 7, 12, 23, 0, 0, tzinfo=timezone.utc)
        assert _is_quiet_hours(job, ref)

    def test_quiet_early_morning(self):
        job = DispatcherJob(
            job_id="j1",
            idempotency_key="k1",
            job_type=JobType.REMINDER,
            payload={},
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            scheduled_at=_future_iso(),
            created_at=_future_iso(),
            updated_at=_future_iso(),
        )
        # 03:00 UTC is in quiet hours
        ref = datetime(2026, 7, 12, 3, 0, 0, tzinfo=timezone.utc)
        assert _is_quiet_hours(job, ref)

    def test_not_quiet_when_no_hours_set(self):
        job = DispatcherJob(
            job_id="j1",
            idempotency_key="k1",
            job_type=JobType.REMINDER,
            payload={},
            quiet_hours_start=None,
            quiet_hours_end=None,
            scheduled_at=_future_iso(),
            created_at=_future_iso(),
            updated_at=_future_iso(),
        )
        ref = datetime(2026, 7, 12, 23, 0, 0, tzinfo=timezone.utc)
        assert not _is_quiet_hours(job, ref)

    def test_non_wrapped_range(self):
        job = DispatcherJob(
            job_id="j1",
            idempotency_key="k1",
            job_type=JobType.REMINDER,
            payload={},
            quiet_hours_start="09:00",
            quiet_hours_end="17:00",
            scheduled_at=_future_iso(),
            created_at=_future_iso(),
            updated_at=_future_iso(),
        )
        # 12:00 is in quiet hours (09-17 non-wrapped)
        ref = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
        assert _is_quiet_hours(job, ref)
        # 18:00 is not
        ref2 = datetime(2026, 7, 12, 18, 0, 0, tzinfo=timezone.utc)
        assert not _is_quiet_hours(job, ref2)

    def test_invalid_hours_returns_false(self):
        job = DispatcherJob(
            job_id="j1",
            idempotency_key="k1",
            job_type=JobType.REMINDER,
            payload={},
            quiet_hours_start="not-valid",
            quiet_hours_end="07:00",
            scheduled_at=_future_iso(),
            created_at=_future_iso(),
            updated_at=_future_iso(),
        )
        ref = datetime(2026, 7, 12, 23, 0, 0, tzinfo=timezone.utc)
        assert not _is_quiet_hours(job, ref)


# ── Atomic claiming tests ────────────────────────────────────────────


class TestClaimDueJobs:
    def test_claims_due_jobs(self):
        schedule_job(JobType.REMINDER, {"n": 1}, _past_iso(5))
        schedule_job(JobType.REMINDER, {"n": 2}, _past_iso(5))

        claimed = claim_due_jobs(limit=5, reference_time=_now_dt())
        assert len(claimed) == 2
        for j in claimed:
            assert j.status == JobStatus.CLAIMED
            assert j.claimed_at is not None

    def test_does_not_claim_future_jobs(self):
        schedule_job(JobType.REMINDER, {"n": 1}, _future_iso(10))

        claimed = claim_due_jobs(limit=5, reference_time=_now_dt())
        assert len(claimed) == 0

    def test_respects_limit(self):
        for i in range(10):
            schedule_job(JobType.REMINDER, {"n": i}, _past_iso(5))

        claimed = claim_due_jobs(limit=3, reference_time=_now_dt())
        assert len(claimed) == 3

    def test_suppresses_during_quiet_hours(self):
        # Schedule a job due now but with quiet hours covering now
        now = _now_dt()
        now_h = now.hour
        start_h = (now_h - 1) % 24
        end_h = (now_h + 1) % 24
        start_str = f"{start_h:02d}:00"
        end_str = f"{end_h:02d}:00"

        schedule_job(
            JobType.REMINDER,
            {"msg": "quiet"},
            _past_iso(5),
            quiet_hours_start=start_str,
            quiet_hours_end=end_str,
        )
        claimed = claim_due_jobs(limit=5, reference_time=now)
        # Should be suppressed
        assert len(claimed) == 0

    def test_permission_recheck_denies(self):
        schedule_job(JobType.REMINDER, {"msg": "bad"}, _past_iso(5))

        def deny_all(job: DispatcherJob) -> Tuple[bool, str]:
            return (False, "test denial")

        claimed = claim_due_jobs(
            limit=5, reference_time=_now_dt(), recheck_permission=deny_all
        )
        assert len(claimed) == 0
        # Job should now be expired
        jobs = get_jobs_by_status(JobStatus.EXPIRED)
        assert len(jobs) == 1

    def test_relevance_recheck_denies(self):
        schedule_job(JobType.REMINDER, {"msg": "irrelevant"}, _past_iso(5))

        def deny_relevance(job: DispatcherJob) -> Tuple[bool, str]:
            return (False, "not relevant")

        claimed = claim_due_jobs(
            limit=5, reference_time=_now_dt(), recheck_relevance=deny_relevance
        )
        assert len(claimed) == 0
        jobs = get_jobs_by_status(JobStatus.EXPIRED)
        assert len(jobs) == 1

    def test_permission_recheck_allows(self):
        schedule_job(JobType.REMINDER, {"msg": "ok"}, _past_iso(5))

        def allow_all(job: DispatcherJob) -> Tuple[bool, str]:
            return (True, "allowed")

        claimed = claim_due_jobs(
            limit=5, reference_time=_now_dt(), recheck_permission=allow_all
        )
        assert len(claimed) == 1

    def test_stale_claims_are_coalesced(self):
        now = _now_dt()
        # Insert a job that was claimed 2 hours ago
        import agent_runtime.dispatcher as mod

        conn = mod._get_conn()
        stale_time = (now - timedelta(hours=2)).isoformat(timespec="seconds")
        conn.execute(
            """INSERT INTO jobs (job_id, idempotency_key, job_type, payload,
               status, scheduled_at, claimed_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "stale-1", "key-stale", "reminder", "{}",
                "claimed", _past_iso(10), stale_time,
                stale_time, stale_time,
            ),
        )
        conn.commit()

        claimed = claim_due_jobs(limit=5, reference_time=now)
        # The stale job should have been released and re-claimed
        assert len(claimed) >= 1

    def test_claim_is_atomic_no_double_claim(self):
        for i in range(5):
            schedule_job(JobType.REMINDER, {"n": i}, _past_iso(5))

        # Claim with limit=5 should get all 5
        claimed = claim_due_jobs(limit=5, reference_time=_now_dt())
        assert len(claimed) == 5

        # Second claim should get nothing (all already claimed)
        claimed2 = claim_due_jobs(limit=5, reference_time=_now_dt())
        assert len(claimed2) == 0


# ── Delivery recording tests ─────────────────────────────────────────


class TestRecordDelivery:
    def test_record_delivered(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _past_iso(5))
        record = record_delivery(job.job_id, DeliveryEvent.DELIVERED)

        assert record.event_type == DeliveryEvent.DELIVERED
        assert record.job_id == job.job_id

        # Job status updated
        updated = get_job(job.job_id)
        assert updated is not None
        assert updated.status == JobStatus.DELIVERED
        assert updated.delivery_count == 1

    def test_record_seen(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _past_iso(5))
        record = record_delivery(job.job_id, DeliveryEvent.SEEN)

        assert record.event_type == DeliveryEvent.SEEN
        events = get_delivery_events(job.job_id)
        assert len(events) == 1
        assert events[0].event_type == DeliveryEvent.SEEN

    def test_record_acted(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _past_iso(5))
        record = record_delivery(job.job_id, DeliveryEvent.ACTED)

        updated = get_job(job.job_id)
        assert updated is not None
        assert updated.status == JobStatus.DELIVERED

    def test_record_with_metadata(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _past_iso(5))
        record = record_delivery(
            job.job_id,
            DeliveryEvent.SEEN,
            metadata={"channel": "discord", "latency_ms": 150},
        )
        assert record.metadata["channel"] == "discord"

    def test_multiple_events_for_same_job(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _past_iso(5))
        record_delivery(job.job_id, DeliveryEvent.DELIVERED)
        record_delivery(job.job_id, DeliveryEvent.SEEN)
        record_delivery(job.job_id, DeliveryEvent.ACTED)

        events = get_delivery_events(job.job_id)
        assert len(events) == 3
        types = [e.event_type for e in events]
        assert DeliveryEvent.DELIVERED in types
        assert DeliveryEvent.SEEN in types
        assert DeliveryEvent.ACTED in types


# ── Failure recording tests ──────────────────────────────────────────


class TestRecordFailure:
    def test_failure_increments_count_and_resets(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _past_iso(5))
        updated = record_failure(job.job_id, "temporary error")
        assert updated is not None
        assert updated.delivery_count == 1
        assert updated.status == JobStatus.PENDING  # reset for retry
        assert updated.last_error == "temporary error"

    def test_failure_exceeds_max_retries(self):
        job = schedule_job(
            JobType.REMINDER, {"msg": "hi"}, _past_iso(5), max_retries=2
        )
        record_failure(job.job_id, "error 1")
        updated = record_failure(job.job_id, "error 2")
        assert updated is not None
        assert updated.delivery_count == 2
        assert updated.status == JobStatus.FAILED

    def test_failure_nonexistent_job(self):
        result = record_failure("nonexistent-id", "error")
        assert result is None


# ── Job management tests ─────────────────────────────────────────────


class TestCancelJob:
    def test_cancel_pending_job(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _future_iso(10))
        cancelled = cancel_job(job.job_id)
        assert cancelled is not None
        assert cancelled.status == JobStatus.CANCELLED

    def test_cancel_claimed_job(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _past_iso(5))
        claimed = claim_due_jobs(limit=1, reference_time=_now_dt())
        assert len(claimed) == 1

        cancelled = cancel_job(job.job_id)
        assert cancelled is not None
        assert cancelled.status == JobStatus.CANCELLED

    def test_cancel_nonexistent_returns_none(self):
        result = cancel_job("nonexistent")
        assert result is None


class TestExpireStaleJobs:
    def test_expires_old_pending_jobs(self):
        # Insert a job scheduled 100 hours ago
        now = _now_dt()
        old_time = (now - timedelta(hours=100)).isoformat(timespec="seconds")
        import agent_runtime.dispatcher as mod

        conn = mod._get_conn()
        conn.execute(
            """INSERT INTO jobs (job_id, idempotency_key, job_type, payload,
               status, scheduled_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("old-1", "key-old", "reminder", "{}",
             "pending", old_time, old_time, old_time),
        )
        conn.commit()

        expired = expire_stale_jobs(reference_time=now, max_age_hours=72)
        assert expired >= 1

        # Check job is expired
        row = conn.execute(
            "SELECT status FROM jobs WHERE job_id = 'old-1'"
        ).fetchone()
        assert row is not None
        assert row["status"] == "expired"

    def test_does_not_expire_recent_jobs(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _past_iso(1))
        expired = expire_stale_jobs(reference_time=_now_dt(), max_age_hours=72)
        assert expired == 0
        j = get_job(job.job_id)
        assert j is not None
        assert j.status == JobStatus.PENDING


class TestDeleteJob:
    def test_delete_job_and_events(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _past_iso(5))
        record_delivery(job.job_id, DeliveryEvent.DELIVERED)

        assert delete_job(job.job_id) is True
        assert get_job(job.job_id) is None
        assert len(get_delivery_events(job.job_id)) == 0

    def test_delete_nonexistent(self):
        assert delete_job("nonexistent") is False


# ── Query tests ──────────────────────────────────────────────────────


class TestQueryJobs:
    def test_get_job(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _future_iso(10))
        retrieved = get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id
        assert retrieved.payload == {"msg": "hi"}

    def test_get_nonexistent_job(self):
        assert get_job("nonexistent") is None

    def test_get_jobs_by_status(self):
        schedule_job(JobType.REMINDER, {"n": 1}, _future_iso(10))
        schedule_job(JobType.REMINDER, {"n": 2}, _future_iso(10))

        pending = get_jobs_by_status(JobStatus.PENDING)
        assert len(pending) == 2
        assert all(j.status == JobStatus.PENDING for j in pending)

    def test_get_pending_count(self):
        assert get_pending_count() == 0
        schedule_job(JobType.REMINDER, {"n": 1}, _future_iso(10))
        schedule_job(JobType.REMINDER, {"n": 2}, _future_iso(10))
        assert get_pending_count() == 2

    def test_get_failed_count(self):
        job = schedule_job(
            JobType.REMINDER, {"msg": "hi"}, _past_iso(5), max_retries=1
        )
        record_failure(job.job_id, "error")
        assert get_failed_count() == 1

    def test_get_delivery_events_empty(self):
        job = schedule_job(JobType.REMINDER, {"msg": "hi"}, _future_iso(10))
        events = get_delivery_events(job.job_id)
        assert len(events) == 0


# ── Integration: restart safety ──────────────────────────────────────


class TestRestartSafety:
    def test_duplicate_delivery_prevented_by_idempotency(self):
        """ADR 0118: restart does not release a reminder burst."""
        key = "restart-test-key"
        schedule_job(JobType.REMINDER, {"msg": "hi"}, _past_iso(5), idempotency_key=key)
        # Simulate restart: schedule again with same key
        schedule_job(JobType.REMINDER, {"msg": "should not duplicate"}, _past_iso(5), idempotency_key=key)

        # Only one job should exist
        pending = get_jobs_by_status(JobStatus.PENDING)
        assert len(pending) == 1

    def test_stale_claims_dont_block_restart(self):
        """ADR 0118: stale claimed jobs are coalesced on restart."""
        now = _now_dt()
        import agent_runtime.dispatcher as mod

        conn = mod._get_conn()
        stale_time = (now - timedelta(hours=3)).isoformat(timespec="seconds")
        for i in range(3):
            conn.execute(
                """INSERT INTO jobs (job_id, idempotency_key, job_type, payload,
                   status, scheduled_at, claimed_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"stale-{i}", f"key-stale-{i}", "reminder", "{}",
                    "claimed", _past_iso(10), stale_time,
                    stale_time, stale_time,
                ),
            )
        conn.commit()

        # Claim due jobs should release stale claims and claim them
        claimed = claim_due_jobs(limit=10, reference_time=now)
        # The stale jobs should be reclaimable
        assert len(claimed) >= 3
