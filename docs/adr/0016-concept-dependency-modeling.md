# ADR 0016: Concept Dependency Modeling

## Status

Accepted

## Context

ADR 0015 (Tutor Mode) rejected concept dependency modeling for the initial pass, noting that "the concept graph doesn't model dependencies, and building that is a separate architectural decision." The Tutor Mode's `_next_concept` uses a simple alternating strategy (weak concepts, then strong concepts, then interests) with no awareness of which concepts pedagogically depend on others. This means the tutor might teach "vector search" before "embeddings" — a suboptimal curriculum sequence.

The Concept Graph (ADR 0014) is a bipartite graph connecting User Interests to Paper Concepts. Adding concept-to-concept dependency edges extends the graph model without replacing it.

## Decision

Add **Prerequisite Hints** — soft pedagogical dependency edges between Paper Concepts — stored in the Concept Graph JSON alongside existing interest-to-concept edges.

### Design choices

| Choice | Decision |
|--------|----------|
| Dependency semantics | **Pedagogical advisability** — a soft "recommends-before" hint, not a hard "requires" gate. The user can override at any time |
| Source of dependencies | **LLM-inferred at ingest time** — one extra LLM call per paper, piggybacking on concept extraction |
| Effect on `_next_concept` | **Priority boost** — unmet prerequisites get a scoring bonus in the curriculum ordering, but never block |
| Cycle / orphan safety | **Depth cap of 1** — only one hop is ever inspected per turn, making cycles harmless and orphan prerequisites silently ignored |
| Storage | New `"dependencies"` key in `concept_graph.json` (schema version bumped to 2), alongside existing `"edges"` |
| Scope | `concept_graph.py` (two new functions: `link_prerequisite`, `get_prerequisites`) + `agent.py` (one new helper `_infer_dependencies`, modified `_next_concept`) |

### Data shape

```json
{
  "schema_version": 2,
  "edges": { /* existing interest→concept edges unchanged */ },
  "dependencies": {
    "vector search": {
      "embeddings": {
        "concept": "vector search",
        "prerequisite": "embeddings",
        "source_papers": ["paper_a.pdf"],
        "created_at": "2026-06-30T12:00:00Z"
      }
    }
  }
}
```

### How `_next_concept` uses prerequisites

1. Build weak/strong candidate lists as before.
2. For each candidate, call `get_prerequisites(concept)` (one hop).
3. If a prerequisite is in `tutor_progress` with mastery < 80%, boost it to the front of the weak list.
4. If a prerequisite exists in the graph but has never been taught, return it immediately as a new concept to introduce.
5. Fall through to the existing alternating strategy if no prerequisites apply.

The depth cap of 1 means `_next_concept` never recurses into prerequisites-of-prerequisites — that's the next turn's problem.

## Consequences

- The tutor curriculum gains meaningful sequencing without rigid constraints. A misinferred dependency is at worst a mild nudge, never a dead end.
- One additional LLM call per `ingest_paper` (temperature 0, ~200 tokens). At current DeepSeek pricing this is negligible.
- The bipartite concept graph becomes a mixed graph (interest→concept edges + concept→concept prerequisite edges). Future features like transitive closure or dependency-aware paper briefs are possible but deferred.
- Dependency edges are never decayed — they represent pedagogical relationships that don't change with time. They can be superseded by re-ingesting a paper (newer inference overwrites the same keys).

## Alternatives Considered

- **Hard blocking**: refuse to teach a concept until prerequisites are mastered. Rejected — too rigid for research concepts where strict dependencies are rare, and a misinferred dependency would lock the curriculum.
- **Warning mode**: teach anyway but show a warning. Rejected — adds UI friction for a soft signal; priority boost is invisible and equally effective.
- **Full topological sort with cycle detection**: proper curriculum sequencing with Tarjan's algorithm. Rejected — over-engineered for a soft-hint system; depth cap of 1 achieves 80% of the value at 5% of the complexity.
- **On-demand inference**: ask the LLM during every `_next_concept` call. Rejected — adds latency to every tutor turn; ingest-time inference is amortized.
- **User-authored prerequisites**: a manual `prerequisites.json` file. Rejected — defeats the agent's purpose of adapting to whatever papers the user throws at it.
