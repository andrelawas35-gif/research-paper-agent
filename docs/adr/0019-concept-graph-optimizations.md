# ADR 0019 — Concept Graph Optimizations

**Date:** 2026-07-01
**Status:** Accepted

## Context

The concept graph has only 2 edges across 7 ingested papers. Token overlap
is too literal ("research agents" won't match "epistemic convergence" even
when the paper is about agent-based epistemology). Edge types are a one-way
ratchet with no rejection signal. There are no paper↔paper links, no concept
deduplication, no weight seeding from match quality, and no decay for ingest
edges. The graph is starving.

## Decisions

### 1. Fuzzy similarity replaces exact token overlap

Token overlap is replaced with a fuzzy Jaccard similarity that uses prefix
matching (first 4 chars), case normalization, and punctuation stripping.
This catches "agent"↔"agents", "model"↔"modeling", "bayesian"↔"bayes"
without new dependencies. The similarity function returns a float 0–1 and
its signature is swappable for embeddings later. Token overlap remains as
a fast pre-filter.

### 2. `rejected` edge type with negative weight

Added to `_EDGE_TYPES`. `rank()` and `annotate()` subtract rejected weight
instead of adding it. A `rejected` edge is sticky — only an explicit `saved`
edge can override it. `decay()` never touches rejected edges.

Promotion hierarchy: `rejected < ingest < engaged < saved`. A rejected edge
can be promoted to saved (user changes their mind), but never to engaged or
ingest (those would dilute the rejection signal).

### 3. Paper↔paper links computed lazily on `_save()`

A `"paper_links"` key is added to the graph. After every `_save()`, papers
that share concept edges are linked with a `shared_concepts` count and a
`shared_interests` list. `get_concept_graph()` exposes this for the agent's
cluster-weight bias (ADR 0018). No new data — purely aggregating existing edges.

### 4. `merge_similar_concepts(threshold)` for deduplication

On-demand function that compares all concept keys pairwise using the same
similarity function. When similarity ≥ threshold (default 0.85), concepts
are merged: weights sum, source_papers union, highest edge type kept. The
surviving key is the one with the most source_papers. Merging is deliberate
and on-demand, not automatic on save.

### 5. Initial edge weight seeded from similarity score

When `link()` creates a new edge, `weight` starts at the similarity score
(0–1) rather than flat 1.0. The type bonus multiplier applies on top in
`_edge_weight()`. This means among ingest edges, genuinely similar concepts
rank higher from day one. Explicit saves still outrank passive matches
through the type bonus multiplier (×2.0 vs ×0.5).

### 6. Decay extended to ingest edges

- Ingest edges with weight < 0.5 and no activity for 60 days → removed
- Ingest edges with no promotion for 90 days → removed
- Engaged edges: unchanged (30-day decay, 60-day removal)
- Saved edges: never decayed
- Rejected edges: never decayed

Ingest edges now carry a `created_at` timestamp (already present) used for
the 90-day check.

## Consequences

- `concept_graph.py` grows `_similarity()`, `merge_similar_concepts()`,
  `_rebuild_paper_links()`, and an updated `decay()`.
- `link()` signature unchanged but behavior changes (weight from similarity).
- Existing edges at weight 1.0 are grandfathered — they keep their weight.
- `_EDGE_TYPES` grows from 3 to 4 values.
- No new Python dependencies.
- All existing tests should pass; new tests needed for reject, merge, and
  extended decay.
