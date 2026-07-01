"""Tests for concept_graph — pure functions and graph operations."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# concept_graph tests
# ---------------------------------------------------------------------------


class TestTokenOverlap:
    def test_exact_match(self):
        from research_paper_agent.concept_graph import token_overlap

        assert token_overlap("research agents", "research agents")

    def test_shared_token(self):
        from research_paper_agent.concept_graph import token_overlap

        # "agents" is in both after tokenisation
        assert token_overlap("research agents", "agents and workflows")

    def test_no_overlap(self):
        from research_paper_agent.concept_graph import token_overlap

        assert not token_overlap("research agents", "banana farming")

    def test_short_words_ignored(self):
        from research_paper_agent.concept_graph import token_overlap

        # "ai" is 2 chars — filtered by _tokens()
        assert not token_overlap("ai research", "ai agents")

    def test_case_insensitive(self):
        from research_paper_agent.concept_graph import token_overlap

        assert token_overlap("Research Agents", "agents workflows")


class TestLinkAndLoad:
    def test_link_creates_edge(self):
        from research_paper_agent.concept_graph import link, load

        result = link("research agents", "retrieval", "paper_a.pdf", edge_type="ingest", similarity_score=1.0)
        assert result["type"] == "ingest"
        assert result["weight"] == 1.0
        graph = load()
        assert "research agents" in graph["edges"]
        assert "retrieval" in graph["edges"]["research agents"]

    def test_link_increments_weight(self):
        from research_paper_agent.concept_graph import link, load

        link("research agents", "retrieval", "paper_a.pdf", edge_type="ingest", similarity_score=1.0)
        result = link("research agents", "retrieval", "paper_b.pdf", edge_type="ingest", similarity_score=1.0)
        assert result["weight"] == 2.0
        assert result["source_papers"] == ["paper_a.pdf", "paper_b.pdf"]

    def test_link_promotes_edge_type(self):
        from research_paper_agent.concept_graph import link, load

        link("research agents", "retrieval", "paper_a.pdf", edge_type="ingest", similarity_score=1.0)
        result = link("research agents", "retrieval", "paper_a.pdf", edge_type="saved", similarity_score=1.0)
        assert result["type"] == "saved"

    def test_link_no_downgrade(self):
        from research_paper_agent.concept_graph import link

        link("research agents", "retrieval", "paper_a.pdf", edge_type="saved", similarity_score=1.0)
        result = link("research agents", "retrieval", "paper_a.pdf", edge_type="ingest", similarity_score=1.0)
        assert result["type"] == "saved"

    def test_link_empty_interest_skipped(self):
        from research_paper_agent.concept_graph import link

        result = link("", "retrieval", "paper_a.pdf")
        assert result.get("status") == "skipped"


class TestEdgeWeight:
    def test_ingest_bonus(self):
        from research_paper_agent.concept_graph import link, _edge_weight

        link("research agents", "retrieval", "paper_a.pdf", edge_type="ingest", similarity_score=1.0)
        from research_paper_agent.concept_graph import load

        edges = load()["edges"]
        w = _edge_weight(edges, "research agents", "retrieval")
        assert w == pytest.approx(1.0 * 0.5)

    def test_saved_bonus(self):
        from research_paper_agent.concept_graph import link, _edge_weight

        link("research agents", "retrieval", "paper_a.pdf", edge_type="saved", similarity_score=1.0)
        from research_paper_agent.concept_graph import load

        edges = load()["edges"]
        w = _edge_weight(edges, "research agents", "retrieval")
        assert w == pytest.approx(1.0 * 2.0)

    def test_no_edge_returns_zero(self):
        from research_paper_agent.concept_graph import _edge_weight

        assert _edge_weight({}, "nope", "nope") == 0.0


class TestRank:
    def test_ranks_by_graph_weight(self):
        from research_paper_agent.concept_graph import link, rank

        link("research agents", "retrieval", "paper_a.pdf", edge_type="saved", similarity_score=1.0)
        link("research agents", "benchmarks", "paper_b.pdf", edge_type="ingest", similarity_score=1.0)

        concepts = [{"name": "benchmarks"}, {"name": "retrieval"}, {"name": "unrelated"}]
        ranked = rank(["research agents"], concepts)

        assert ranked[0]["name"] == "retrieval"  # saved → weight 2.0
        assert ranked[1]["name"] == "benchmarks"  # ingest → weight 0.5
        assert ranked[2]["name"] == "unrelated"  # no edge → 0
        assert ranked[0]["graph_weight"] > ranked[1]["graph_weight"]

    def test_rank_empty_concepts(self):
        from research_paper_agent.concept_graph import rank

        assert rank(["research agents"], []) == []


class TestAnnotate:
    def test_annotate_labels(self):
        from research_paper_agent.concept_graph import link, annotate

        link("research agents", "retrieval", "paper_a.pdf", edge_type="saved", similarity_score=1.0)
        link("research agents", "benchmarks", "paper_b.pdf", edge_type="ingest", similarity_score=1.0)

        brief = {
            "source": "paper_a.pdf",
            "top_concepts": [{"name": "retrieval"}, {"name": "benchmarks"}, {"name": "unrelated"}],
        }
        annotated = annotate(brief, ["research agents"])

        concepts = annotated["top_concepts"]
        assert concepts[0]["interest_match"] == "high"  # saved → 2.0
        assert concepts[1]["interest_match"] == "medium"  # ingest → 0.5
        assert concepts[2]["interest_match"] == "low"  # no edge


class TestDecay:
    def test_decay_removes_stale_engaged(self):
        from research_paper_agent.concept_graph import link, decay, load

        link("research agents", "old_topic", "paper_a.pdf", edge_type="engaged", similarity_score=1.0)
        # Artificially age the edge.
        graph = load()
        old = "1900-01-01T00:00:00+00:00"
        graph["edges"]["research agents"]["old_topic"]["last_engaged_at"] = old
        from research_paper_agent.concept_graph import _save

        _save(graph)

        result = decay()
        assert result["removed_edges"] == 1

    def test_decay_preserves_saved(self):
        from research_paper_agent.concept_graph import link, decay, load

        link("research agents", "forever", "paper_a.pdf", edge_type="saved", similarity_score=1.0)
        graph = load()
        graph["edges"]["research agents"]["forever"]["last_engaged_at"] = (
            "1900-01-01T00:00:00+00:00"
        )
        from research_paper_agent.concept_graph import _save

        _save(graph)

        result = decay()
        assert result["removed_edges"] == 0
        assert "forever" in load()["edges"]["research agents"]


class TestGetConceptGraph:
    def test_returns_summary(self):
        from research_paper_agent.concept_graph import link, get_concept_graph

        link("research agents", "retrieval", "paper_a.pdf", edge_type="saved", similarity_score=1.0)
        summary = get_concept_graph()
        assert summary["edge_count"] == 1
        assert summary["edges"][0]["interest"] == "research agents"
        assert summary["edges"][0]["type"] == "saved"

    def test_includes_dependencies(self):
        from research_paper_agent.concept_graph import link_prerequisite, get_concept_graph

        link_prerequisite("vector search", "embeddings", "paper_a.pdf")
        summary = get_concept_graph()
        assert summary["dependency_count"] == 1
        assert summary["dependencies"][0]["concept"] == "vector search"
        assert summary["dependencies"][0]["prerequisite"] == "embeddings"


# ---------------------------------------------------------------------------
# Prerequisite hint tests
# ---------------------------------------------------------------------------


class TestLinkPrerequisite:
    def test_creates_prerequisite_edge(self):
        from research_paper_agent.concept_graph import link_prerequisite, load

        result = link_prerequisite("vector search", "embeddings", "paper_a.pdf")
        assert result["concept"] == "vector search"
        assert result["prerequisite"] == "embeddings"
        graph = load()
        assert "vector search" in graph["dependencies"]
        assert "embeddings" in graph["dependencies"]["vector search"]

    def test_skips_self_reference(self):
        from research_paper_agent.concept_graph import link_prerequisite

        result = link_prerequisite("embeddings", "embeddings", "paper_a.pdf")
        assert result.get("status") == "skipped"

    def test_skips_empty_concept(self):
        from research_paper_agent.concept_graph import link_prerequisite

        result = link_prerequisite("", "embeddings", "paper_a.pdf")
        assert result.get("status") == "skipped"

    def test_appends_second_source_paper(self):
        from research_paper_agent.concept_graph import link_prerequisite

        link_prerequisite("vector search", "embeddings", "paper_a.pdf")
        result = link_prerequisite("vector search", "embeddings", "paper_b.pdf")
        assert result["source_papers"] == ["paper_a.pdf", "paper_b.pdf"]

    def test_multiple_prerequisites_per_concept(self):
        from research_paper_agent.concept_graph import link_prerequisite, load

        link_prerequisite("transformer", "attention", "paper_a.pdf")
        link_prerequisite("transformer", "neural networks", "paper_a.pdf")
        graph = load()
        deps = graph["dependencies"]["transformer"]
        assert "attention" in deps
        assert "neural networks" in deps


class TestGetPrerequisites:
    def test_returns_list(self):
        from research_paper_agent.concept_graph import link_prerequisite, get_prerequisites

        link_prerequisite("vector search", "embeddings", "paper_a.pdf")
        link_prerequisite("vector search", "nearest neighbor", "paper_a.pdf")
        prereqs = get_prerequisites("vector search")
        assert "embeddings" in prereqs
        assert "nearest neighbor" in prereqs

    def test_empty_for_unknown_concept(self):
        from research_paper_agent.concept_graph import get_prerequisites

        assert get_prerequisites("nonexistent") == []

    def test_empty_when_no_dependencies_exist(self):
        from research_paper_agent.concept_graph import get_prerequisites, load

        # ensure fresh state
        graph = load()
        graph.pop("dependencies", None)
        from research_paper_agent.concept_graph import _save
        _save(graph)
        assert get_prerequisites("anything") == []
