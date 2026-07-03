# Performance Budget Implementation Plan

This plan implements ADR 0072 in two slices. Slice 1 makes dynamic context budget-aware and cache-friendly. Slice 2 extends the same Performance Budget into runtime controls such as tool exposure, durable writes, lookup behavior, diagnostics, and generation settings.

## Slice 1: Dynamic Context Budgeting

Goal: reduce context-cache misses and prompt bloat without changing tool exposure or model routing.

### 1. Add Budget Inference

Add the following helpers in `agent.py` near the current dynamic-instruction code:

- `_extract_latest_user_text(ctx) -> str`
- `_extract_mode_hint(ctx) -> str`
- `_infer_performance_budget_from_text(text: str, mode_hint: str = "") -> str`
- `_infer_performance_budget(ctx) -> str`

Rules:

- Explicit fast/deep wording wins over mode inference.
- Agent Mode is only a hint.
- Unknown or missing context falls back to `balanced`.
- No helper may raise into prompt construction.

### 2. Split Snapshot Builders

Replace the single `_build_snapshot(ctx)` path with tier-specific builders:

- `_build_balanced_snapshot(ctx: Any | None = None) -> str`
- `_build_deep_snapshot(ctx: Any | None = None, mode_hint: str = "") -> str`

`fast` should bypass snapshot building entirely and return an empty dynamic instruction.

`balanced` includes stable orientation only:

- explicit interests
- style preferences
- polish default
- explicit avoidances
- quirks
- stable top graph concepts without counts

`balanced` excludes:

- recent notes
- unfinished session metadata
- interaction logs
- weak tutor concepts
- exact counts
- timestamps
- any "latest" state

`deep` may include richer context, but only when task-scoped:

- recent note titles/concepts for note, synthesis, builder, review, or resume tasks
- weak tutor concepts for tutor, mentor, or learning tasks
- one unfinished prior session only for explicit resume or continuation tasks
- top graph concepts without volatile counters

`deep` still excludes raw note text, full logs, full graph dumps, timestamps, exact changing counts, and unbounded session rows.

### 3. Make Snapshot Cache Budget-Aware

Change `_SNAPSHOT_CACHE` from a two-field tuple to either:

- `(state_fingerprint, budget_tier, snapshot_text)`, or
- a small dictionary keyed by `(state_fingerprint, budget_tier)`

`balanced` and `deep` must not share cached snapshot text for the same durable state. `fast` bypasses the cache because it returns `""`.

### 4. Update `_dynamic_instruction(ctx)`

Expected flow:

1. Infer budget.
2. If `fast`, return `""`.
3. Compute durable-state fingerprint.
4. Look up cached snapshot by `(fingerprint, budget)`.
5. Build the tier-specific snapshot on cache miss.
6. Append only stable fixed hints, never counts, timestamps, or session-churn details.

Keep `_STATIC_INSTRUCTION` unchanged.

### 5. Add Tests

Add focused tests in `tests/test_agent.py`:

- pure inference for `fast`, `balanced`, and `deep`
- explicit performance wording beats mode hints
- context extraction failure falls back to `balanced`
- `fast` returns an empty dynamic instruction
- `balanced` excludes recent notes, session metadata, weak tutor concepts, counts, timestamps, and latest-state content
- `deep` includes richer context only for relevant task types
- consecutive `fast` and `balanced` turns remain cache-stable when durable state is unchanged

### 6. Verify

Run:

```bash
/tmp/research_agent_test_venv/bin/python -m pytest
```

Slice 1 is complete when the full suite passes and ADR 0072's first-slice done criteria are covered.

## Slice 2: Runtime Performance Controls

Goal: extend Performance Budget beyond dynamic context after Slice 1 proves stable.

### 1. Tool Surface Policy

First inspect whether the ADK runtime supports per-turn tool selection for `Agent`.

If supported:

- `fast`: expose only core low-latency tools, often no tools when the answer can be direct
- `balanced`: expose tools for the inferred primary mode plus safe inspection tools
- `deep`: expose broader synthesis, review, tutor, mentor, and multi-step tools

If not supported:

- shorten tool descriptions
- group related capabilities behind facade tools
- avoid unbounded growth of `root_agent.tools`

### 2. Durable Write Gating

Route memory/profile/graph writes through budget-aware checks:

- `fast`: explicit commands only, such as "remember," "save note," or "add person"
- `balanced`: explicit intent and high-confidence structured events
- `deep`: candidate signals and projection updates are allowed, but durable preferences still require explicit confirmation or repeated evidence

### 3. External Lookup Policy

Apply budget-aware lookup behavior:

- `fast`: avoid external lookup unless the user asks for current information or correctness requires it
- `balanced`: allow one targeted lookup when freshness materially affects the answer
- `deep`: allow multi-query verification and source comparison

When lookup is skipped for speed, the agent should make recency limits clear.

### 4. Diagnostics Outside Prompt Context

Record lightweight diagnostics outside dynamic instructions:

- selected budget tier
- snapshot type and approximate size
- cache hit or miss
- exposed tool count when available
- latency when the runtime exposes it

These diagnostics belong in logs or debug/admin surfaces, not model prompt context.

### 5. Generation Controls

Only implement generation controls if the runtime supports them cleanly.

- `fast`: shorter maximum output, lower reasoning depth, and possibly faster model routing when correctness floors allow
- `balanced`: default generation settings
- `deep`: larger output and deeper reasoning

Model routing must be conservative. Do not downgrade tasks that require strong reasoning, evidence synthesis, mentor/review judgment, or high-stakes safety handling.

### 6. Slice 2 Tests

Prefer policy tests over brittle ADK integration tests:

- budget to durable-write permission
- budget to lookup policy
- budget to tool group selection, if supported
- diagnostics never appear in `_dynamic_instruction`
- correctness floors override speed-sensitive routing

## Implementation Order

1. Implement Slice 1 and commit it independently.
2. Inspect ADK support for per-turn tools and generation controls.
3. Implement Slice 2 in smaller commits by runtime surface: tool policy, write gating, lookup policy, diagnostics, then generation controls.
