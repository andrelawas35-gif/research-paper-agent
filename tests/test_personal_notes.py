"""Tests for local personal-note storage and agent wrappers."""

from __future__ import annotations

import json
from pathlib import Path


def test_save_note_creates_schema_record(tmp_path: Path):
    from research_paper_agent import personal_notes

    path = tmp_path / "personal_notes.jsonl"

    result = personal_notes.save_note(
        "Graph memory should separate user notes from paper evidence.",
        title="Graph memory",
        user_tags="agent, knowledge management",
        concepts="concept graph, personal notes",
        path=path,
    )

    assert result["status"] == "ok"
    assert result["note_id"].startswith("note_")
    note = result["note"]
    assert note["schema_version"] == 1
    assert note["title"] == "Graph memory"
    assert note["text"].startswith("Graph memory")
    assert note["deleted_at"] is None
    assert note["user_tags"] == ["agent", "knowledge management"]
    assert "graph" in note["suggested_tags"]
    assert len(note["cards"]) == 1
    assert note["cards"][0]["card_id"] == "card_001"
    assert note["cards"][0]["text"] == "Graph memory should separate user notes from paper evidence."
    assert note["cards"][0]["rejected"] is False
    assert note["concepts"][:2] == ["concept graph", "personal notes"]
    assert note["candidate_signals"] == []
    assert note["markdown_path"] is None
    assert note["versions"] == []

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["note_id"] == result["note_id"]


def test_save_note_derives_title_and_incrementing_ids(tmp_path: Path):
    from research_paper_agent import personal_notes

    path = tmp_path / "personal_notes.jsonl"

    first = personal_notes.save_note("First note body", path=path)
    second = personal_notes.save_note("Second note body", path=path)

    assert first["note"]["title"] == "First note body"
    assert second["note"]["title"] == "Second note body"
    assert first["note_id"] != second["note_id"]
    assert second["note_id"].endswith("_002")


def test_list_get_and_search_notes(tmp_path: Path):
    from research_paper_agent import personal_notes

    path = tmp_path / "personal_notes.jsonl"
    saved = personal_notes.save_note(
        "Obsidian-like backlinks should be concept-derived first.",
        user_tags="obsidian",
        concepts="backlinks, concept graph",
        path=path,
    )

    listed = personal_notes.list_notes(path=path)
    assert listed["count"] == 1
    assert listed["notes"][0]["note_id"] == saved["note_id"]

    fetched = personal_notes.get_note(saved["note_id"], path=path)
    assert fetched["status"] == "ok"
    assert fetched["note"]["text"].startswith("Obsidian-like")

    by_text = personal_notes.search_notes("backlinks", path=path)
    by_tag = personal_notes.search_notes("obsidian", path=path)
    by_concept = personal_notes.search_notes("concept graph", path=path)

    assert by_text["matches"][0]["note_id"] == saved["note_id"]
    assert by_tag["matches"][0]["note_id"] == saved["note_id"]
    assert by_concept["matches"][0]["note_id"] == saved["note_id"]


def test_save_note_extracts_conservative_cards_concepts_and_tags(tmp_path: Path):
    from research_paper_agent import personal_notes

    path = tmp_path / "personal_notes.jsonl"

    saved = personal_notes.save_note(
        (
            "Knowledge management should keep paper evidence separate from personal notes. "
            "The self-learning loop needs candidate signals before confirmed adaptation rules. "
            "Tiny aside."
        ),
        user_tags="agent",
        path=path,
    )

    note = saved["note"]

    assert 1 <= len(note["cards"]) <= 5
    assert note["cards"][0] == {
        "card_id": "card_001",
        "text": "Knowledge management should keep paper evidence separate from personal notes.",
        "concepts": note["cards"][0]["concepts"],
        "rejected": False,
    }
    assert all(card["concepts"] for card in note["cards"])
    assert "knowledge" in note["suggested_tags"]
    assert "agent" not in note["suggested_tags"]
    assert any("knowledge" in concept for concept in note["concepts"])


def test_soft_deleted_notes_are_hidden_from_list_and_search(tmp_path: Path):
    from research_paper_agent import personal_notes

    path = tmp_path / "personal_notes.jsonl"
    saved = personal_notes.save_note("Hide this provisional memory.", path=path)

    deleted = personal_notes.soft_delete_note(saved["note_id"], path=path)

    assert deleted["status"] == "ok"
    assert deleted["changed"] is True
    assert personal_notes.list_notes(path=path)["notes"] == []
    assert personal_notes.search_notes("provisional", path=path)["matches"] == []

    recovered = personal_notes.get_note(saved["note_id"], path=path, include_deleted=True)
    assert recovered["status"] == "ok"
    assert recovered["note"]["deleted_at"] is not None


def test_agent_personal_note_wrappers_use_user_model_path():
    from research_paper_agent import agent

    saved = agent.save_personal_note(
        "Self-learning should keep weak signals separate from confirmed rules.",
        title="Weak signals",
        user_tags="adaptation",
        concepts="self-learning, candidate signals",
    )

    assert saved["status"] == "ok"
    assert saved["notes_path"] == str(agent.PERSONAL_NOTES_PATH)
    assert agent.list_personal_notes()["count"] == 1
    assert agent.get_personal_note(saved["note_id"])["note"]["title"] == "Weak signals"
    assert agent.search_personal_notes("candidate signals")["matches"][0]["note_id"] == saved["note_id"]

    deleted = agent.delete_personal_note(saved["note_id"])
    assert deleted["status"] == "ok"
    assert agent.list_personal_notes()["notes"] == []
