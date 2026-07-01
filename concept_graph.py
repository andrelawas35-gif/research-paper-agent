"""Bipartite concept graph connecting User Interests to Paper Concepts.

Stored in ``user_model/concept_graph.json``. Edges carry a type (ingest,
engaged, saved), a weight, source-paper references, and a last-engaged
timestamp. The graph drives personalised grill-question ranking and
paper-brief annotations.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_APP_DIR = Path(__file__).resolve().parent
_USER_MODEL_DIR = _APP_DIR / "user_model"
CONCEPT_GRAPH_PATH = _USER_MODEL_DIR / "concept_graph.json"

_EDGE_TYPES = frozenset({"ingest", "engaged", "saved", "rejected", "note"})

# In-memory cache — invalidated on every _save().
_graph_cache: dict[str, Any] | None = None

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_TYPE_BONUS = {"ingest": 0.5, "engaged": 1.0, "saved": 2.0, "rejected": -1.0, "note": 0.8}

# Type promotion rank — higher beats lower.  Rejected is below everything;
# note edges sit between ingest (passive) and engaged (active).
_TYPE_RANK = {"rejected": -1, "ingest": 0, "note": 1, "engaged": 2, "saved": 3}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_graph() -> dict[str, Any]:
    return {"schema_version": 2, "edges": {}, "dependencies": {}}


def _tokens(text: str) -> set[str]:
    """Tokenise a phrase into a set of meaningful lowercase words."""
    return {word for word in text.lower().split() if len(word) > 2}


def _similarity(a: str, b: str) -> float:
    """Fuzzy similarity between two phrases using prefix-matched Jaccard.

    Catches "agent"↔"agents", "model"↔"modeling", "bayesian"↔"bayes"
    without new dependencies.  Returns a float in [0, 1].

    The function signature is deliberately swappable — replace the body
    with an embedding-based cosine similarity when needed.
    """
    tokens_a = _tokens(a)
    tokens_b = _tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0

    # Prefix matching: two tokens match if they share a 4-char prefix.
    # This handles simple morphological variants without a stemmer.
    def _prefixes(ts: set[str]) -> set[str]:
        return {t[:4] for t in ts}

    pre_a = _prefixes(tokens_a)
    pre_b = _prefixes(tokens_b)

    intersection = len(pre_a & pre_b)
    union = len(pre_a | pre_b)
    if union == 0:
        return 0.0

    jaccard = intersection / union

    # Bonus for exact token matches (stronger signal than prefix-only).
    exact = len(tokens_a & tokens_b)
    if exact > 0:
        jaccard = min(1.0, jaccard + 0.15 * exact)

    return round(jaccard, 4)


def _edge_weight(
    edges: dict[str, dict[str, dict[str, Any]]],
    interest_key: str,
    concept_key: str,
) -> float:
    """Return the scored weight of a single interest→concept edge, or 0.0."""
    edge = edges.get(interest_key, {}).get(concept_key)
    if edge is None:
        return 0.0
    return edge.get("weight", 1.0) * _TYPE_BONUS.get(edge.get("type", "ingest"), 0.5)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def load() -> dict[str, Any]:
    """Load the concept graph, returning defaults when the file is missing."""
    global _graph_cache
    if _graph_cache is not None:
        return _graph_cache
    _USER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not CONCEPT_GRAPH_PATH.exists():
        graph = _default_graph()
        CONCEPT_GRAPH_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        _graph_cache = graph
        return graph
    try:
        graph = json.loads(CONCEPT_GRAPH_PATH.read_text(encoding="utf-8"))
        _graph_cache = graph
        return graph
    except json.JSONDecodeError:
        graph = _default_graph()
        graph["recovery_note"] = "concept_graph.json was unreadable and defaults were restored."
        CONCEPT_GRAPH_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        _graph_cache = graph
        return graph


def _save(graph: dict[str, Any]) -> None:
    global _graph_cache
    _USER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    graph["updated_at"] = _now_iso()
    _rebuild_paper_links(graph)
    CONCEPT_GRAPH_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    _graph_cache = graph


def link(
    interest: str,
    concept: str,
    source_paper: str,
    edge_type: str = "ingest",
    similarity_score: float | None = None,
) -> dict[str, Any]:
    """Create or strengthen a directed edge from an interest to a concept.

    Parameters
    ----------
    interest:
        Normalised interest name (lowercased for keying).
    concept:
        Normalised concept name (lowercased for keying).
    source_paper:
        The paper filename this edge came from.
    edge_type:
        One of ``"ingest"`` (passive keyword match), ``"engaged"`` (active
        grill answer), ``"saved"`` (explicit user save), or ``"rejected"``
        (explicit user dismissal).
    similarity_score:
        Optional pre-computed similarity; if None, computed via ``_similarity``.

    Returns
    -------
    The updated edge record.
    """
    if edge_type not in _EDGE_TYPES:
        raise ValueError(f"Unknown edge_type {edge_type!r}; use one of {sorted(_EDGE_TYPES)}")

    graph = load()
    interest_key = interest.strip().lower()
    concept_key = concept.strip().lower()

    if not interest_key or not concept_key:
        return {"status": "skipped", "reason": "empty interest or concept"}

    graph.setdefault("edges", {})
    graph["edges"].setdefault(interest_key, {})

    edge = graph["edges"][interest_key].get(concept_key)
    now = _now_iso()

    if similarity_score is None:
        similarity_score = _similarity(interest, concept)

    if edge is None:
        edge = {
            "interest": interest_key,
            "concept": concept_key,
            "type": edge_type,
            "weight": round(similarity_score, 4),
            "source_papers": [source_paper],
            "sources": [{"source_type": "paper", "source_id": source_paper}],
            "created_at": now,
            "last_engaged_at": now if edge_type in {"engaged", "saved", "note"} else None,
        }
    else:
        # Promote edge type: saved > engaged > note > ingest > rejected.
        current_rank = _TYPE_RANK.get(edge.get("type", "ingest"), 0)
        new_rank = _TYPE_RANK.get(edge_type, 0)
        if edge.get("type") == "rejected" and edge_type != "saved":
            pass  # rejection is sticky — only saved can override
        elif new_rank > current_rank:
            edge["type"] = edge_type

        edge["weight"] = round(edge.get("weight", similarity_score) + similarity_score, 4)
        if source_paper not in edge.setdefault("source_papers", []):
            edge["source_papers"].append(source_paper)
        # ADR 0038: append typed source reference.
        source_entry = {"source_type": "paper", "source_id": source_paper}
        existing_sources = edge.setdefault("sources", [])
        if source_entry not in existing_sources:
            existing_sources.append(source_entry)
        if edge_type in {"engaged", "saved", "note"}:
            edge["last_engaged_at"] = now

    graph["edges"][interest_key][concept_key] = edge
    _save(graph)
    return edge


def decay() -> dict[str, Any]:
    """Decay stale edges.

    - Ingest edges with weight < 0.5 and no activity for 60 days → removed.
    - Ingest edges with no promotion for 90 days → removed.
    - Note edges: stable for 90 days, lose half weight after 180 days inactivity,
      removed after 365 days (ADR 0040).
    - Engaged edges lose half weight after 30 days, removed after 60 days.
    - Saved edges never decay.
    - Rejected edges never decay.
    """
    graph = load()
    now = datetime.now(timezone.utc)
    removed = 0
    decayed = 0

    for interest_key in list(graph.get("edges", {})):
        concept_edges = graph["edges"].get(interest_key, {})
        for concept_key in list(concept_edges):
            edge = concept_edges[concept_key]
            edge_type = edge.get("type", "ingest")

            # Saved and rejected edges are immortal.
            if edge_type in {"saved", "rejected"}:
                continue

            last = edge.get("last_engaged_at") or edge.get("created_at")
            if not last:
                continue

            try:
                last_dt = datetime.fromisoformat(last)
            except (ValueError, TypeError):
                continue

            days = (now - last_dt).days

            if edge_type == "ingest":
                weight = edge.get("weight", 1.0)
                if weight < 0.5 and days >= 60:
                    del concept_edges[concept_key]
                    removed += 1
                elif days >= 90:
                    del concept_edges[concept_key]
                    removed += 1
            elif edge_type == "note":
                # ADR 0040: note signals decay slowly.
                if days >= 365:
                    del concept_edges[concept_key]
                    removed += 1
                elif days >= 180:
                    edge["weight"] = round(max(0.1, edge.get("weight", 1.0) * 0.5), 4)
                    decayed += 1
                # 0–90 days: stable, no decay.
            elif edge_type == "engaged":
                if days >= 60:
                    del concept_edges[concept_key]
                    removed += 1
                elif days >= 30:
                    edge["weight"] = round(max(0.1, edge.get("weight", 1.0) * 0.5), 4)
                    decayed += 1

        if not concept_edges:
            del graph["edges"][interest_key]

    if removed or decayed:
        _save(graph)

    return {"decayed_edges": decayed, "removed_edges": removed}


def refresh_note_signal(note_id: str) -> dict[str, Any]:
    """Refresh the ``last_engaged_at`` timestamp on all note-type edges
    linked to *note_id* so they don't decay prematurely (ADR 0040).

    Call this from note edit, search, link, grill, or tutor operations.
    """
    graph = load()
    now = _now_iso()
    refreshed = 0
    for interest_key in graph.get("edges", {}):
        for concept_key, edge in graph["edges"][interest_key].items():
            if edge.get("type") != "note":
                continue
            sources = edge.get("source_papers", [])
            if note_id in sources:
                edge["last_engaged_at"] = now
                refreshed += 1
    if refreshed:
        _save(graph)
    return {"refreshed_edges": refreshed, "note_id": note_id}


def rank(
    user_interests: list[str],
    concepts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score concepts by how strongly they connect to the user's interests.

    Rejected edges contribute *negative* weight, pushing dismissed concepts
    below even unconnected ones (weight 0).

    Parameters
    ----------
    user_interests:
        Interest names from the user profile (e.g. ``["research agents",
        "self-improving local assistants"]``).
    concepts:
        Concept dicts (must have a ``"name"`` key) — typically from
        ``paper_brief`` or ``list_concepts`` output.

    Returns
    -------
    The same concept list with a ``graph_weight`` field added, sorted
    highest-weight first.  Concepts with no graph match get weight 0.
    Concepts with rejected edges get negative weight.
    """
    decay()
    edges = load().get("edges", {})

    for concept in concepts:
        concept_key = concept.get("name", "").strip().lower()
        total = 0.0
        for interest in user_interests:
            interest_key = interest.strip().lower()
            edge = edges.get(interest_key, {}).get(concept_key)
            if edge is None:
                continue
            w = _edge_weight(edges, interest_key, concept_key)
            total += w
        concept["graph_weight"] = round(total, 4)

    concepts.sort(key=lambda c: c.get("graph_weight", 0), reverse=True)
    return concepts


def annotate(
    brief: dict[str, Any],
    user_interests: list[str],
) -> dict[str, Any]:
    """Add ``interest_match`` labels to every concept in a paper brief.

    Labels are ``"high"`` (graph weight ≥ 2), ``"medium"`` (≥ 0.5),
    ``"low"`` (≥ 0), or ``"rejected"`` (< 0 — user has dismissed this).

    Parameters
    ----------
    brief:
        A single brief dict (from ``paper_brief`` output).
    user_interests:
        Interest names from the user profile.

    Returns
    -------
    The same brief with ``interest_match`` added to each concept entry.
    """
    decay()
    edges = load().get("edges", {})

    for bucket_key in ("top_concepts", "concepts"):
        for concept in brief.get(bucket_key, []):
            concept_key = concept.get("name", "").strip().lower()
            total = 0.0
            for interest in user_interests:
                interest_key = interest.strip().lower()
                edge = edges.get(interest_key, {}).get(concept_key)
                if edge is None:
                    continue
                total += _edge_weight(edges, interest_key, concept_key)

            if total < 0:
                concept["interest_match"] = "rejected"
            elif total >= 2.0:
                concept["interest_match"] = "high"
            elif total >= 0.5:
                concept["interest_match"] = "medium"
            else:
                concept["interest_match"] = "low"

    return brief


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------


def token_overlap(interest: str, concept: str, min_shared: int = 1) -> bool:
    """Return True when an interest and concept share enough meaningful tokens.

    Uses token-set intersection instead of naive substring matching.
    "interest = \"research agents\"" and "concept = \"agent-building workflows\""
    share the token ``"agent"`` → True.
    """
    return len(_tokens(interest) & _tokens(concept)) >= min_shared


# ---------------------------------------------------------------------------
# Prerequisite hints — soft concept→concept edges for curriculum sequencing
# ---------------------------------------------------------------------------


def link_prerequisite(
    concept: str,
    prerequisite: str,
    source_paper: str,
) -> dict[str, Any]:
    """Record a soft pedagogical hint: *prerequisite* should be taught before *concept*.

    These are advisory, not blocking.  The tutor uses them as a priority-boost
    signal, never as a hard gate.  Cycles are safe because only one hop is
    ever inspected at a time.

    Parameters
    ----------
    concept:
        The concept that depends on the prerequisite (e.g. "vector search").
    prerequisite:
        The concept that should come first (e.g. "embeddings").
    source_paper:
        The paper filename this relationship was inferred from.

    Returns
    -------
    The updated prerequisite record.
    """
    graph = load()
    concept_key = concept.strip().lower()
    prereq_key = prerequisite.strip().lower()

    if not concept_key or not prereq_key or concept_key == prereq_key:
        return {"status": "skipped", "reason": "empty or self-referential prerequisite"}

    graph.setdefault("dependencies", {})
    graph["dependencies"].setdefault(concept_key, {})

    edge = graph["dependencies"][concept_key].get(prereq_key)
    now = _now_iso()

    if edge is None:
        edge = {
            "concept": concept_key,
            "prerequisite": prereq_key,
            "source_papers": [source_paper],
            "created_at": now,
        }
    else:
        if source_paper not in edge.setdefault("source_papers", []):
            edge["source_papers"].append(source_paper)

    graph["dependencies"][concept_key][prereq_key] = edge
    _save(graph)
    return edge


def get_prerequisites(concept: str) -> list[str]:
    """Return the prerequisite concept keys for *concept* (one-hop lookahead).

    Returns an empty list when the concept has no recorded prerequisites or
    when the concept is unknown to the dependency graph.
    """
    graph = load()
    deps = graph.get("dependencies", {})
    concept_key = concept.strip().lower()
    prereq_map = deps.get(concept_key, {})
    return sorted(prereq_map.keys())


def get_concept_graph() -> dict[str, Any]:
    """Inspect the local concept graph (interest-to-concept edges with weights)."""
    decay()
    graph = load()
    edges = graph.get("edges", {})
    deps = graph.get("dependencies", {})
    paper_links = graph.get("paper_links", {})
    summary = []
    for interest_key, concept_edges in sorted(edges.items()):
        for concept_key, edge in sorted(concept_edges.items()):
            summary.append(
                {
                    "interest": edge.get("interest", interest_key),
                    "concept": edge.get("concept", concept_key),
                    "type": edge.get("type"),
                    "weight": edge.get("weight"),
                    "source_papers": edge.get("source_papers", []),
                    "last_engaged_at": edge.get("last_engaged_at"),
                }
            )

    dep_summary = []
    for concept_key, prereqs in sorted(deps.items()):
        for prereq_key, edge in sorted(prereqs.items()):
            dep_summary.append({
                "concept": concept_key,
                "prerequisite": prereq_key,
                "source_papers": edge.get("source_papers", []),
            })

    return {
        "graph_path": str(CONCEPT_GRAPH_PATH),
        "edge_count": len(summary),
        "edges": summary,
        "dependency_count": len(dep_summary),
        "dependencies": dep_summary,
        "paper_link_count": len(paper_links),
        "paper_links": paper_links,
    }


def _rebuild_paper_links(graph: dict[str, Any]) -> None:
    """Rebuild the ``paper_links`` index from shared concept edges.

    Two papers are linked when they appear together in at least one edge's
    ``source_papers`` list.  The link records the count of shared concepts
    and which interests connect them.  Called automatically by ``_save()``.
    """
    links: dict[str, dict[str, dict[str, Any]]] = {}

    for interest_key, concept_edges in graph.get("edges", {}).items():
        for _concept_key, edge in concept_edges.items():
            papers = edge.get("source_papers", [])
            if len(papers) < 2:
                continue
            for i, p1 in enumerate(papers):
                for p2 in papers[i + 1 :]:
                    if p1 == p2:
                        continue
                    links.setdefault(p1, {})
                    links.setdefault(p2, {})
                    # p1 → p2
                    if p2 not in links[p1]:
                        links[p1][p2] = {
                            "paper": p2,
                            "shared_concepts": 0,
                            "shared_interests": [],
                        }
                    links[p1][p2]["shared_concepts"] += 1
                    if interest_key not in links[p1][p2]["shared_interests"]:
                        links[p1][p2]["shared_interests"].append(interest_key)
                    # p2 → p1
                    if p1 not in links[p2]:
                        links[p2][p1] = {
                            "paper": p1,
                            "shared_concepts": 0,
                            "shared_interests": [],
                        }
                    links[p2][p1]["shared_concepts"] += 1
                    if interest_key not in links[p2][p1]["shared_interests"]:
                        links[p2][p1]["shared_interests"].append(interest_key)

    graph["paper_links"] = links


def suggest_concept_merges(threshold: float = 0.75) -> dict[str, Any]:
    """Suggest near-duplicate concepts for user approval (ADR 0022).

    Unlike ``merge_similar_concepts``, this is **non-destructive** — it
    returns merge candidates but does not modify the graph.  The user must
    approve each merge explicitly before calling ``merge_similar_concepts``.

    Parameters
    ----------
    threshold:
        Similarity threshold for suggesting a merge (default 0.75, lower
        than the destructive merge threshold to catch more candidates).

    Returns
    -------
    A dict with ``suggestions`` — a list of {concept_a, concept_b, similarity,
    shared_papers, recommendation}.
    """
    graph = load()
    edges = graph.get("edges", {})
    suggestions: list[dict[str, Any]] = []

    all_concepts: set[str] = set()
    for concept_edges in edges.values():
        all_concepts.update(concept_edges.keys())

    concept_list = sorted(all_concepts)
    seen_pairs: set[tuple[str, str]] = set()

    for i, ca in enumerate(concept_list):
        for cb in concept_list[i + 1:]:
            pair = (ca, cb)
            if pair in seen_pairs:
                continue
            sim = _similarity(ca, cb)
            if sim < threshold:
                continue
            seen_pairs.add(pair)

            # Collect shared source papers and interests.
            shared_papers: set[str] = set()
            shared_interests: set[str] = set()
            for interest_key, concept_edges in edges.items():
                if ca in concept_edges and cb in concept_edges:
                    shared_interests.add(interest_key)
                    shared_papers.update(concept_edges[ca].get("source_papers", []))
                    shared_papers.update(concept_edges[cb].get("source_papers", []))

            confidence = "high" if sim >= 0.85 else "medium" if sim >= 0.75 else "low"
            suggestions.append({
                "concept_a": ca,
                "concept_b": cb,
                "similarity": round(sim, 4),
                "shared_papers": sorted(shared_papers)[:5],
                "shared_interests": sorted(shared_interests)[:5],
                "recommendation": (
                    f"Strong match ({confidence} confidence). "
                    f"Reply 'merge {ca} and {cb}' to confirm, or ignore to keep separate."
                ),
            })

    suggestions.sort(key=lambda s: s["similarity"], reverse=True)
    return {
        "status": "ok",
        "suggestion_count": len(suggestions),
        "suggestions": suggestions[:10],
    }


def merge_similar_concepts(threshold: float = 0.85) -> dict[str, Any]:
    """Merge near-duplicate concept keys across the graph.

    Compares all concept keys pairwise using ``_similarity``.  When
    similarity ≥ *threshold*, the concepts are merged: weights sum,
    source_papers are unioned, and the highest edge type survives.
    The surviving key is the one with the most source_papers.

    This is on-demand and deliberately destructive — call it explicitly
    after batch ingests or when the graph feels scattered.
    """
    graph = load()
    edges = graph.get("edges", {})
    if not edges:
        return {"status": "ok", "merged": 0, "message": "Graph is empty; nothing to merge."}

    # Collect all concept keys grouped by interest.
    interest_concepts: dict[str, list[str]] = {}
    for interest_key, concept_edges in edges.items():
        interest_concepts[interest_key] = list(concept_edges.keys())

    merges = []
    for interest_key, concept_keys in interest_concepts.items():
        merged_in_interest: set[str] = set()
        for i, ck_a in enumerate(concept_keys):
            if ck_a in merged_in_interest:
                continue
            for ck_b in concept_keys[i + 1 :]:
                if ck_b in merged_in_interest:
                    continue
                sim = _similarity(ck_a, ck_b)
                if sim < threshold:
                    continue

                # Decide survivor: keep the one with more source_papers.
                edge_a = edges[interest_key].get(ck_a, {})
                edge_b = edges[interest_key].get(ck_b, {})
                papers_a = len(edge_a.get("source_papers", []))
                papers_b = len(edge_b.get("source_papers", []))

                if papers_b > papers_a:
                    survivor_key, absorbed_key = ck_b, ck_a
                    survivor, absorbed = edge_b, edge_a
                else:
                    survivor_key, absorbed_key = ck_a, ck_b
                    survivor, absorbed = edge_a, edge_b

                # Merge: sum weights, union source_papers, keep highest type.
                survivor["weight"] = round(
                    survivor.get("weight", 0) + absorbed.get("weight", 0), 4
                )
                for sp in absorbed.get("source_papers", []):
                    if sp not in survivor.setdefault("source_papers", []):
                        survivor["source_papers"].append(sp)
                if _TYPE_RANK.get(absorbed.get("type", "ingest"), 0) > _TYPE_RANK.get(
                    survivor.get("type", "ingest"), 0
                ):
                    survivor["type"] = absorbed["type"]

                del edges[interest_key][absorbed_key]
                merged_in_interest.add(absorbed_key)
                merges.append(
                    {
                        "interest": interest_key,
                        "survivor": survivor_key,
                        "absorbed": absorbed_key,
                        "similarity": round(sim, 4),
                    }
                )

        # Clean up empty interest keys.
        if not edges.get(interest_key):
            del edges[interest_key]

    if merges:
        _save(graph)

    return {
        "status": "ok",
        "merged": len(merges),
        "merges": merges,
    }


def rename_source_paper(old_name: str, new_name: str) -> dict[str, Any]:
    """Migrate all graph references from *old_name* to *new_name*.

    Updates ``source_papers`` lists in both interest→concept edges and
    dependency edges.  Returns counts of edges touched so callers can
    verify completeness.
    """
    graph = load()
    edge_updates = 0
    dep_updates = 0

    # --- interest → concept edges ---
    for interest_key in graph.get("edges", {}):
        for concept_key, edge in graph["edges"][interest_key].items():
            papers = edge.get("source_papers", [])
            if old_name in papers:
                papers[papers.index(old_name)] = new_name
                edge_updates += 1

    # --- dependency edges ---
    for concept_key in graph.get("dependencies", {}):
        for prereq_key, edge in graph["dependencies"][concept_key].items():
            papers = edge.get("source_papers", [])
            if old_name in papers:
                papers[papers.index(old_name)] = new_name
                dep_updates += 1

    if edge_updates or dep_updates:
        _save(graph)

    return {
        "status": "ok",
        "old_name": old_name,
        "new_name": new_name,
        "edge_updates": edge_updates,
        "dependency_updates": dep_updates,
    }


def remove_source_paper(source_name: str) -> dict[str, Any]:
    """Remove all graph references to *source_name*.

    Strips the name from ``source_papers`` lists in both edge types.
    Edges whose ``source_papers`` list becomes empty are left in place
    (their weight may still be relevant from other sources).
    """
    graph = load()
    edge_removals = 0
    dep_removals = 0

    for interest_key in graph.get("edges", {}):
        for concept_key, edge in graph["edges"][interest_key].items():
            papers = edge.get("source_papers", [])
            if source_name in papers:
                papers.remove(source_name)
                edge_removals += 1

    for concept_key in graph.get("dependencies", {}):
        for prereq_key, edge in graph["dependencies"][concept_key].items():
            papers = edge.get("source_papers", [])
            if source_name in papers:
                papers.remove(source_name)
                dep_removals += 1

    if edge_removals or dep_removals:
        _save(graph)

    return {
        "status": "ok",
        "source_name": source_name,
        "edge_removals": edge_removals,
        "dependency_removals": dep_removals,
    }


def reject_concept(concept: str, reason: str = "") -> dict[str, Any]:
    """Mark a concept as rejected so it is suppressed in graph ranking.

    Sets the edge type to ``"rejected"`` for all interest→concept edges
    matching *concept*.  Rejected edges carry a negative weight bonus and
    are never decayed — the rejection is durable until explicitly reversed
    (e.g. by a subsequent ``link(…, edge_type="saved")`` call).

    Parameters
    ----------
    concept:
        The concept name to suppress (case-insensitive, token-matched).
    reason:
        Human-readable reason for the rejection (stored on the edge).

    Returns
    -------
    A dict with ``rejected_edges`` count and the concept key.
    """
    graph = load()
    concept_key = concept.strip().lower()
    now = _now_iso()
    rejected = 0

    for interest_key in graph.get("edges", {}):
        for edge_key in list(graph["edges"][interest_key]):
            # Token-match: accept partial overlap so "outdated_method"
            # matches edges whose concept key contains "outdated" or "method".
            if concept_key in edge_key or any(
                token in edge_key for token in concept_key.split()
            ):
                edge = graph["edges"][interest_key][edge_key]
                edge["type"] = "rejected"
                edge["weight"] = round(edge.get("weight", 1.0) * 0.1, 4)
                edge["rejected_at"] = now
                edge["rejection_reason"] = reason[:500]
                rejected += 1

    if rejected:
        _save(graph)

    return {
        "status": "ok",
        "concept_key": concept_key,
        "rejected_edges": rejected,
        "reason": reason[:500],
    }
