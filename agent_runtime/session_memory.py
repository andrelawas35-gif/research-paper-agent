"""Volatile session and interaction state — logs, not durable preferences.

Extracted from agent.py per Python Module Architecture Plan Phase 2.
Owns the interaction log and session-metadata recording that feed
cognitive-adaptation signals, kept separate from the durable user
profile so context-cache stability is easy to reason about.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .paths import INTERACTION_LOG_PATH, SESSION_META_PATH, ensure_dirs, now_iso


def record_interaction(
    user_message: str,
    agent_response: str = "",
    outcome: str = "",
    tags: str = "",
) -> dict[str, Any]:
    """Append an interaction event to the local personalization log."""
    ensure_dirs()
    event = {
        "timestamp": now_iso(),
        "user_message": user_message,
        "agent_response": agent_response,
        "outcome": outcome,
        "tags": [tag.strip() for tag in tags.split(",") if tag.strip()],
    }
    with INTERACTION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    return {"status": "ok", "log_path": str(INTERACTION_LOG_PATH), "event": event}


def _parse_iso_datetime(value: str, field_name: str, errors: list[str]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} must be an ISO 8601 timestamp")
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# ── ADR 0067: Session metadata for cognitive adaptation ──────────────


def _write_session_meta(
    message_count: int,
    inferred_goal: str = "",
    topic_stability: float = 1.0,
    completion_status: str = "ended_naturally",
    question_depth: str = "stable",
    started_at: str = "",
    ended_at: str = "",
) -> dict[str, Any]:
    """Write a lightweight session summary to session_meta.jsonl."""
    ensure_dirs()
    errors: list[str] = []

    try:
        message_count_int = int(message_count)
    except (TypeError, ValueError):
        message_count_int = 0
        errors.append("message_count must be an integer")
    if message_count_int < 0:
        errors.append("message_count must be non-negative")

    try:
        topic_stability_float = float(topic_stability)
    except (TypeError, ValueError):
        topic_stability_float = -1.0
        errors.append("topic_stability must be a number")
    if not 0.0 <= topic_stability_float <= 1.0:
        errors.append("topic_stability must be between 0.0 and 1.0")

    allowed_statuses = {"ended_naturally", "abandoned", "timeout"}
    if completion_status not in allowed_statuses:
        errors.append(
            "completion_status must be one of: "
            + ", ".join(sorted(allowed_statuses))
        )

    allowed_depth = {"deepening", "shallowing", "stable"}
    if question_depth not in allowed_depth:
        errors.append(
            "question_depth must be one of: "
            + ", ".join(sorted(allowed_depth))
        )

    ended_at_value = ended_at or now_iso()
    if not started_at:
        errors.append("started_at must be provided by runtime session state")
    started_dt = _parse_iso_datetime(started_at, "started_at", errors) if started_at else None
    ended_dt = _parse_iso_datetime(ended_at_value, "ended_at", errors)
    if started_dt is not None and ended_dt is not None and started_dt > ended_dt:
        errors.append("started_at must be before or equal to ended_at")

    if errors:
        return {"status": "error", "message": "; ".join(errors)}

    meta = {
        "session_id": f"sess_{started_at[:10].replace('-', '')}_{message_count_int:03d}",
        "started_at": started_at,
        "ended_at": ended_at_value,
        "message_count": message_count_int,
        "inferred_goal": inferred_goal or "general exploration",
        "topic_stability": round(topic_stability_float, 2),
        "completion_status": completion_status,
        "question_depth_trajectory": question_depth,
    }
    with SESSION_META_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(meta) + "\n")
    return {"status": "ok", "session_id": meta["session_id"]}
