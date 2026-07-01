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
