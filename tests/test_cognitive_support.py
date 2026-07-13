"""Tests for A4: Cognitive Support policies."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Override conftest autouse fixture
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    """No-op: cognitive support tests are self-contained."""
    pass


from agent_runtime.cognitive_support import (
    COGNITIVE_SUPPORT_PATH,
    CapacityLevel,
    ChoiceLimit,
    ChunkSize,
    CognitiveSupportProfile,
    ParkedQuestion,
    _default_profile,
    _dict_to_profile,
    _profile_to_dict,
    chunk_points,
    frame_next_actions,
    get_parked_questions,
    inspect_profile,
    limit_choices,
    load_profile,
    park_question,
    resolve_parked_question,
    save_profile,
    should_reanchor,
    update_profile,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_profile(**overrides: Any) -> CognitiveSupportProfile:
    """Create a CognitiveSupportProfile with overrides."""
    defaults: Dict[str, Any] = {}
    defaults.update(overrides)
    return CognitiveSupportProfile(**defaults)


# ── Profile load/save tests ──────────────────────────────────────────


class TestProfilePersistence:
    def test_default_profile(self):
        p = _default_profile()
        assert p.schema_version == 1
        assert p.default_capacity == CapacityLevel.UNKNOWN
        assert p.preferred_chunk_size == ChunkSize.ADAPTIVE

    def test_round_trip(self):
        tmp = Path(tempfile.mktemp(suffix=".json"))
        p = _make_profile(
            default_capacity=CapacityLevel.LOW,
            max_points_per_chunk=3,
        )
        save_profile(p, path=tmp)
        loaded = load_profile(path=tmp)
        assert loaded.default_capacity == CapacityLevel.LOW
        assert loaded.max_points_per_chunk == 3

    def test_load_missing_returns_default(self):
        tmp = Path(tempfile.mktemp(suffix=".json"))
        # Delete the file if it exists
        if tmp.exists():
            tmp.unlink()
        p = load_profile(path=tmp)
        assert p.schema_version == 1

    def test_load_corrupt_returns_default(self):
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text("not valid json")
        p = load_profile(path=tmp)
        assert p.schema_version == 1
        assert p.recovery_note is not None


# ── Inspect tests ────────────────────────────────────────────────────


class TestInspectProfile:
    def test_inspect_returns_all_sections(self):
        result = inspect_profile(_default_profile())
        assert "capacity" in result
        assert "choices" in result
        assert "pause_recovery" in result
        assert "question_parking" in result
        assert "commitment_framing" in result
        assert "pacing" in result
        assert "comprehension" in result

    def test_inspect_no_diagnostic_language(self):
        result = inspect_profile(_default_profile())
        flat = json.dumps(result)
        # These terms should not appear except in explicit negations
        diagnostic_terms = ["disorder", "symptom", "treatment"]
        for term in diagnostic_terms:
            assert term not in flat.lower(), f"Diagnostic term '{term}' found in output"

    def test_every_setting_has_description(self):
        result = inspect_profile(_default_profile())

        def check_descriptions(obj: Any) -> None:
            if isinstance(obj, dict):
                if "value" in obj and "description" in obj:
                    assert len(obj["description"]) > 0
                for v in obj.values():
                    check_descriptions(v)

        check_descriptions(result)


# ── Update tests ─────────────────────────────────────────────────────


class TestUpdateProfile:
    def test_update_known_field(self):
        p = _default_profile()
        updated = update_profile({"max_points_per_chunk": 3}, profile=p)
        assert updated.max_points_per_chunk == 3

    def test_update_enum_field(self):
        p = _default_profile()
        updated = update_profile({"default_capacity": "low"}, profile=p)
        assert updated.default_capacity == CapacityLevel.LOW

    def test_ignores_unknown_fields(self):
        p = _default_profile()
        updated = update_profile({"not_a_real_field": "value"}, profile=p)
        assert updated.schema_version == 1  # unchanged

    def test_update_boolean(self):
        p = _default_profile()
        updated = update_profile({"check_comprehension": True}, profile=p)
        assert updated.check_comprehension is True

    def test_persists_update(self):
        tmp = Path(tempfile.mktemp(suffix=".json"))
        p = _default_profile()
        update_profile({"max_points_per_chunk": 7}, profile=p, path=tmp)
        loaded = load_profile(path=tmp)
        assert loaded.max_points_per_chunk == 7


# ── Chunking tests ───────────────────────────────────────────────────


class TestChunkPoints:
    def test_empty(self):
        chunks = chunk_points([], _default_profile())
        assert chunks == []

    def test_single_chunk(self):
        points = ["a", "b", "c"]
        chunks = chunk_points(points, _make_profile(max_points_per_chunk=5))
        assert len(chunks) == 1
        assert len(chunks[0]) == 3

    def test_multiple_chunks(self):
        points = ["a", "b", "c", "d", "e", "f", "g"]
        chunks = chunk_points(points, _make_profile(max_points_per_chunk=3))
        assert len(chunks) == 3
        assert len(chunks[0]) == 3

    def test_small_chunk_size(self):
        points = ["a", "b", "c", "d", "e"]
        profile = _make_profile(
            preferred_chunk_size=ChunkSize.SMALL,
            max_points_per_chunk=10,
        )
        chunks = chunk_points(points, profile)
        for chunk in chunks:
            assert len(chunk) <= 2

    def test_low_capacity_reduces_chunks(self):
        points = ["a", "b", "c", "d", "e"]
        profile = _make_profile(max_points_per_chunk=10)
        chunks = chunk_points(points, profile, capacity=CapacityLevel.LOW)
        for chunk in chunks:
            assert len(chunk) <= 2

    def test_high_capacity_allows_more(self):
        points = ["a", "b", "c", "d", "e", "f"]
        profile = _make_profile(max_points_per_chunk=10)
        chunks = chunk_points(points, profile, capacity=CapacityLevel.HIGH)
        for chunk in chunks:
            assert len(chunk) <= 6


# ── Choice limiting tests ────────────────────────────────────────────


class TestLimitChoices:
    def test_limits_to_profile_max(self):
        options = ["a", "b", "c", "d", "e", "f", "g", "h"]
        result = limit_choices(options, _make_profile(max_choices_shown=3))
        assert len(result) == 3

    def test_minimal_choice_limit(self):
        options = ["a", "b", "c", "d", "e"]
        result = limit_choices(options, _make_profile(choice_limit=ChoiceLimit.MINIMAL, max_choices_shown=5))
        assert len(result) <= 3

    def test_expanded_choice_limit(self):
        options = ["a", "b", "c", "d", "e", "f", "g", "h"]
        result = limit_choices(options, _make_profile(choice_limit=ChoiceLimit.EXPANDED, max_choices_shown=10))
        assert len(result) == 8

    def test_fewer_options_than_limit(self):
        options = ["a", "b"]
        result = limit_choices(options, _make_profile(max_choices_shown=5))
        assert len(result) == 2


# ── Pause recovery tests ─────────────────────────────────────────────


class TestShouldReanchor:
    def test_no_previous_activity(self):
        result = should_reanchor(profile=_default_profile())
        assert result["should_reanchor"] is False

    def test_short_gap(self):
        result = should_reanchor(
            current_time="2026-07-12T10:05:00Z",
            last_active_at="2026-07-12T10:00:00Z",
            profile=_default_profile(),
        )
        assert result["should_reanchor"] is False

    def test_long_gap(self):
        result = should_reanchor(
            current_time="2026-07-12T11:00:00Z",
            last_active_at="2026-07-12T10:00:00Z",
            profile=_default_profile(),
        )
        assert result["should_reanchor"] is True
        assert "phrasing" in result

    def test_cross_day(self):
        result = should_reanchor(
            current_time="2026-07-13T10:00:00Z",
            last_active_at="2026-07-12T23:55:00Z",
            profile=_default_profile(),
        )
        assert result["should_reanchor"] is True

    def test_cross_day_can_be_disabled(self):
        result = should_reanchor(
            current_time="2026-07-13T10:00:00Z",
            last_active_at="2026-07-12T23:55:00Z",
            profile=_make_profile(always_reanchor_cross_day=False),
        )
        # 10 hour gap should still trigger time-based reanchor
        assert result["should_reanchor"] is True

    def test_custom_threshold(self):
        result = should_reanchor(
            current_time="2026-07-12T10:10:00Z",
            last_active_at="2026-07-12T10:00:00Z",
            profile=_make_profile(reanchor_after_minutes=5),
        )
        assert result["should_reanchor"] is True


# ── Question parking tests ───────────────────────────────────────────


class TestParkQuestion:
    def test_park_question_success(self):
        result = park_question(
            "What is the capital of France?",
            "geography study",
            profile=_default_profile(),
        )
        assert result["status"] == "ok"
        assert "question_id" in result

    def test_park_disabled(self):
        result = park_question(
            "What is the capital?",
            "context",
            profile=_make_profile(enable_question_parking=False),
        )
        assert result["status"] == "error"

    def test_parking_lot_full(self):
        parked = [
            ParkedQuestion(
                question_id=f"pq_{i:03d}",
                question=f"Question {i}",
                context="test",
                parked_at="2026-07-12T00:00:00Z",
            )
            for i in range(10)
        ]
        result = park_question(
            "New question",
            "context",
            parked_questions=parked,
            profile=_make_profile(max_parked_questions=10),
        )
        assert result["status"] == "error"
        assert "full" in result["message"].lower()


class TestGetParkedQuestions:
    def test_filters_resolved(self):
        parked = [
            ParkedQuestion(
                question_id="pq_1",
                question="Q1",
                context="test",
                parked_at="2026-07-12T00:00:00Z",
                resolved=True,
            ),
            ParkedQuestion(
                question_id="pq_2",
                question="Q2",
                context="test",
                parked_at="2026-07-12T00:00:00Z",
            ),
        ]
        active = get_parked_questions(parked)
        assert len(active) == 1
        assert active[0].question_id == "pq_2"

    def test_include_resolved(self):
        parked = [
            ParkedQuestion(
                question_id="pq_1",
                question="Q1",
                context="test",
                parked_at="2026-07-12T00:00:00Z",
                resolved=True,
            ),
        ]
        all_qs = get_parked_questions(parked, include_resolved=True)
        assert len(all_qs) == 1


class TestResolveParkedQuestion:
    def test_resolve_existing(self):
        parked = [
            ParkedQuestion(
                question_id="pq_test",
                question="Test",
                context="test",
                parked_at="2026-07-12T00:00:00Z",
            ),
        ]
        result = resolve_parked_question("pq_test", parked)
        assert result["status"] == "ok"
        assert parked[0].resolved is True

    def test_resolve_not_found(self):
        result = resolve_parked_question("nonexistent", [])
        assert result["status"] == "error"


# ── Commitment framing tests ─────────────────────────────────────────


class TestFrameNextActions:
    def test_frames_actions(self):
        result = frame_next_actions(
            ["Review notes", "Practice problems", "Read chapter 3"],
            profile=_default_profile(),
        )
        assert result["offer_actions"] is True
        assert len(result["actions"]) == 3
        assert result["actions"][0]["index"] == 1

    def test_respects_max(self):
        result = frame_next_actions(
            ["a", "b", "c", "d", "e", "f"],
            profile=_make_profile(max_next_actions=3),
        )
        assert len(result["actions"]) == 3

    def test_disabled(self):
        result = frame_next_actions(
            ["a", "b"],
            profile=_make_profile(offer_next_actions=False),
        )
        assert result["offer_actions"] is False
        assert result["actions"] == []


# ── Serialization tests ──────────────────────────────────────────────


class TestSerialization:
    def test_round_trip_all_fields(self):
        p = _make_profile(
            default_capacity=CapacityLevel.LOW,
            preferred_chunk_size=ChunkSize.SMALL,
            choice_limit=ChoiceLimit.MINIMAL,
            check_comprehension=True,
            reanchor_after_minutes=15,
            max_parked_questions=5,
        )
        d = _profile_to_dict(p)
        restored = _dict_to_profile(d)
        assert restored.default_capacity == p.default_capacity
        assert restored.preferred_chunk_size == p.preferred_chunk_size
        assert restored.choice_limit == p.choice_limit
        assert restored.check_comprehension == p.check_comprehension
        assert restored.reanchor_after_minutes == p.reanchor_after_minutes
        assert restored.max_parked_questions == p.max_parked_questions
