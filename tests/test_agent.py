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
