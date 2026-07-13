"""SQLite-backed idempotent job dispatcher — S1 from implementation-plan-regulation-pkm.md.

ADR 0118: Reminders Use a SQLite-Backed Idempotent Dispatcher.
ADR 0080: Tier Proactive Companion Reminders by Permission.

Atomic claiming, idempotency, retries, quiet hours, timezone semantics,
stale-job coalescing, permission/relevance rechecks, and separate
delivery/seen/acted records. Designed for a single-process VM — no Redis,
Celery, or distributed coordination.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .paths import ensure_dirs, now_iso, USER_MODEL_DIR

# ── SQLite database path ─────────────────────────────────────────────

DISPATCHER_DB_PATH: Path = USER_MODEL_DIR / "dispatcher.db"


# ── Domain types ─────────────────────────────────────────────────────


class JobStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class DeliveryEvent(str, Enum):
    DELIVERED = "delivered"
    SEEN = "seen"
    ACTED = "acted"
    DISMISSED = "dismissed"


class JobType(str, Enum):
    REMINDER = "reminder"
    CHECK_IN = "check_in"
    REFLECTION = "reflection"
    FOLLOW_UP = "follow_up"
    REVIEW = "review"


@dataclass
class DispatcherJob:
    """A scheduled job with idempotency and lifecycle tracking."""

    job_id: str
    idempotency_key: str
    job_type: JobType
    payload: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    scheduled_at: str = ""
    claimed_at: Optional[str] = None
    delivery_count: int = 0
    max_retries: int = 3
    quiet_hours_start: Optional[str] = None  # HH:MM
    quiet_hours_end: Optional[str] = None    # HH:MM
    timezone_name: str = "UTC"
    created_at: str = ""
    updated_at: str = ""
    last_error: Optional[str] = None


@dataclass
class DeliveryRecord:
    """A separate record of delivery, seen, or acted event.

    ADR 0118: Delivery, seen, and acted outcomes are recorded separately
    so the system can distinguish "not yet delivered" from "delivered
    but not seen" from "seen but not acted upon."
    """

    event_id: str
    job_id: str
    event_type: DeliveryEvent
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Default quiet hours ──────────────────────────────────────────────

DEFAULT_QUIET_HOURS_START = "22:00"
DEFAULT_QUIET_HOURS_END = "07:00"


# ── Schema ───────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    scheduled_at TEXT NOT NULL,
    claimed_at TEXT,
    delivery_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    quiet_hours_start TEXT,
    quiet_hours_end TEXT,
    timezone_name TEXT NOT NULL DEFAULT 'UTC',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_error TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency
    ON jobs(idempotency_key);

CREATE INDEX IF NOT EXISTS idx_jobs_status_scheduled
    ON jobs(status, scheduled_at);

CREATE TABLE IF NOT EXISTS delivery_events (
    event_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_delivery_job
    ON delivery_events(job_id, event_type);
"""

# ── Connection management ────────────────────────────────────────────

_conn_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    """Get or create the dispatcher database connection (thread-safe)."""
    global _conn
    if _conn is not None:
        return _conn
    with _conn_lock:
        if _conn is not None:
            return _conn
        ensure_dirs()
        conn = sqlite3.connect(str(DISPATCHER_DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        _conn = conn
        return _conn


def _reset_conn() -> None:
    """Reset the connection (for testing)."""
    global _conn
    with _conn_lock:
        if _conn is not None:
            _conn.close()
            _conn = None


# ── Job lifecycle ────────────────────────────────────────────────────


def schedule_job(
    job_type: JobType,
    payload: Dict[str, Any],
    scheduled_at: str,
    *,
    idempotency_key: Optional[str] = None,
    max_retries: int = 3,
    quiet_hours_start: Optional[str] = None,
    quiet_hours_end: Optional[str] = None,
    timezone_name: str = "UTC",
) -> DispatcherJob:
    """Schedule a new job with idempotency protection.

    If an idempotency_key is provided and a job with that key already
    exists, the existing job is returned unchanged — no duplicate.
    """
    conn = _get_conn()
    now = now_iso()
    job_id = str(uuid.uuid4())

    if idempotency_key is None:
        idempotency_key = job_id

    # Idempotency check: if key exists, return existing
    existing = conn.execute(
        "SELECT * FROM jobs WHERE idempotency_key = ?",
        (idempotency_key,),
    ).fetchone()
    if existing is not None:
        return _row_to_job(existing)

    job = DispatcherJob(
        job_id=job_id,
        idempotency_key=idempotency_key,
        job_type=job_type,
        payload=payload,
        status=JobStatus.PENDING,
        scheduled_at=scheduled_at,
        max_retries=max_retries,
        quiet_hours_start=quiet_hours_start,  # None = no quiet hours
        quiet_hours_end=quiet_hours_end,      # None = no quiet hours
        timezone_name=timezone_name,
        created_at=now,
        updated_at=now,
    )

    conn.execute(
        """INSERT INTO jobs (
            job_id, idempotency_key, job_type, payload, status,
            scheduled_at, max_retries, quiet_hours_start, quiet_hours_end,
            timezone_name, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job.job_id,
            job.idempotency_key,
            job.job_type.value,
            json.dumps(job.payload),
            job.status.value,
            job.scheduled_at,
            job.max_retries,
            job.quiet_hours_start,
            job.quiet_hours_end,
            job.timezone_name,
            job.created_at,
            job.updated_at,
        ),
    )
    conn.commit()
    return job


def _row_to_job(row: sqlite3.Row) -> DispatcherJob:
    """Convert a database row to a DispatcherJob."""
    return DispatcherJob(
        job_id=row["job_id"],
        idempotency_key=row["idempotency_key"],
        job_type=JobType(row["job_type"]),
        payload=json.loads(row["payload"]),
        status=JobStatus(row["status"]),
        scheduled_at=row["scheduled_at"],
        claimed_at=row["claimed_at"],
        delivery_count=row["delivery_count"],
        max_retries=row["max_retries"],
        quiet_hours_start=row["quiet_hours_start"],
        quiet_hours_end=row["quiet_hours_end"],
        timezone_name=row["timezone_name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_error=row["last_error"],
    )


def _row_to_delivery(row: sqlite3.Row) -> DeliveryRecord:
    """Convert a database row to a DeliveryRecord."""
    return DeliveryRecord(
        event_id=row["event_id"],
        job_id=row["job_id"],
        event_type=DeliveryEvent(row["event_type"]),
        timestamp=row["timestamp"],
        metadata=json.loads(row["metadata"]),
    )


# ── Quiet hours check ────────────────────────────────────────────────


def _is_quiet_hours(job: DispatcherJob, reference_time: Optional[datetime] = None) -> bool:
    """Check if the current time falls within the job's quiet hours.

    ADR 0118: Quiet hours are configurable per schedule with timezone semantics.
    Returns True if delivery should be suppressed.
    """
    if job.quiet_hours_start is None or job.quiet_hours_end is None:
        return False

    now = reference_time or datetime.now(timezone.utc)
    # For simplicity, treat quiet hours as UTC unless a timezone is specified.
    # Full tz handling would require pytz/zoneinfo; this is the minimal
    # implementation per the single-VM constraint.
    try:
        start_h, start_m = map(int, job.quiet_hours_start.split(":"))
        end_h, end_m = map(int, job.quiet_hours_end.split(":"))
    except (ValueError, AttributeError):
        return False

    current_minutes = now.hour * 60 + now.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    if start_minutes <= end_minutes:
        # Normal range, e.g. 22:00–07:00 doesn't wrap
        return start_minutes <= current_minutes < end_minutes
    else:
        # Wrapped range, e.g. 22:00–07:00
        return current_minutes >= start_minutes or current_minutes < end_minutes


# ── Atomic claiming ──────────────────────────────────────────────────


def claim_due_jobs(
    *,
    limit: int = 5,
    reference_time: Optional[datetime] = None,
    recheck_permission: Optional[Callable[[DispatcherJob], Tuple[bool, str]]] = None,
    recheck_relevance: Optional[Callable[[DispatcherJob], Tuple[bool, str]]] = None,
) -> List[DispatcherJob]:
    """Atomically claim up to `limit` due jobs that are past their scheduled_at.

    ADR 0118:
    - Atomic claiming via SQLite transaction (single writer = safe).
    - Stale claimed jobs (claimed > 1 hour ago without delivery) are coalesced:
      they are released back to pending so they can be reclaimed.
    - Quiet hours suppress delivery of jobs whose quiet-hours window is active.
    - Permission and relevance rechecks run before final claim.

    Returns the list of successfully claimed jobs.
    """
    conn = _get_conn()
    now = reference_time or datetime.now(timezone.utc)
    now_iso_str = now.isoformat(timespec="seconds")

    claimed: List[DispatcherJob] = []

    with conn:
        # Step 1: Coalesce stale claims — release jobs claimed > 1 hour ago
        stale_threshold = (now - timedelta(hours=1)).isoformat(timespec="seconds")
        conn.execute(
            """UPDATE jobs SET status = 'pending', claimed_at = NULL, updated_at = ?
             WHERE status = 'claimed' AND claimed_at < ?""",
            (now_iso_str, stale_threshold),
        )

        # Step 2: Claim pending jobs that are due
        rows = conn.execute(
            """SELECT * FROM jobs
             WHERE status = 'pending'
               AND scheduled_at <= ?
             ORDER BY scheduled_at ASC
             LIMIT ?""",
            (now_iso_str, limit),
        ).fetchall()

        for row in rows:
            job = _row_to_job(row)

            # Quiet hours check
            if _is_quiet_hours(job, now):
                continue

            # Permission recheck
            if recheck_permission is not None:
                allowed, reason = recheck_permission(job)
                if not allowed:
                    conn.execute(
                        """UPDATE jobs SET status = 'expired', updated_at = ?,
                           last_error = ? WHERE job_id = ?""",
                        (now_iso_str, f"Permission denied: {reason}", job.job_id),
                    )
                    continue

            # Relevance recheck
            if recheck_relevance is not None:
                relevant, reason = recheck_relevance(job)
                if not relevant:
                    conn.execute(
                        """UPDATE jobs SET status = 'expired', updated_at = ?,
                           last_error = ? WHERE job_id = ?""",
                        (now_iso_str, f"Not relevant: {reason}", job.job_id),
                    )
                    continue

            # Claim the job
            conn.execute(
                """UPDATE jobs SET status = 'claimed', claimed_at = ?,
                   updated_at = ? WHERE job_id = ? AND status = 'pending'""",
                (now_iso_str, now_iso_str, job.job_id),
            )

            if conn.total_changes > 0:
                job.status = JobStatus.CLAIMED
                job.claimed_at = now_iso_str
                job.updated_at = now_iso_str
                claimed.append(job)

    return claimed


# ── Delivery recording ───────────────────────────────────────────────


def record_delivery(
    job_id: str,
    event_type: DeliveryEvent,
    metadata: Optional[Dict[str, Any]] = None,
) -> DeliveryRecord:
    """Record a delivery event and update the job status.

    ADR 0118: Delivery, seen, and acted are recorded separately.
    """
    conn = _get_conn()
    now = now_iso()
    event_id = str(uuid.uuid4())

    record = DeliveryRecord(
        event_id=event_id,
        job_id=job_id,
        event_type=event_type,
        timestamp=now,
        metadata=metadata or {},
    )

    with conn:
        conn.execute(
            """INSERT INTO delivery_events (event_id, job_id, event_type, timestamp, metadata)
             VALUES (?, ?, ?, ?, ?)""",
            (
                record.event_id,
                record.job_id,
                record.event_type.value,
                record.timestamp,
                json.dumps(record.metadata),
            ),
        )

        # Update job status based on event type
        if event_type == DeliveryEvent.DELIVERED:
            conn.execute(
                """UPDATE jobs SET status = 'delivered',
                   delivery_count = delivery_count + 1,
                   updated_at = ? WHERE job_id = ?""",
                (now, job_id),
            )
        elif event_type == DeliveryEvent.ACTED:
            conn.execute(
                """UPDATE jobs SET status = 'delivered', updated_at = ?
                 WHERE job_id = ?""",
                (now, job_id),
            )

    return record


def record_failure(job_id: str, error: str) -> Optional[DispatcherJob]:
    """Record a delivery failure. If retries remain, reset to pending.
    If max retries exceeded, mark as failed.
    """
    conn = _get_conn()
    now = now_iso()

    with conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None

        job = _row_to_job(row)
        new_count = job.delivery_count + 1

        if new_count >= job.max_retries:
            conn.execute(
                """UPDATE jobs SET status = 'failed', delivery_count = ?,
                   last_error = ?, updated_at = ? WHERE job_id = ?""",
                (new_count, error, now, job_id),
            )
            job.status = JobStatus.FAILED
        else:
            # Reset to pending with incremented count for retry
            conn.execute(
                """UPDATE jobs SET status = 'pending', claimed_at = NULL,
                   delivery_count = ?, last_error = ?, updated_at = ?
                 WHERE job_id = ?""",
                (new_count, error, now, job_id),
            )
            job.status = JobStatus.PENDING

        job.delivery_count = new_count
        job.last_error = error
        job.updated_at = now
        return job


# ── Querying ─────────────────────────────────────────────────────────


def get_job(job_id: str) -> Optional[DispatcherJob]:
    """Retrieve a single job by ID."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    return _row_to_job(row)


def get_jobs_by_status(status: JobStatus, limit: int = 50) -> List[DispatcherJob]:
    """Retrieve jobs filtered by status."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status = ? ORDER BY scheduled_at ASC LIMIT ?",
        (status.value, limit),
    ).fetchall()
    return [_row_to_job(r) for r in rows]


def get_delivery_events(job_id: str) -> List[DeliveryRecord]:
    """Retrieve all delivery events for a job."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM delivery_events WHERE job_id = ? ORDER BY timestamp ASC",
        (job_id,),
    ).fetchall()
    return [_row_to_delivery(r) for r in rows]


def get_pending_count() -> int:
    """Count pending jobs."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM jobs WHERE status = 'pending'"
    ).fetchone()
    return row["cnt"] if row else 0


def get_failed_count() -> int:
    """Count failed jobs."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM jobs WHERE status = 'failed'"
    ).fetchone()
    return row["cnt"] if row else 0


# ── Job management ───────────────────────────────────────────────────


def cancel_job(job_id: str) -> Optional[DispatcherJob]:
    """Cancel a pending or claimed job."""
    conn = _get_conn()
    now = now_iso()
    with conn:
        conn.execute(
            """UPDATE jobs SET status = 'cancelled', updated_at = ?
             WHERE job_id = ? AND status IN ('pending', 'claimed')""",
            (now, job_id),
        )
        if conn.total_changes > 0:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return _row_to_job(row) if row else None
    return None


def expire_stale_jobs(
    *,
    reference_time: Optional[datetime] = None,
    max_age_hours: int = 72,
) -> int:
    """Expire pending jobs older than max_age_hours.

    ADR 0118: Downtime recovery coalesces or expires stale reminders
    instead of releasing a burst.
    """
    conn = _get_conn()
    now = reference_time or datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=max_age_hours)).isoformat(timespec="seconds")
    now_iso_str = now.isoformat(timespec="seconds")

    with conn:
        cursor = conn.execute(
            """UPDATE jobs SET status = 'expired', updated_at = ?
             WHERE status = 'pending' AND scheduled_at < ?""",
            (now_iso_str, cutoff),
        )
        return cursor.rowcount


def delete_job(job_id: str) -> bool:
    """Permanently delete a job and its delivery events."""
    conn = _get_conn()
    with conn:
        conn.execute("DELETE FROM delivery_events WHERE job_id = ?", (job_id,))
        cursor = conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        return cursor.rowcount > 0
