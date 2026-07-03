# ADR 0065: Web Search + Projection Plumbing + Mode Taxonomy

Implements the remaining gaps from ADR 0071 and ADRs 0061 through 0064: the `search_web` tool, projection plumbing across canonical stores, `projection_status` in tool results, and the updated mode taxonomy.

## Decision

### `search_web` tool (ADR 0071)

- Single tool with dual backends: `source="scholar"` (Semantic Scholar API, free) and `source="web"` (DuckDuckGo instant answers, free). `source="auto"` uses heuristic signals to route queries.
- Scholar results return structured paper metadata (title, authors, year, abstract, citations, URL) with `source_quality: peer-reviewed`. These can earn High recommendation confidence.
- Web results return snippets with `[from web: domain.com]` provenance and `source_quality` tags. Capped at Medium confidence.
- Zero new API dependencies — uses `urllib.request` (stdlib) for both backends.
- Fourth provenance lane instruction added: web results presented separately from paper Evidence, Personal Notes, and Inference.
- Source quality classifier: `_classify_source_quality(url)` returns `peer-reviewed`, `official-docs`, `technical-blog`, `forum`, `vendor`, or `unknown`.

### Projection plumbing (ADR 0061-0064)

- `_emit_projection_update(source_type, source_id, context)` — best-effort typed projection update after canonical writes. Adds concept-graph edges with typed `source_type` references for `personal_note`, `tutor_progress`, and `grill_answer` sources. Failure does not fail the canonical write (ADR 0063).
- `_projection_status(result, ...)` — attaches a `projection_status` dict (`{status, updated_edges, reason}`) to tool result dicts (ADR 0064).
- Wired into four write tools: `save_personal_note`, `edit_personal_note`, `record_tutor_answer`, `respond_to_adaptive_grill`.

### Mode taxonomy update (ADR 0060)

- Instruction updated with 14 job-based modes: Source, Retrieve, Synthesis, Builder, Grill, Tutor, Reflect, Relationship, Taste, Review, Writing, Artifact, Admin. Old names preserved as aliases (Reader→Source, Profile→Reflect).
- Rule: at most one primary mode plus one supporting mode, silently inferred by default.

## Consequences

- `search_web` tool added to agent tools list
- Fourth provenance lane and mode taxonomy in agent instruction
- `projection_status` field on all four write tools
- Zero new Python dependencies
- 70/70 tests passing, zero regressions
