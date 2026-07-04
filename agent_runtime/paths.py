"""Shared path constants and directory helpers.

Extracted from agent.py so every runtime module can import paths
without creating a circular dependency on the composition module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
PAPERS_DIR = APP_DIR / "papers"
KNOWLEDGE_DIR = APP_DIR / "knowledge_base"
USER_MODEL_DIR = APP_DIR / "user_model"

USER_PROFILE_PATH = USER_MODEL_DIR / "profile.json"
INTERACTION_LOG_PATH = USER_MODEL_DIR / "interaction_log.jsonl"
GRILL_LOG_PATH = USER_MODEL_DIR / "adaptive_grill_sessions.jsonl"
CANDIDATE_SIGNALS_PATH = USER_MODEL_DIR / "candidate_signals.jsonl"
CONCEPT_GRAPH_PATH = USER_MODEL_DIR / "concept_graph.json"
TUTOR_PROGRESS_PATH = USER_MODEL_DIR / "tutor_progress.json"
TUTOR_SESSIONS_PATH = USER_MODEL_DIR / "tutor_sessions.jsonl"
PERSONAL_NOTES_PATH = USER_MODEL_DIR / "personal_notes.jsonl"
PEOPLE_PATH = USER_MODEL_DIR / "people.jsonl"
SESSION_META_PATH = USER_MODEL_DIR / "session_meta.jsonl"


def ensure_dirs() -> None:
    """Create standard data directories if they don't exist."""
    PAPERS_DIR.mkdir(exist_ok=True)
    KNOWLEDGE_DIR.mkdir(exist_ok=True)
    USER_MODEL_DIR.mkdir(exist_ok=True)


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
