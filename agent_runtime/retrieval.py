"""Text utilities, passage scoring, and evidence search.

Extracted from agent.py per Python Module Architecture Plan Phase 3.
Owns tokenisation, citation formatting, TF-IDF passage scoring, and
the ``search_evidence`` tool — everything needed to find and rank
passages from ingested papers.

Circular-dependency note: ``search_evidence`` needs ``_load_records``,
``_filter_records_by_scope``, and ``_all_passages`` from
``agent_runtime.papers``.  These are imported lazily inside the
function to avoid a module-level cycle.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

# ── Stopwords ────────────────────────────────────────────────────────

STOPWORDS: frozenset[str] = frozenset({
    "about", "abstract", "after", "again", "against", "and", "are",
    "also", "among", "because", "before", "between", "can", "could",
    "figure", "first", "for", "from", "have", "into", "more", "most",
    "other", "paper", "results", "section", "show", "shows", "such",
    "table", "than", "that", "the", "their", "these", "this",
    "through", "using", "were", "when", "where", "which", "while",
    "with", "would",
})

# ── Section patterns ─────────────────────────────────────────────────

SECTION_PATTERNS: dict[str, str] = {
    "abstract": r"\babstract\b",
    "introduction": r"\bintroduction\b",
    "methods": r"\b(method|approach|model|architecture|dataset|experiment|training|evaluation|implementation)\b",
    "findings": r"\b(result|finding|improve|outperform|demonstrate|show|evidence|accuracy|performance)\b",
    "limitations": r"\b(limitation|limited|challenge|risk|failure|bias|constraint|threat|future work)\b",
    "open_questions": r"\b(open question|future|unknown|unclear|further research|remains|next step)\b",
}


# ── Text utilities ───────────────────────────────────────────────────


def tokenize(text: str) -> list[str]:
    """Tokenise text into meaningful lowercase words, filtering stopwords."""
    return [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
        if word not in STOPWORDS
    ]


def sentences(text: str) -> list[str]:
    """Split text into sentences, skipping fragments shorter than 40 chars."""
    compact = re.sub(r"\s+", " ", text).strip()
    return [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", compact)
        if len(s.strip()) > 40
    ]


def keywords(text: str, limit: int = 30) -> list[str]:
    """Return the most frequent meaningful words in text."""
    counts = Counter(tokenize(text))
    return [word for word, _ in counts.most_common(limit)]


def citation(source: str, page: int | None, passage_id: str) -> str:
    """Format a standard citation string."""
    if page is None:
        return f"{source}, {passage_id}"
    return f"{source}, page {page}, {passage_id}"


# ── Passage scoring ──────────────────────────────────────────────────

_SEARCH_INDEX_CACHE: dict[
    tuple[tuple[str, int, int, int], ...],
    tuple[list[dict[str, Any]], Counter, list[Counter], list[str]],
] = {}


def _clear_search_cache() -> None:
    """Clear cached retrieval indexes after knowledge-base writes."""
    _SEARCH_INDEX_CACHE.clear()


def _records_signature(records: list[dict[str, Any]]) -> tuple[tuple[str, int, int, int], ...]:
    """Return a compact signature for the records used in a search."""
    return tuple(
        (
            str(record.get("source", "")),
            int(record.get("characters", 0) or 0),
            int(record.get("page_count", 0) or 0),
            len(record.get("passages", []) or []),
        )
        for record in records
    )


def _search_index(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Counter, list[Counter], list[str]]:
    """Build or reuse tokenized passages and document frequencies."""
    signature = _records_signature(records)
    cached = _SEARCH_INDEX_CACHE.get(signature)
    if cached is not None:
        return cached

    passages = [p for r in records for p in r.get("passages", [])]
    doc_freq: Counter = Counter()
    passage_terms: list[Counter] = []
    passage_text_lower: list[str] = []
    for passage in passages:
        text_lower = passage.get("text", "").lower()
        terms = Counter(tokenize(text_lower))
        passage_terms.append(terms)
        passage_text_lower.append(text_lower)
        for term in terms:
            doc_freq[term] += 1

    index = (passages, doc_freq, passage_terms, passage_text_lower)
    _SEARCH_INDEX_CACHE[signature] = index
    return index


def score_passage(
    query_terms: list[str],
    passage: dict[str, Any],
    document_count: int,
    doc_freq: Counter,
) -> float:
    """TF-IDF score for one passage against query terms.

    Bonuses:
    - +3.0 for exact phrase match
    - +0.35 per keyword match
    """
    text = passage["text"].lower()
    passage_terms = Counter(tokenize(text))
    if not passage_terms:
        return 0.0

    score = 0.0
    for term in query_terms:
        tf = passage_terms.get(term, 0)
        if not tf:
            continue
        idf = math.log((document_count + 1) / (doc_freq.get(term, 0) + 1)) + 1
        score += (1 + math.log(tf)) * idf

    query_phrase = " ".join(query_terms)
    if query_phrase and query_phrase in text:
        score += 3.0

    for kw in passage.get("keywords", []):
        if kw in query_terms:
            score += 0.35

    return round(score, 4)


def _score_precomputed_passage(
    query_terms: list[str],
    query_phrase: str,
    passage: dict[str, Any],
    passage_terms: Counter,
    text_lower: str,
    document_count: int,
    doc_freq: Counter,
) -> float:
    """Score a passage using cached tokenization."""
    if not passage_terms:
        return 0.0

    score = 0.0
    for term in query_terms:
        tf = passage_terms.get(term, 0)
        if not tf:
            continue
        idf = math.log((document_count + 1) / (doc_freq.get(term, 0) + 1)) + 1
        score += (1 + math.log(tf)) * idf

    if query_phrase and query_phrase in text_lower:
        score += 3.0

    for kw in passage.get("keywords", []):
        if kw in query_terms:
            score += 0.35

    return round(score, 4)


# ── Evidence search ──────────────────────────────────────────────────


def search_evidence(
    query: str,
    max_passages: int = 8,
    evidence_scope: str = "",
) -> dict[str, Any]:
    """Search ingested evidence passages with weighted lexical ranking and citations.

    Uses lazy imports for ``agent_runtime.papers`` to avoid a circular
    dependency at module level (papers imports retrieval for text utils).
    """
    # Lazy imports — avoid circular dependency with papers module.
    from research_paper_agent.agent_runtime.papers import (  # noqa: PLC0415
        _filter_records_by_scope,
        _load_records,
    )

    query_terms = tokenize(query)
    if not query_terms:
        return {"query": query, "evidence_scope": evidence_scope or None, "matches": []}

    records = _filter_records_by_scope(_load_records(), evidence_scope)
    passages, doc_freq, passage_terms, passage_text_lower = _search_index(records)

    matches = []
    query_phrase = " ".join(query_terms)
    for index, passage in enumerate(passages):
        s = _score_precomputed_passage(
            query_terms,
            query_phrase,
            passage,
            passage_terms[index],
            passage_text_lower[index],
            len(passages),
            doc_freq,
        )
        if s > 0:
            matches.append({
                "source": passage["source"],
                "citation": passage["citation"],
                "score": s,
                "keywords": passage.get("keywords", []),
                "passage": passage["text"],
            })

    matches.sort(key=lambda item: item["score"], reverse=True)
    return {
        "query": query,
        "evidence_scope": evidence_scope or None,
        "matches": matches[:max(1, min(max_passages, 20))],
    }
