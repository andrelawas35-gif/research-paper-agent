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

_EDGE_TYPES = frozenset({"ingest", "engaged", "saved"})

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_graph() -> dict[str, Any]:
    return {"schema_version": 1, "edges": {}}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def load() -> dict[str, Any]:
    """Load the concept graph, returning defaults when the file is missing."""
    _USER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not CONCEPT_GRAPH_PATH.exists():
        graph = _default_graph()
        CONCEPT_GRAPH_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        return graph
    try:
        return json.loads(CONCEPT_GRAPH_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        graph = _default_graph()
        graph["recovery_note"] = "concept_graph.json was unreadable and defaults were restored."
        CONCEPT_GRAPH_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        return graph


def _save(graph: dict[str, Any]) -> None:
    _USER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    graph["updated_at"] = _now_iso()
    CONCEPT_GRAPH_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")


def link(
    interest: str,
    concept: str,
    source_paper: str,
    edge_type: str = "ingest",
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
        grill answer), or ``"saved"`` (explicit user save).

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

    if edge is None:
        edge = {
            "interest": interest_key,
            "concept": concept_key,
            "type": edge_type,
            "weight": 1.0,
            "source_papers": [source_paper],
            "created_at": now,
            "last_engaged_at": now if edge_type in {"engaged", "saved"} else None,
        }
    else:
        # Promote edge type: saved > engaged > ingest
        type_rank = {"ingest": 0, "engaged": 1, "saved": 2}
        if type_rank.get(edge_type, 0) > type_rank.get(edge.get("type", "ingest"), 0):
            edge["type"] = edge_type

        edge["weight"] = round(edge.get("weight", 1.0) + 1.0, 2)
        if source_paper not in edge.setdefault("source_papers", []):
            edge["source_papers"].append(source_paper)
        if edge_type in {"engaged", "saved"}:
            edge["last_engaged_at"] = now

    graph["edges"][interest_key][concept_key] = edge
    _save(graph)
    return edge


def decay() -> dict[str, Any]:
    """Decay engaged edges that haven't been touched recently.

    Engaged edges lose half their weight after 30 days of inactivity and
    are removed entirely after 60 days.  Ingest and saved edges are never
    decayed.
    """
    graph = load()
    now = datetime.now(timezone.utc)
    removed = 0
    decayed = 0

    for interest_key in list(graph.get("edges", {})):
        concept_edges = graph["edges"].get(interest_key, {})
        for concept_key in list(concept_edges):
            edge = concept_edges[concept_key]
            if edge.get("type") != "engaged":
                continue

            last = edge.get("last_engaged_at")
            if not last:
                continue

            try:
                last_dt = datetime.fromisoformat(last)
            except (ValueError, TypeError):
                continue

            days = (now - last_dt).days
            if days >= 60:
                del concept_edges[concept_key]
                removed += 1
            elif days >= 30:
                edge["weight"] = round(max(0.1, edge.get("weight", 1.0) * 0.5), 2)
                decayed += 1

        if not concept_edges:
            del graph["edges"][interest_key]

    if removed or decayed:
        _save(graph)

    return {"decayed_edges": decayed, "removed_edges": removed}


def rank(
    user_interests: list[str],
    concepts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score concepts by how strongly they connect to the user's interests.

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
    """
    graph = load()
    edges = graph.get("edges", {})

    for concept in concepts:
        concept_key = concept.get("name", "").strip().lower()
        total = 0.0
        for interest in user_interests:
            interest_key = interest.strip().lower()
            edge = edges.get(interest_key, {}).get(concept_key)
            if edge is not None:
                type_bonus = {"ingest": 0.5, "engaged": 1.0, "saved": 2.0}
                total += edge.get("weight", 1.0) * type_bonus.get(edge.get("type", "ingest"), 0.5)
        concept["graph_weight"] = round(total, 2)

    concepts.sort(key=lambda c: c.get("graph_weight", 0), reverse=True)
    return concepts


def annotate(
    brief: dict[str, Any],
    user_interests: list[str],
) -> dict[str, Any]:
    """Add ``interest_match`` labels to every concept in a paper brief.

    Labels are ``"high"`` (graph weight ≥ 2), ``"medium"`` (≥ 0.5), or
    ``"low"`` (< 0.5 or absent from the graph).

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
    graph = load()
    edges = graph.get("edges", {})

    for bucket_key in ("top_concepts", "concepts"):
        for concept in brief.get(bucket_key, []):
            concept_key = concept.get("name", "").strip().lower()
            total = 0.0
            for interest in user_interests:
                interest_key = interest.strip().lower()
                edge = edges.get(interest_key, {}).get(concept_key)
                if edge is not None:
                    type_bonus = {"ingest": 0.5, "engaged": 1.0, "saved": 2.0}
                    total += edge.get("weight", 1.0) * type_bonus.get(edge.get("type", "ingest"), 0.5)

            if total >= 2.0:
                concept["interest_match"] = "high"
            elif total >= 0.5:
                concept["interest_match"] = "medium"
            else:
                concept["interest_match"] = "low"

    return brief


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------


def get_concept_graph() -> dict[str, Any]:
    """Inspect the local concept graph (interest-to-concept edges with weights)."""
    graph = load()
    edges = graph.get("edges", {})
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

    return {
        "graph_path": str(CONCEPT_GRAPH_PATH),
        "edge_count": len(summary),
        "edges": summary,
    }
