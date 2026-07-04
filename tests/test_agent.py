"""Tests for agent — pure functions and tool-level tests with temp fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_filters_stopwords(self):
        from research_paper_agent.agent import _tokenize

        tokens = _tokenize("the paper shows results using machine learning")
        # "the" and "using" are stopwords
        assert "the" not in tokens
        assert "using" not in tokens
        assert "machine" in tokens
        assert "learning" in tokens

    def test_minimum_length(self):
        from research_paper_agent.agent import _tokenize

        # "ab" is only 2 chars — filtered
        tokens = _tokenize("ab cd abc defg")
        assert "ab" not in tokens
        assert "cd" not in tokens
        assert "abc" in tokens
        assert "defg" in tokens

    def test_keeps_hyphenated(self):
        from research_paper_agent.agent import _tokenize

        tokens = _tokenize("retrieval-augmented generation")
        # hyphenated words are kept
        assert any("retrieval-augmented" in t for t in tokens) or (
            "retrieval" in tokens and "augmented" in tokens
        )

    def test_lowercase_output(self):
        from research_paper_agent.agent import _tokenize

        tokens = _tokenize("Machine Learning")
        assert all(t == t.lower() for t in tokens)


class TestKeywords:
    def test_returns_top_words(self):
        from research_paper_agent.agent import _keywords

        text = "retrieval retrieval retrieval augmented augmented generation"
        kw = _keywords(text, limit=3)
        assert "retrieval" in kw
        assert "augmented" in kw
        assert "generation" in kw

    def test_excludes_stopwords(self):
        from research_paper_agent.agent import _keywords

        text = "the the the about about agent"
        kw = _keywords(text, limit=5)
        assert "the" not in kw
        assert "about" not in kw
        assert "agent" in kw


class TestSentences:
    def test_splits_on_period(self):
        from research_paper_agent.agent import _sentences

        text = "This is the first sentence with enough length to pass the filter. This is the second sentence also long enough for testing."
        sentences = _sentences(text)
        assert len(sentences) == 2
        assert "first sentence" in sentences[0]

    def test_filters_short(self):
        from research_paper_agent.agent import _sentences

        text = "Hi. This is a long enough sentence for the test to pass."
        sentences = _sentences(text)
        assert len(sentences) == 1


class TestCitation:
    def test_with_page(self):
        from research_paper_agent.agent import _citation

        assert _citation("paper.pdf", 3, "P0042") == "paper.pdf, page 3, P0042"

    def test_without_page(self):
        from research_paper_agent.agent import _citation

        assert _citation("paper.txt", None, "P0001") == "paper.txt, P0001"


class TestScorePassage:
    def test_exact_phrase_bonus(self):
        from research_paper_agent.agent import _score_passage
        from collections import Counter

        passage = {
            "text": "retrieval augmented generation improves accuracy",
            "keywords": ["retrieval", "generation"],
        }
        score = _score_passage(["retrieval", "augmented"], passage, 10, Counter())
        # phrase "retrieval augmented" appears → +3 bonus
        assert score > 3.0

    def test_zero_for_empty_passage(self):
        from research_paper_agent.agent import _score_passage
        from collections import Counter

        passage = {"text": "", "keywords": []}
        score = _score_passage(["test"], passage, 10, Counter())
        assert score == 0.0

    def test_keyword_bonus(self):
        from research_paper_agent.agent import _score_passage
        from collections import Counter

        passage = {
            "text": "some text about machine learning and neural networks",
            "keywords": ["machine", "neural"],
        }
        # "machine" matches query term "machine" → +0.35 bonus
        score = _score_passage(["machine"], passage, 10, Counter({"machine": 2}))
        assert score > 0.0


# ---------------------------------------------------------------------------
# Tool-level tests
# ---------------------------------------------------------------------------


class TestSearchEvidence:
    @pytest.fixture
    def _seed_record(self, tmp_path: Path):
        """Write a fake ingested-paper record so search_evidence has data."""
        from research_paper_agent import agent

        record = {
            "schema_version": 2,
            "source": "test_paper.txt",
            "metadata": {"title": "Test Paper"},
            "characters": 200,
            "page_count": 1,
            "keywords": ["retrieval", "augmented", "generation"],
            "notes": {"concepts": [], "methods": [], "findings": [], "limitations": [], "open_questions": []},
            "passages": [
                {
                    "id": "P0001",
                    "source": "test_paper.txt",
                    "page": None,
                    "citation": "test_paper.txt, P0001",
                    "text": "Retrieval augmented generation combines retrieval with language models for improved factual accuracy.",
                    "keywords": ["retrieval", "augmented", "generation", "language", "models", "factual"],
                },
                {
                    "id": "P0002",
                    "source": "test_paper.txt",
                    "page": None,
                    "citation": "test_paper.txt, P0002",
                    "text": "Benchmark evaluation shows strong performance on knowledge-intensive tasks.",
                    "keywords": ["benchmark", "evaluation", "performance", "knowledge"],
                },
            ],
        }
        kb = agent.KNOWLEDGE_DIR
        kb.mkdir(parents=True, exist_ok=True)
        (kb / "test_paper.json").write_text(json.dumps(record), encoding="utf-8")
        # Clear the record cache so it picks up the temp data.
        agent._load_records._cache = None  # type: ignore[attr-defined]

    def test_finds_relevant_passage(self, _seed_record):
        from research_paper_agent.agent import search_evidence

        result = search_evidence("retrieval augmented")
        assert len(result["matches"]) > 0
        assert any("retrieval" in m["passage"].lower() for m in result["matches"])

    def test_returns_empty_for_no_match(self, _seed_record):
        from research_paper_agent.agent import search_evidence

        result = search_evidence("zzz_nonexistent_term_zzz")
        assert result["matches"] == []

    def test_respects_max_passages(self, _seed_record):
        from research_paper_agent.agent import search_evidence

        result = search_evidence("retrieval", max_passages=1)
        assert len(result["matches"]) <= 1

    def test_filters_by_evidence_scope(self):
        from research_paper_agent import agent
        from research_paper_agent.agent import search_evidence

        simon_record = {
            "schema_version": 2,
            "source": "simon_design.txt",
            "metadata": {"title": "Simon Design"},
            "evidence_scope": ["mentor:simon"],
            "characters": 100,
            "page_count": 1,
            "keywords": ["bounded", "rationality"],
            "notes": {"concepts": [], "methods": [], "findings": [], "limitations": [], "open_questions": []},
            "passages": [
                {
                    "id": "P0001",
                    "source": "simon_design.txt",
                    "page": None,
                    "citation": "simon_design.txt, P0001",
                    "text": "Bounded rationality frames design as search under constraints.",
                    "keywords": ["bounded", "rationality", "design"],
                }
            ],
        }
        ordinary_record = {
            "schema_version": 2,
            "source": "fpga_design.txt",
            "metadata": {"title": "FPGA Design"},
            "characters": 100,
            "page_count": 1,
            "keywords": ["bounded", "rationality"],
            "notes": {"concepts": [], "methods": [], "findings": [], "limitations": [], "open_questions": []},
            "passages": [
                {
                    "id": "P0001",
                    "source": "fpga_design.txt",
                    "page": None,
                    "citation": "fpga_design.txt, P0001",
                    "text": "Bounded rationality appears here as an unrelated phrase.",
                    "keywords": ["bounded", "rationality"],
                }
            ],
        }

        (agent.KNOWLEDGE_DIR / "simon_design.json").write_text(
            json.dumps(simon_record), encoding="utf-8"
        )
        (agent.KNOWLEDGE_DIR / "fpga_design.json").write_text(
            json.dumps(ordinary_record), encoding="utf-8"
        )
        agent._load_records._cache = None  # type: ignore[attr-defined]

        result = search_evidence("bounded rationality", evidence_scope="mentor:simon")

        assert [match["source"] for match in result["matches"]] == ["simon_design.txt"]

    def test_unknown_evidence_scope_returns_no_matches(self):
        from research_paper_agent import agent
        from research_paper_agent.agent import search_evidence

        record = {
            "schema_version": 2,
            "source": "simon_design.txt",
            "metadata": {"title": "Simon Design"},
            "evidence_scope": ["mentor:simon"],
            "characters": 100,
            "page_count": 1,
            "keywords": ["bounded", "rationality"],
            "notes": {"concepts": [], "methods": [], "findings": [], "limitations": [], "open_questions": []},
            "passages": [
                {
                    "id": "P0001",
                    "source": "simon_design.txt",
                    "page": None,
                    "citation": "simon_design.txt, P0001",
                    "text": "Bounded rationality frames design as search under constraints.",
                    "keywords": ["bounded", "rationality", "design"],
                }
            ],
        }
        (agent.KNOWLEDGE_DIR / "simon_design.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        agent._load_records._cache = None  # type: ignore[attr-defined]

        result = search_evidence("bounded rationality", evidence_scope="mentor:lanier")

        assert result["matches"] == []


class TestListPapers:
    def test_empty_dir(self):
        from research_paper_agent.agent import list_papers

        result = list_papers()
        assert result["papers"] == []


class TestIngestAllPapers:
    def test_empty_papers_dir(self):
        from research_paper_agent.agent import ingest_all_papers

        result = ingest_all_papers()
        assert result["count"] == 0


class TestIngestEvidenceScope:
    def test_ingest_paper_stores_explicit_evidence_scope(self):
        from research_paper_agent import agent
        from research_paper_agent.agent import ingest_paper

        (agent.PAPERS_DIR / "simon_design.txt").write_text(
            "Bounded rationality frames design as search under constraints. "
            "Design science studies artifacts and choices in complex situations.",
            encoding="utf-8",
        )

        result = ingest_paper("simon_design.txt", evidence_scope="mentor:simon")

        assert result["status"] == "ok"
        record = json.loads((agent.KNOWLEDGE_DIR / "simon_design.json").read_text(encoding="utf-8"))
        assert record["evidence_scope"] == ["mentor:simon"]

    def test_ingest_paper_can_infer_mentor_scope_from_import_name(self):
        from research_paper_agent import agent
        from research_paper_agent.agent import ingest_paper

        (agent.PAPERS_DIR / "lanier_agency.txt").write_text(
            "Human agency matters when systems reduce people to data. "
            "The argument centers experience and dignity in networked tools.",
            encoding="utf-8",
        )

        result = ingest_paper("lanier_agency.txt")

        assert result["status"] == "ok"
        record = json.loads((agent.KNOWLEDGE_DIR / "lanier_agency.json").read_text(encoding="utf-8"))
        assert record["evidence_scope"] == ["mentor:lanier"]


class TestGetUserProfile:
    def test_returns_default_profile(self):
        from research_paper_agent.agent import get_user_profile

        result = get_user_profile()
        assert "profile" in result
        assert "interests" in result["profile"]


class TestSetUserPreference:
    def test_adds_interest(self):
        from research_paper_agent.agent import set_user_preference

        result = set_user_preference("interest", "knowledge graphs", "test", 0.9)
        assert result["status"] == "ok"
        assert result["changed"] is True

    def test_unknown_category(self):
        from research_paper_agent.agent import set_user_preference

        result = set_user_preference("nonexistent", "value")
        assert result["status"] == "error"


class TestSessionMetadata:
    def test_writes_runtime_session_boundaries(self):
        from research_paper_agent import agent
        from research_paper_agent.agent import _write_session_meta

        result = _write_session_meta(
            message_count=4,
            inferred_goal="mentor exploration",
            topic_stability=0.75,
            completion_status="timeout",
            question_depth="deepening",
            started_at="2026-07-02T15:00:00+00:00",
            ended_at="2026-07-02T15:22:00+00:00",
        )

        assert result["status"] == "ok"
        meta = json.loads(agent.SESSION_META_PATH.read_text(encoding="utf-8").splitlines()[-1])
        assert meta["started_at"] == "2026-07-02T15:00:00+00:00"
        assert meta["ended_at"] == "2026-07-02T15:22:00+00:00"
        assert meta["topic_stability"] == 0.75
        assert meta["completion_status"] == "timeout"
        assert meta["question_depth_trajectory"] == "deepening"

    def test_rejects_invalid_session_metadata(self):
        from research_paper_agent.agent import _write_session_meta

        result = _write_session_meta(
            message_count=4,
            topic_stability=1.2,
            completion_status="done",
            question_depth="wandering",
            started_at="2026-07-02T15:22:00+00:00",
            ended_at="2026-07-02T15:00:00+00:00",
        )

        assert result["status"] == "error"
        assert "topic_stability" in result["message"]
        assert "completion_status" in result["message"]
        assert "question_depth" in result["message"]
        assert "started_at" in result["message"]


class TestDynamicInstructionCacheStability:
    def test_long_session_hint_does_not_change_between_consecutive_turns(self):
        from research_paper_agent import agent

        agent._SNAPSHOT_CACHE.clear()
        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

        class Session:
            events: list[object]

        class Ctx:
            session: Session

        first_ctx = Ctx()
        first_ctx.session = Session()
        first_ctx.session.events = [object()] * 81

        second_ctx = Ctx()
        second_ctx.session = Session()
        second_ctx.session.events = [object()] * 82

        first = agent._dynamic_instruction(first_ctx)
        second = agent._dynamic_instruction(second_ctx)

        assert first == second
        assert "long session" in first
        assert "81" not in first
        assert "82" not in second


# ---------------------------------------------------------------------------
# ADR 0072: Performance Budget — inference and snapshot tests
# ---------------------------------------------------------------------------


class TestBudgetInference:
    """Pure budget inference from text — no ADK context needed."""

    @pytest.mark.parametrize("text,expected", [
        ("keep it quick", "fast"),
        ("fast mode", "fast"),
        ("just tell me the answer", "fast"),
        ("quickly check this", "fast"),
        ("don't explain, just do it", "fast"),
        ("make it fast", "fast"),
        ("think deeply about this", "deep"),
        ("deep mode analysis", "deep"),
        ("go deep on this topic", "deep"),
        ("thorough review", "deep"),
        ("comprehensive analysis", "deep"),
        ("in-depth explanation", "deep"),
        ("take your time", "deep"),
    ])
    def test_explicit_wording_wins(self, text, expected):
        from research_paper_agent.agent_runtime.dynamic_context import (
            _infer_performance_budget_from_text,
        )

        assert _infer_performance_budget_from_text(text) == expected

    def test_empty_text_falls_back_to_balanced(self):
        from research_paper_agent.agent_runtime.dynamic_context import (
            _infer_performance_budget_from_text,
        )

        assert _infer_performance_budget_from_text("") == "balanced"

    def test_no_signal_defaults_to_balanced(self):
        from research_paper_agent.agent_runtime.dynamic_context import (
            _infer_performance_budget_from_text,
        )

        assert _infer_performance_budget_from_text("hello, what papers do I have?") == "balanced"

    def test_mode_hint_suggests_deep(self):
        from research_paper_agent.agent_runtime.dynamic_context import (
            _infer_performance_budget_from_text,
        )

        # Grill mode should suggest deep when no explicit wording.
        assert _infer_performance_budget_from_text("grill me on this paper", "grill") == "deep"

    def test_explicit_beats_mode_hint(self):
        from research_paper_agent.agent_runtime.dynamic_context import (
            _infer_performance_budget_from_text,
        )

        # "keep it quick" beats "grill" mode hint.
        assert _infer_performance_budget_from_text("keep it quick, grill me", "grill") == "fast"

    def test_mode_hint_suggests_fast(self):
        from research_paper_agent.agent_runtime.dynamic_context import (
            _infer_performance_budget_from_text,
        )

        assert _infer_performance_budget_from_text("list my papers", "admin") == "fast"

    def test_unknown_mode_hint_falls_back(self):
        from research_paper_agent.agent_runtime.dynamic_context import (
            _infer_performance_budget_from_text,
        )

        assert _infer_performance_budget_from_text("some text", "unknown_mode") == "balanced"

    def test_context_extraction_failure_falls_back(self):
        from research_paper_agent.agent_runtime.dynamic_context import (
            _infer_performance_budget,
        )

        # None context should not raise.
        result = _infer_performance_budget(None)
        assert result == "balanced"

    def test_validate_tier_rejects_invalid(self):
        from research_paper_agent.agent_runtime.dynamic_context import _validate_tier

        assert _validate_tier("invalid") == "balanced"
        assert _validate_tier("fast") == "fast"
        assert _validate_tier("DEEP") == "deep"


class TestBalancedSnapshot:
    """Balanced snapshot includes only stable orientation fields."""

    def test_includes_stable_fields(self):
        from research_paper_agent import agent
        from research_paper_agent.agent_runtime.dynamic_context import (
            _build_balanced_snapshot,
        )

        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [{"name": "research agents", "evidence": "test", "confidence": 0.8}],
            "style_preferences": [{"preference": "be direct", "evidence": "test", "confidence": 0.7}],
            "adaptation_rules": [],
            "avoidances": [{"rule": "no small talk", "source": "test", "confidence": 0.6}],
            "polish_preferences": {"default": "moderate"},
            "grammar_and_quirks": [{"observation": "lowercase", "evidence": "test", "confidence": 0.5}],
        })

        snapshot = _build_balanced_snapshot()
        assert "interests:" in snapshot
        assert "research agents" in snapshot
        assert "style:" in snapshot
        assert "be direct" in snapshot
        assert "polish: moderate" in snapshot
        assert "avoid:" in snapshot
        assert "no small talk" in snapshot
        assert "quirks:" in snapshot
        assert "lowercase" in snapshot

    def test_excludes_recent_notes(self):
        from research_paper_agent import agent
        from research_paper_agent.agent_runtime.dynamic_context import (
            _build_balanced_snapshot,
        )

        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

        snapshot = _build_balanced_snapshot()
        assert "recent notes:" not in snapshot

    def test_excludes_weak_concepts(self):
        from research_paper_agent import agent
        from research_paper_agent.agent_runtime.dynamic_context import (
            _build_balanced_snapshot,
        )

        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

        snapshot = _build_balanced_snapshot()
        assert "weak concepts:" not in snapshot

    def test_excludes_session_metadata(self):
        from research_paper_agent import agent
        from research_paper_agent.agent_runtime.dynamic_context import (
            _build_balanced_snapshot,
        )

        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

        snapshot = _build_balanced_snapshot()
        assert "prior session:" not in snapshot

    def test_no_volatile_counts(self):
        from research_paper_agent import agent
        from research_paper_agent.agent_runtime.dynamic_context import (
            _build_balanced_snapshot,
        )

        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

        snapshot = _build_balanced_snapshot()
        # Counts like "(5)" after concepts should not appear.
        if "top concepts:" in snapshot:
            import re
            concepts_part = snapshot.split("top concepts:")[1].split("\n")[0]
            assert not re.search(r"\(\d+\)", concepts_part)


class TestFastBudget:
    """Fast budget bypasses snapshot entirely."""

    def test_fast_returns_empty_string(self):
        from research_paper_agent.agent_runtime.dynamic_context import (
            _infer_performance_budget_from_text,
            build_dynamic_instruction,
        )

        # Create a context where the latest user text triggers fast.
        class Event:
            author = "user"
            content = "keep it quick"

        class Session:
            events: list[Event]

        class Ctx:
            session: Session

        ctx = Ctx()
        ctx.session = Session()
        ctx.session.events = [Event()]

        result = build_dynamic_instruction(ctx)
        assert result == ""


class TestBudgetCacheStability:
    """Cache stability across consecutive turns per ADR 0072."""

    def test_consecutive_balanced_turns_return_same_text(self):
        from research_paper_agent import agent
        from research_paper_agent.agent_runtime.dynamic_context import (
            _SNAPSHOT_CACHE,
            build_dynamic_instruction,
        )

        _SNAPSHOT_CACHE.clear()
        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

        class Session:
            events: list[object]

        class Ctx:
            session: Session

        ctx1 = Ctx()
        ctx1.session = Session()
        ctx1.session.events = [object()] * 5

        ctx2 = Ctx()
        ctx2.session = Session()
        ctx2.session.events = [object()] * 6

        first = build_dynamic_instruction(ctx1)
        second = build_dynamic_instruction(ctx2)

        assert first == second
        assert len(first) > 0  # balanced should return a non-empty snapshot

    def test_fast_always_returns_empty(self):
        from research_paper_agent import agent
        from research_paper_agent.agent_runtime.dynamic_context import (
            _SNAPSHOT_CACHE,
            build_dynamic_instruction,
        )

        _SNAPSHOT_CACHE.clear()
        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

        class Event:
            author = "user"
            content = "fast mode please"

        class Session:
            events: list[Event]

        class Ctx:
            session: Session

        ctx = Ctx()
        ctx.session = Session()
        ctx.session.events = [Event()]

        first = build_dynamic_instruction(ctx)
        second = build_dynamic_instruction(ctx)

        assert first == ""
        assert second == ""


# ---------------------------------------------------------------------------
# ADR 0066: Polish preference learning tests
# ---------------------------------------------------------------------------


class TestPolishPreferenceLearning:
    def test_learn_from_user_message_updates_polish_preferences(self):
        from research_paper_agent import agent
        from research_paper_agent.agent import learn_from_user_message

        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

        result = learn_from_user_message("keep my wording, don't rewrite")

        assert result["status"] == "ok"
        profile = agent._load_user_profile()
        assert profile["polish_preferences"]["default"] == "none"

    def test_polish_correction_too_formal(self):
        from research_paper_agent import agent
        from research_paper_agent.agent import learn_from_user_message

        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

        result = learn_from_user_message("this is too formal, just fix grammar")

        assert result["status"] == "ok"
        profile = agent._load_user_profile()
        assert profile["polish_preferences"]["default"] == "light"

    def test_polish_correction_too_casual(self):
        from research_paper_agent import agent
        from research_paper_agent.agent import learn_from_user_message

        agent._save_user_profile({
            "schema_version": 1,
            "updated_at": agent._now_iso(),
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

        result = learn_from_user_message("make it flow better, polish this up")

        assert result["status"] == "ok"
        profile = agent._load_user_profile()
        assert profile["polish_preferences"]["default"] == "full"

    def test_polish_signal_detection_none(self):
        from research_paper_agent.agent import _infer_message_signals

        signals = _infer_message_signals("keep my wording please")
        assert len(signals["polish_corrections"]) > 0
        assert signals["polish_corrections"][0]["level"] == "none"

    def test_polish_signal_detection_light(self):
        from research_paper_agent.agent import _infer_message_signals

        signals = _infer_message_signals("that's too formal for me")
        assert len(signals["polish_corrections"]) > 0
        assert signals["polish_corrections"][0]["level"] == "light"

    def test_no_polish_signal_for_normal_message(self):
        from research_paper_agent.agent import _infer_message_signals

        signals = _infer_message_signals("what papers do I have about agents?")
        assert signals["polish_corrections"] == []


# ---------------------------------------------------------------------------
# ADR 0070: Record validation tests
# ---------------------------------------------------------------------------


class TestRecordValidation:
    def test_validate_profile_rejects_missing_fields(self):
        from research_paper_agent.agent import _validate_profile

        assert not _validate_profile({"schema_version": 1})
        assert not _validate_profile({})

    def test_validate_profile_accepts_valid(self):
        from research_paper_agent.agent import _validate_profile

        assert _validate_profile({
            "schema_version": 1,
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
        })

    def test_validate_profile_accepts_polish_preferences(self):
        from research_paper_agent.agent import _validate_profile

        assert _validate_profile({
            "schema_version": 1,
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
            "polish_preferences": {"default": "moderate"},
        })

    def test_validate_profile_rejects_bad_polish(self):
        from research_paper_agent.agent import _validate_profile

        assert not _validate_profile({
            "schema_version": 1,
            "interests": [],
            "style_preferences": [],
            "adaptation_rules": [],
            "avoidances": [],
            "polish_preferences": "not a dict",
        })

    def test_validate_candidate_signal_rejects_missing_fields(self):
        from research_paper_agent.agent import _validate_candidate_signal

        assert not _validate_candidate_signal({"source": "test"})
        assert not _validate_candidate_signal({"timestamp": "2026-01-01"})

    def test_validate_candidate_signal_accepts_valid(self):
        from research_paper_agent.agent import _validate_candidate_signal

        assert _validate_candidate_signal({
            "timestamp": "2026-07-03T12:00:00Z",
            "signals": [{"type": "interest", "value": "test"}],
        })

    def test_validate_tutor_progress_rejects_missing_fields(self):
        from research_paper_agent.agent import _validate_tutor_progress

        assert not _validate_tutor_progress({"schema_version": "abc"})
        assert not _validate_tutor_progress({"concepts": {}})

    def test_validate_tutor_progress_accepts_valid(self):
        from research_paper_agent.agent import _validate_tutor_progress

        assert _validate_tutor_progress({
            "schema_version": 1,
            "concepts": {"embeddings": {"times_asked": 3, "times_correct": 2}},
        })

    def test_validate_tutor_progress_defaults_on_corruption(self):
        from research_paper_agent import agent

        # Write corrupted tutor progress and verify recovery.
        agent.TUTOR_PROGRESS_PATH.write_text(
            '{"schema_version": "bad", "concepts": "not a dict"}',
            encoding="utf-8",
        )
        # Clear the cache so it re-reads.
        agent._load_tutor_progress._cache = None  # type: ignore[attr-defined]

        progress = agent._load_tutor_progress()
        assert progress["schema_version"] == 1
        assert isinstance(progress["concepts"], dict)
        # Clean up — write valid progress.
        agent._save_tutor_progress({"schema_version": 1, "concepts": {}})


class TestRelationshipWrappers:
    def test_add_and_list_people_use_agent_people_path(self):
        from research_paper_agent import agent
        from research_paper_agent.agent import add_person, list_people

        created = add_person(
            "Ada Lovelace",
            relationship_type="collaborator",
            aliases="Ada",
            context_note="Worked on analytical engines and design notes.",
            tags="computing",
            concepts="design",
        )

        assert created["status"] == "ok"
        assert agent.PEOPLE_PATH.exists()

        listed = list_people()
        assert listed["status"] == "ok"
        assert listed["count"] == 1
        assert listed["people"][0]["display_name"] == "Ada Lovelace"


# ---------------------------------------------------------------------------
# ADR 0072 Slice 2: Write gating, tool groups, diagnostics
# ---------------------------------------------------------------------------


class TestWriteGating:
    def test_fast_allows_explicit_memory_only(self):
        from research_paper_agent.agent_runtime.dynamic_context import write_allowed

        assert write_allowed("memory", "fast", "explicit") is True
        assert write_allowed("note", "fast", "explicit") is True
        assert write_allowed("profile", "fast", "explicit") is False
        assert write_allowed("graph", "fast", "explicit") is False
        assert write_allowed("projection", "fast", "explicit") is False

    def test_fast_blocks_candidate_signals(self):
        from research_paper_agent.agent_runtime.dynamic_context import write_allowed

        assert write_allowed("memory", "fast", "candidate") is False
        assert write_allowed("note", "fast", "candidate") is False

    def test_balanced_allows_explicit_and_high_confidence(self):
        from research_paper_agent.agent_runtime.dynamic_context import write_allowed

        assert write_allowed("memory", "balanced", "explicit") is True
        assert write_allowed("note", "balanced", "high_confidence") is True
        assert write_allowed("graph", "balanced", "high_confidence") is True

    def test_balanced_blocks_candidate(self):
        from research_paper_agent.agent_runtime.dynamic_context import write_allowed

        assert write_allowed("memory", "balanced", "candidate") is False

    def test_deep_allows_candidate_projection(self):
        from research_paper_agent.agent_runtime.dynamic_context import write_allowed

        assert write_allowed("projection", "deep", "candidate") is True
        assert write_allowed("note", "deep", "candidate") is False

    def test_deep_blocks_candidate_durable_prefs(self):
        from research_paper_agent.agent_runtime.dynamic_context import write_allowed

        # Durable preferences (memory, profile) still need explicit or high_confidence.
        assert write_allowed("memory", "deep", "candidate") is False
        assert write_allowed("profile", "deep", "candidate") is False

    def test_invalid_budget_falls_back_to_balanced(self):
        from research_paper_agent.agent_runtime.dynamic_context import write_allowed

        # Unknown budget → balanced rules apply.
        assert write_allowed("note", "invalid", "explicit") is True
        assert write_allowed("memory", "invalid", "candidate") is False


class TestToolGroups:
    def test_fast_tools_are_read_only(self):
        from research_paper_agent.agent_runtime.dynamic_context import _allowed_tool_names

        fast = _allowed_tool_names("fast")
        assert "list_papers" in fast
        assert "get_user_profile" in fast
        # Write and heavy tools excluded.
        assert "save_personal_note" not in fast
        assert "ingest_paper" not in fast
        assert "adaptive_grill" not in fast

    def test_balanced_includes_search_and_write(self):
        from research_paper_agent.agent_runtime.dynamic_context import _allowed_tool_names

        balanced = _allowed_tool_names("balanced")
        assert "search_evidence" in balanced
        assert "save_personal_note" in balanced
        # Heavy tools excluded.
        assert "ingest_paper" not in balanced
        assert "adaptive_grill" not in balanced

    def test_deep_includes_everything(self):
        from research_paper_agent.agent_runtime.dynamic_context import _allowed_tool_names

        deep = _allowed_tool_names("deep")
        assert "ingest_paper" in deep
        assert "adaptive_grill" in deep
        assert "rename_paper" in deep


# ---------------------------------------------------------------------------
# Tutor _next_concept tests (including prerequisite priority boost)
# ---------------------------------------------------------------------------


class TestNextConcept:
    def test_picks_weakest_first(self):
        from research_paper_agent.agent import _next_concept

        progress = {
            "concepts": {
                "embeddings": {"concept": "embeddings", "times_asked": 3, "times_correct": 2},
                "vector search": {"concept": "vector search", "times_asked": 3, "times_correct": 0},
            }
        }
        result = _next_concept(progress, ["research agents"], last_was_weak=False)
        assert result["concept"] == "vector search"  # 0/3 = weakest

    def test_alternates_to_strong(self):
        from research_paper_agent.agent import _next_concept

        progress = {
            "concepts": {
                "embeddings": {"concept": "embeddings", "times_asked": 3, "times_correct": 2},
                "vector search": {"concept": "vector search", "times_asked": 3, "times_correct": 0},
            }
        }
        result = _next_concept(progress, ["research agents"], last_was_weak=True)
        # last was weak, so should pick strong
        assert result["concept"] == "embeddings"

    def test_falls_back_to_interest(self):
        from research_paper_agent.agent import _next_concept

        progress = {"concepts": {}}
        result = _next_concept(progress, ["research agents"], last_was_weak=False)
        assert result["concept"] == "research agents"

    def test_prerequisite_boost_unmet(self):
        """When a candidate has an unmet prereq, boost the prereq to front."""
        from research_paper_agent.agent import _next_concept
        from research_paper_agent import concept_graph

        # Set up a dependency: vector search requires embeddings.
        concept_graph.link_prerequisite("vector search", "embeddings", "test.pdf")

        # Both are in progress, but embeddings is weaker — vector search
        # is the candidate. The boost should bring embeddings to the front.
        progress = {
            "concepts": {
                "embeddings": {"concept": "embeddings", "times_asked": 3, "times_correct": 0},
                "vector search": {"concept": "vector search", "times_asked": 3, "times_correct": 1},
            }
        }
        result = _next_concept(progress, ["research agents"], last_was_weak=False)
        # embeddings is the prereq of vector search; both are weak,
        # but embeddings gets boosted to the front of the weak list.
        assert result["concept"] == "embeddings"

    def test_prerequisite_never_taught_introduced(self):
        """When a concept's prereq has never been taught, introduce it."""
        from research_paper_agent.agent import _next_concept
        from research_paper_agent import concept_graph

        # Set up dependency but only the dependent concept has progress.
        concept_graph.link_prerequisite("vector search", "embeddings", "test.pdf")

        progress = {
            "concepts": {
                "vector search": {"concept": "vector search", "times_asked": 3, "times_correct": 0},
            }
        }
        result = _next_concept(progress, ["research agents"], last_was_weak=False)
        # embeddings is a prereq of vector search and has never been taught.
        assert result["concept"] == "embeddings"
        assert "never taught" in result["reason"]

    def test_prerequisite_already_mastered_no_boost(self):
        """When a prereq is already mastered (≥80%), no boost occurs."""
        from research_paper_agent.agent import _next_concept
        from research_paper_agent import concept_graph

        concept_graph.link_prerequisite("vector search", "embeddings", "test.pdf")

        progress = {
            "concepts": {
                "embeddings": {"concept": "embeddings", "times_asked": 5, "times_correct": 5},
                "vector search": {"concept": "vector search", "times_asked": 3, "times_correct": 0},
            }
        }
        result = _next_concept(progress, ["research agents"], last_was_weak=False)
        # embeddings is mastered (100%), so vector search is the weakest.
        assert result["concept"] == "vector search"


# ---------------------------------------------------------------------------
# Knowledge Self-Audit & Correction — integration tests
# ---------------------------------------------------------------------------


class TestKnowledgeSelfAudit:
    def test_returns_audit_structure(self, tmp_path: Path):
        """Audit returns the expected top-level keys even with no data."""
        from research_paper_agent import agent as agent_module

        # Point file paths at temp dir so we don't mutate real data.
        agent_module.USER_PROFILE_PATH = tmp_path / "profile.json"
        agent_module.CANDIDATE_SIGNALS_PATH = tmp_path / "candidate_signals.jsonl"
        agent_module.INTERACTION_LOG_PATH = tmp_path / "interaction_log.jsonl"
        agent_module.CONCEPT_GRAPH_PATH = tmp_path / "concept_graph.json"
        agent_module.TUTOR_PROGRESS_PATH = tmp_path / "tutor_progress.json"
        agent_module.PERSONAL_NOTES_PATH = tmp_path / "personal_notes.jsonl"

        # Create empty profile so the audit doesn't create the default.
        agent_module._save_user_profile(
            {"schema_version": 1, "updated_at": agent_module._now_iso(), "interests": []}
        )

        result = agent_module.knowledge_self_audit()

        for key in (
            "audit_generated_at",
            "confirmed",
            "candidate_signals",
            "concept_graph",
            "tutor_state",
            "notes",
            "interaction_summary",
            "correction_actions_available",
        ):
            assert key in result, f"Missing key: {key}"

        # Correction actions should list all 4 supported actions.
        actions = [a["action"] for a in result["correction_actions_available"]]
        assert "confirm_signal" in actions
        assert "reject_signal" in actions
        assert "downgrade_preference" in actions
        assert "suppress_concept" in actions

    def test_audit_with_profile_data(self, tmp_path: Path):
        """Audit surfaces confirmed preferences from the profile."""
        from research_paper_agent import agent as agent_module

        agent_module.USER_PROFILE_PATH = tmp_path / "profile.json"
        agent_module.CANDIDATE_SIGNALS_PATH = tmp_path / "candidate_signals.jsonl"
        agent_module.INTERACTION_LOG_PATH = tmp_path / "interaction_log.jsonl"
        agent_module.CONCEPT_GRAPH_PATH = tmp_path / "concept_graph.json"
        agent_module.TUTOR_PROGRESS_PATH = tmp_path / "tutor_progress.json"
        agent_module.PERSONAL_NOTES_PATH = tmp_path / "personal_notes.jsonl"

        agent_module._save_user_profile({
            "schema_version": 1,
            "updated_at": agent_module._now_iso(),
            "interests": [
                {"name": "knowledge graphs", "confidence": 0.9, "evidence": "Asked repeatedly about graph-based retrieval."}
            ],
            "style_preferences": [
                {"preference": "short answers", "source": "User said 'keep it short'"}
            ],
        })

        result = agent_module.knowledge_self_audit()
        confirmed = result["confirmed"]
        assert len(confirmed["interests"]) >= 1
        assert any("knowledge graphs" in str(i) for i in confirmed["interests"])


class TestSelfAuditCorrection:
    def test_rejects_unknown_action(self, tmp_path: Path):
        """Correction returns an error for unknown actions."""
        from research_paper_agent import agent as agent_module

        agent_module.USER_PROFILE_PATH = tmp_path / "profile.json"
        agent_module.CANDIDATE_SIGNALS_PATH = tmp_path / "candidate_signals.jsonl"

        agent_module._save_user_profile(
            {"schema_version": 1, "updated_at": agent_module._now_iso(), "interests": []}
        )

        result = agent_module.self_audit_correction("invalid_action", "target", "reason")
        assert result["status"] == "error"
        assert "Unknown action" in result["message"]

    def test_confirm_signal_adds_interest(self, tmp_path: Path):
        """confirm_signal with category 'interest' adds to the profile."""
        from research_paper_agent import agent as agent_module

        agent_module.USER_PROFILE_PATH = tmp_path / "profile.json"
        agent_module.CANDIDATE_SIGNALS_PATH = tmp_path / "candidate_signals.jsonl"

        agent_module._save_user_profile(
            {"schema_version": 1, "updated_at": agent_module._now_iso(), "interests": []}
        )

        result = agent_module.self_audit_correction(
            "confirm_signal", "interest:adversarial robustness", "Repeated grill interest"
        )
        assert result["status"] == "ok"

        profile = agent_module._load_user_profile()
        assert any(
            "adversarial robustness" in i.get("name", "")
            for i in profile.get("interests", [])
        )

    def test_confirm_signal_boosts_existing(self, tmp_path: Path):
        """confirm_signal on an existing interest raises its confidence."""
        from research_paper_agent import agent as agent_module

        agent_module.USER_PROFILE_PATH = tmp_path / "profile.json"
        agent_module.CANDIDATE_SIGNALS_PATH = tmp_path / "candidate_signals.jsonl"

        agent_module._save_user_profile({
            "schema_version": 1,
            "updated_at": agent_module._now_iso(),
            "interests": [{"name": "bayesian methods", "confidence": 0.5, "evidence": "initial"}],
        })

        result = agent_module.self_audit_correction(
            "confirm_signal", "interest:bayesian methods", "Stronger now"
        )
        assert result["status"] == "ok"

        profile = agent_module._load_user_profile()
        interest = next(
            i for i in profile.get("interests", []) if "bayesian methods" in i.get("name", "")
        )
        assert interest["confidence"] >= 0.65  # boosted by 0.2

    def test_downgrade_preference(self, tmp_path: Path):
        """downgrade_preference lowers confidence on a matching preference."""
        from research_paper_agent import agent as agent_module

        agent_module.USER_PROFILE_PATH = tmp_path / "profile.json"
        agent_module.CANDIDATE_SIGNALS_PATH = tmp_path / "candidate_signals.jsonl"

        agent_module._save_user_profile({
            "schema_version": 1,
            "updated_at": agent_module._now_iso(),
            "interests": [{"name": "outdated topic", "confidence": 0.9, "evidence": "old"}],
        })

        result = agent_module.self_audit_correction(
            "downgrade_preference", "outdated topic", "No longer relevant"
        )
        assert result["status"] == "ok"

        profile = agent_module._load_user_profile()
        interest = next(
            i for i in profile.get("interests", []) if "outdated topic" in i.get("name", "")
        )
        assert interest["confidence"] <= 0.65  # lowered by 0.3

    def test_reject_signal_logs_rejection(self, tmp_path: Path):
        """reject_signal writes a rejection entry to candidate signals."""
        from research_paper_agent import agent as agent_module

        agent_module.USER_PROFILE_PATH = tmp_path / "profile.json"
        agent_module.CANDIDATE_SIGNALS_PATH = tmp_path / "candidate_signals.jsonl"

        agent_module._save_user_profile(
            {"schema_version": 1, "updated_at": agent_module._now_iso(), "interests": []}
        )

        result = agent_module.self_audit_correction(
            "reject_signal", "verbose_explanations", "Prefers short answers"
        )
        assert result["status"] == "ok"
        assert agent_module.CANDIDATE_SIGNALS_PATH.exists()

    def test_suppress_concept(self, tmp_path: Path):
        """suppress_concept calls concept_graph.reject_concept."""
        from research_paper_agent import agent as agent_module

        agent_module.USER_PROFILE_PATH = tmp_path / "profile.json"
        agent_module.CONCEPT_GRAPH_PATH = tmp_path / "concept_graph.json"

        agent_module._save_user_profile(
            {"schema_version": 1, "updated_at": agent_module._now_iso(), "interests": []}
        )

        # Write a minimal concept graph with the concept to suppress.
        graph = {"schema_version": 2, "edges": {}, "dependencies": {}}
        agent_module.CONCEPT_GRAPH_PATH.write_text(json.dumps(graph))

        result = agent_module.self_audit_correction(
            "suppress_concept", "debunked_theory", "Paper retracted"
        )
        assert result["status"] == "ok"
