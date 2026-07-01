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
    from research_paper_agent import agent, concept_graph

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

    monkeypatch.setattr(concept_graph, "_USER_MODEL_DIR", um)
    monkeypatch.setattr(concept_graph, "CONCEPT_GRAPH_PATH", um / "concept_graph.json")
    concept_graph._graph_cache = None
    agent._load_records._cache = None  # type: ignore[attr-defined]
    agent._load_user_profile._cache = None  # type: ignore[attr-defined]
