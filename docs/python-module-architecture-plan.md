# Python Module Architecture Plan

This plan explains how to split the Python implementation into deeper modules without turning the codebase into a pile of thin pass-through files. It should be implemented after or alongside the first Performance Budget slice from `docs/performance-budget-implementation-plan.md`.

## Status (2026-07-04)

All five phases below are implemented. `agent.py` is now a composition module (~1120 lines, down from 3367) containing imports, the static instruction body, thin tool adapters, tool-list composition, and `root_agent` construction. Every `agent_runtime/` module listed under Target Shape exists and owns its implementation; `agent.py` imports each public/private name once and reassigns it at module level (e.g. `search_web = _ws_search_web`) rather than keeping a duplicate local definition.

A cleanup pass on 2026-07-04 removed nine leftover duplicate function bodies in `agent.py` (tutor and grill helpers) that had been redefined locally *after* their `agent_runtime` reassignment, silently shadowing the extracted implementation — tests passed either way because the duplicates were behaviorally identical, but the extraction was cosmetic for those two modules until the duplicates were deleted.

That same pass also fixed a test-isolation gap: `agent_runtime/tutor.py`, `grill.py`, and `audit.py` each bind their own copy of path constants via `from .paths import X` at import time, so `tests/conftest.py` patching `agent.py`'s or `paths.py`'s copy did not redirect these modules — tests were silently reading/writing the real `user_model/` directory. `conftest.py` now patches every `agent_runtime` submodule's own bound path constants directly.

## Current Shape

`agent.py` is too large because it combines many unrelated modules behind one giant interface. At the time this plan was written, it was 3367 lines and included paper ingestion, evidence retrieval, user profile learning, session metadata, note wrappers, relationship wrappers, web search, self-audit, adaptive grill, tutor mode, dynamic instructions, LLM setup, and root agent wiring.

The problem is not line count alone. The problem is low locality: changing one behavior requires navigating a file that owns many different responsibilities. This also makes tests less direct because the useful seams are buried inside `agent.py`.

`concept_graph.py`, `personal_notes.py`, and `relationship_management.py` are also long, but they are more coherent. They should stay intact until `agent.py` has been reduced.

## Target Shape

Create an `agent_runtime/` package. Keep `agent.py` as the root composition module that imports the runtime modules, exposes tool functions, and constructs `root_agent`.

Recommended modules:

- `agent_runtime/dynamic_context.py` — Performance Budget inference, snapshot builders, state fingerprinting, snapshot cache, and dynamic instruction construction.
- `agent_runtime/user_profile.py` — profile schema, preference writes, signal extraction, validation, and profile summaries.
- `agent_runtime/session_memory.py` — interaction logs, session metadata, session goals, and candidate signal recording.
- `agent_runtime/papers.py` — paper ingestion, paper records, paper file management, metadata extraction, briefs, comparisons, and study guides.
- `agent_runtime/retrieval.py` — passage scoring, evidence filtering, citation formatting, and evidence search.
- `agent_runtime/web_search.py` — Semantic Scholar search, DuckDuckGo search, fallback search, source-quality classification, and web search projection.
- `agent_runtime/audit.py` — knowledge self-audit and self-audit correction flows.
- `agent_runtime/grill.py` — adaptive grill question generation, session storage, and grill responses.
- `agent_runtime/tutor.py` — tutor progress, next concept selection, answer grading, and tutor answer recording.
- `agent_runtime/llm.py` — DeepSeek/OpenAI LLM configuration and token settings.
- `agent_runtime/tools.py` — safe tool wrapping and root tool list composition.
- `agent_runtime/paths.py` — shared path constants and directory setup.

The existing `personal_notes.py`, `concept_graph.py`, and `relationship_management.py` remain domain modules for now. They can be revisited later if their interfaces become too broad.

## Implementation Phases

### Phase 1: Extract Dynamic Context

Extract `agent_runtime/dynamic_context.py` first because it directly supports ADR 0072 and the Performance Budget implementation plan.

Move:

- state fingerprinting
- Performance Budget inference
- balanced and deep snapshot builders
- snapshot cache
- dynamic instruction construction

Keep `agent.py` importing `_dynamic_instruction` and passing it to `Agent(instruction=...)`.

This phase should also implement ADR 0072 Slice 1 if it has not already been implemented.

### Phase 2: Extract Durable and Session State

Move profile-related implementation into `agent_runtime/user_profile.py`.

Move session and interaction implementation into `agent_runtime/session_memory.py`.

This phase should make the distinction between durable user-authored state and volatile session state visible in the code, which is important for context-cache stability.

### Phase 3: Extract Papers and Retrieval

Move paper ingestion, paper record management, and paper organization into `agent_runtime/papers.py`.

Move passage scoring, evidence filtering, and evidence search into `agent_runtime/retrieval.py`.

The public behavior of existing paper tools should remain stable. This is a relocation/refactoring phase, not a feature rewrite.

### Phase 4: Extract Mode-Specific Runtime Modules

Move mode-specific flows into their own modules:

- web search into `agent_runtime/web_search.py`
- self-audit into `agent_runtime/audit.py`
- adaptive grill into `agent_runtime/grill.py`
- tutor mode into `agent_runtime/tutor.py`

Each module should own its implementation helpers, not depend on hidden helper piles in `agent.py`.

### Phase 5: Reduce `agent.py` to Composition

After the extractions, `agent.py` should contain only:

- imports
- static instruction text
- thin public tool adapters when needed by ADK
- tool list composition
- `root_agent` construction

The target is not an empty `agent.py`. The target is an agent composition module with high locality and very little domain implementation.

## Design Rules

- Prefer deep modules: small interfaces with meaningful implementation behind them.
- Do not create files that merely re-export functions whose implementation still lives in `agent.py`.
- Move helper functions with the behavior they support.
- Keep caller-facing tool behavior stable during extraction.
- Avoid introducing abstract seams unless there are at least two real adapters or a clear test seam.
- Keep tests aligned with behavior, not file layout.
- Commit each extraction phase independently after a full test run.

## Test Plan

After each phase, run:

```bash
/tmp/research_agent_test_venv/bin/python -m pytest
```

Expected safety checks:

- existing tool outputs stay compatible
- `root_agent` still constructs successfully
- dynamic instruction tests continue to pass
- paper ingestion and evidence search behavior remain stable
- note, relationship, graph, grill, tutor, and audit tests continue passing

Add focused tests only when a moved module gains a clearer direct interface. Avoid duplicating tests just because code moved.

## Assumptions

- This architecture plan is documentation only.
- `agent.py` remains the root composition module.
- `personal_notes.py`, `concept_graph.py`, and `relationship_management.py` are not split until after `agent.py` has been reduced.
- The first implementation should start with `agent_runtime/dynamic_context.py` because it improves both architecture and context-cache performance.
