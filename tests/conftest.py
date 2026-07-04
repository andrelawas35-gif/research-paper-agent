"""Shared fixtures for all tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the project parent importable so ``from research_paper_agent import agent, concept_graph`` works.
_PROJECT_PARENT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_PARENT))


@pytest.fixture(autouse=True)
def _isolate_paths(monkeypatch, tmp_path: Path):
    """Redirect every file-system constant to tmp_path and reset caches."""
    from research_paper_agent import agent, concept_graph, personal_notes
    from research_paper_agent.agent_runtime import (
        audit,
        dynamic_context,
        grill,
        papers as runtime_papers,
        paths,
        retrieval,
        session_memory,
        tutor,
        user_profile,
    )

    kb = tmp_path / "knowledge_base"
    um = tmp_path / "user_model"
    papers = tmp_path / "papers"
    kb.mkdir()
    um.mkdir()
    papers.mkdir()

    monkeypatch.setattr(agent, "KNOWLEDGE_DIR", kb)
    monkeypatch.setattr(agent, "USER_MODEL_DIR", um)
    monkeypatch.setattr(agent, "PAPERS_DIR", papers)
    monkeypatch.setattr(agent, "USER_PROFILE_PATH", um / "profile.json")
    monkeypatch.setattr(agent, "INTERACTION_LOG_PATH", um / "interaction_log.jsonl")
    monkeypatch.setattr(agent, "GRILL_LOG_PATH", um / "adaptive_grill_sessions.jsonl")
    monkeypatch.setattr(agent, "CANDIDATE_SIGNALS_PATH", um / "candidate_signals.jsonl")
    monkeypatch.setattr(agent, "CONCEPT_GRAPH_PATH", um / "concept_graph.json")
    monkeypatch.setattr(agent, "TUTOR_PROGRESS_PATH", um / "tutor_progress.json")
    monkeypatch.setattr(agent, "TUTOR_SESSIONS_PATH", um / "tutor_sessions.jsonl")
    monkeypatch.setattr(agent, "PERSONAL_NOTES_PATH", um / "personal_notes.jsonl")
    monkeypatch.setattr(agent, "PEOPLE_PATH", um / "people.jsonl")
    monkeypatch.setattr(agent, "SESSION_META_PATH", um / "session_meta.jsonl")

    monkeypatch.setattr(paths, "KNOWLEDGE_DIR", kb)
    monkeypatch.setattr(paths, "USER_MODEL_DIR", um)
    monkeypatch.setattr(paths, "PAPERS_DIR", papers)
    monkeypatch.setattr(paths, "USER_PROFILE_PATH", um / "profile.json")
    monkeypatch.setattr(paths, "INTERACTION_LOG_PATH", um / "interaction_log.jsonl")
    monkeypatch.setattr(paths, "GRILL_LOG_PATH", um / "adaptive_grill_sessions.jsonl")
    monkeypatch.setattr(paths, "CANDIDATE_SIGNALS_PATH", um / "candidate_signals.jsonl")
    monkeypatch.setattr(paths, "CONCEPT_GRAPH_PATH", um / "concept_graph.json")
    monkeypatch.setattr(paths, "TUTOR_PROGRESS_PATH", um / "tutor_progress.json")
    monkeypatch.setattr(paths, "TUTOR_SESSIONS_PATH", um / "tutor_sessions.jsonl")
    monkeypatch.setattr(paths, "PERSONAL_NOTES_PATH", um / "personal_notes.jsonl")
    monkeypatch.setattr(paths, "PEOPLE_PATH", um / "people.jsonl")
    monkeypatch.setattr(paths, "SESSION_META_PATH", um / "session_meta.jsonl")

    monkeypatch.setattr(runtime_papers, "KNOWLEDGE_DIR", kb)
    monkeypatch.setattr(runtime_papers, "PAPERS_DIR", papers)

    # Each agent_runtime submodule binds its own path constants at import
    # time (``from .paths import X``), so patching agent.py's or paths.py's
    # copy alone does not redirect these modules — they must be patched
    # directly, or tests silently read/write the real user_model directory.
    monkeypatch.setattr(user_profile, "USER_PROFILE_PATH", um / "profile.json")
    monkeypatch.setattr(user_profile, "CANDIDATE_SIGNALS_PATH", um / "candidate_signals.jsonl")
    monkeypatch.setattr(session_memory, "INTERACTION_LOG_PATH", um / "interaction_log.jsonl")
    monkeypatch.setattr(session_memory, "SESSION_META_PATH", um / "session_meta.jsonl")
    monkeypatch.setattr(tutor, "TUTOR_PROGRESS_PATH", um / "tutor_progress.json")
    monkeypatch.setattr(tutor, "TUTOR_SESSIONS_PATH", um / "tutor_sessions.jsonl")
    monkeypatch.setattr(grill, "GRILL_LOG_PATH", um / "adaptive_grill_sessions.jsonl")
    monkeypatch.setattr(audit, "CANDIDATE_SIGNALS_PATH", um / "candidate_signals.jsonl")
    monkeypatch.setattr(audit, "INTERACTION_LOG_PATH", um / "interaction_log.jsonl")

    monkeypatch.setattr(dynamic_context, "CONCEPT_GRAPH_PATH", um / "concept_graph.json")
    monkeypatch.setattr(dynamic_context, "PERSONAL_NOTES_PATH", um / "personal_notes.jsonl")
    monkeypatch.setattr(dynamic_context, "SESSION_META_PATH", um / "session_meta.jsonl")
    monkeypatch.setattr(dynamic_context, "TUTOR_PROGRESS_PATH", um / "tutor_progress.json")
    monkeypatch.setattr(dynamic_context, "USER_PROFILE_PATH", um / "profile.json")

    monkeypatch.setattr(concept_graph, "_USER_MODEL_DIR", um)
    monkeypatch.setattr(concept_graph, "CONCEPT_GRAPH_PATH", um / "concept_graph.json")
    monkeypatch.setattr(personal_notes, "USER_MODEL_DIR", um)
    monkeypatch.setattr(personal_notes, "PERSONAL_NOTES_PATH", um / "personal_notes.jsonl")
    concept_graph._graph_cache = None
    agent._load_records._cache = None  # type: ignore[attr-defined]
    agent._load_user_profile._cache = None  # type: ignore[attr-defined]
    agent._load_tutor_progress._cache = None  # type: ignore[attr-defined]
    runtime_papers._load_records._cache = None  # type: ignore[attr-defined]
    retrieval._clear_search_cache()
    dynamic_context._SNAPSHOT_CACHE.clear()
