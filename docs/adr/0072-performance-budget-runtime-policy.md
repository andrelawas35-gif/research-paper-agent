# ADR 0072: Performance Budget Runtime Policy

Agent performance adaptation will be owned by a per-turn Performance Budget rather than scattered across prompt instructions and individual tools. The Performance Budget decides how much context to preload, which tool groups are exposed, whether durable memory writes are allowed immediately, and when fresh tool calls should replace dynamic system-instruction context.

## Budget Tiers

- `fast` — minimal dynamic context, narrow tool surface, no speculative durable writes, and a preference for direct answers or one tool call.
- `balanced` — small stable snapshot, mode-relevant tools, normal evidence retrieval, and durable writes only for explicit user intent or high-confidence events.
- `deep` — richer retrieval, broader tool access, more synthesis context, and allowed multi-step tool use, while still avoiding noisy memory writes.

## Tier Selection

The runtime infers the budget tier from explicit user wording and the active Agent Mode, with `balanced` as the default. Explicit overrides such as "fast mode," "deep mode," "keep it quick," or "think deeply" win over inference.

- Choose `fast` for terse commands, status checks, admin checks, direct facts, and wording such as "quick," "just," "only," or "don't explain."
- Choose `balanced` for ordinary source, retrieve, writing, note, relationship, and implementation work.
- Choose `deep` for explicit grill, design, synthesis, mentor, review, tutoring, comparison, planning, and stress-testing work.

`_infer_performance_budget(ctx)` should use any explicit Agent Mode already inferred by the runtime when available. If no runtime mode is available, it may infer a loose mode hint from the latest user text using the existing mode taxonomy terms. Mode remains a hint only: explicit performance wording wins, and unreliable or missing mode information falls back to `balanced`.

## Budget vs. Mode Priority

When Agent Mode and Performance Budget appear to disagree, explicit performance wording controls execution style and work depth, while Agent Mode controls correctness obligations, evidence boundaries, and privacy rules. The budget can reduce how much work is attempted, but it must not relax the mode's correctness constraints.

Examples:

- "Quickly review this ADR" means Review Mode with a `fast` budget: report the highest-risk findings, use fewer tool calls, and avoid an exhaustive scan.
- "Deeply summarize this file" means Source/Retrieve Mode with a `deep` budget: do a richer pass even though the mode is not inherently deep.
- "Fast mentor answer" means Mentor Mode with a `fast` budget: answer tersely, but do not make mentor-specific claims without evidence.

## Correctness Floors

Correctness floors override speed. A `fast` budget may shorten the scan, reduce output, or ask whether to continue deeper, but it must not skip required evidence, privacy checks, source grounding, validation, or safety constraints.

If a user requests a fast answer for high-stakes or correctness-sensitive work, the agent should either perform the minimum necessary checks or say it cannot responsibly answer at that speed. For example, "quickly tell me if this medical, legal, or financial claim is safe" must not bypass evidence requirements merely because the user asked for speed.

## Dynamic Context Policy

Dynamic context is budgeted rather than automatic.

- `fast` returns an empty dynamic instruction unless a fixed instruction is truly needed. This maximizes context-cache alignment and avoids prompt tokens for runtime-only diagnostics.
- `balanced` may include a tiny stable user overview such as interests, style, polish level, and top concepts. It should not include recent-note listings, session metadata, counters, timestamps, or other frequently changing rows.
- `deep` may include a richer capped snapshot, but volatile details should still be fetched through tools when needed.

Budget diagnostics, including a selected `fast` tier, should live outside prompt context in logs or debug surfaces.

Fresh notes, session metadata, interaction logs, and other changing state should usually be retrieved through tools instead of being preloaded into the system instruction on every turn.

The `balanced` snapshot includes only stable user-orientation fields: explicit interests, style preferences, polish default, explicit avoidances, quirks, and stable top graph concepts without counts. It excludes recent notes, unfinished session metadata, interaction logs, weak tutor concepts, exact counts, timestamps, and other frequently changing "latest" state.

The `deep` snapshot may include task-relevant context with stable slices and strict caps, but it is still scoped by task type rather than dumping all available state. It may include the balanced snapshot, recent note titles/concepts only when note, synthesis, builder, review, or resume work is active, weak tutor concepts only when tutor, mentor, or learning work is active, an unfinished prior session only for explicit resume or continuation tasks, and top graph concepts without exact volatile counters. It still excludes raw note text, full interaction logs, full graph dumps, changing exact counts, timestamps, and more than the one session row needed for re-anchoring.

## Cache Invalidation Semantics

Snapshot cache invalidation is immediate for explicit user-authored state and stale-tolerant for derived state.

- Immediate invalidation: explicit preferences, explicit Personal Notes, explicit relationship captures, and paper ingestion.
- Stale-tolerant: graph projection updates, Candidate Signals, interaction logs, tutor mastery summaries, and session metadata.

User-authored state should become visible quickly, while derived state changes should avoid system-instruction churn and be fetched through tools when needed.

Snapshot cache keys must include the budget tier, such as `(state_fingerprint, budget_tier)`, because `balanced` and `deep` may include different content for the same durable state. `fast` bypasses the snapshot cache entirely because it returns an empty dynamic instruction.

## Tool Calls vs. Preload Boundary

Snapshots are for orientation only. Tools are required for fresh, source-specific, or correctness-sensitive state, including actual note contents, relationship details, paper evidence, mentor evidence, latest graph state, tutor progress used for grading or teaching, audit/correction actions, and anything the user explicitly asks to inspect.

This prevents the dynamic snapshot from becoming an unreliable miniature database.

## External Lookup Policy

Fresh external lookup is budgeted by latency and correctness need.

- `fast` avoids web/search or other external lookup unless the user explicitly asks for current information or correctness requirements make lookup necessary.
- `balanced` may perform one targeted lookup when freshness materially affects the answer.
- `deep` may perform multi-query verification, compare sources, and spend more tool calls on current-state accuracy.

If lookup is skipped for speed, the agent should make the recency limit clear instead of implying it checked fresh state.

## Budget Visibility

Performance Budget is inferred silently by default, following Mode Visibility. The agent should not prefix ordinary answers with the selected tier. It may mention the tier only when performance behavior would otherwise be surprising or useful to control, such as "I'll keep this fast," "I'm switching to deep mode for the comparison," or "I'll fetch fresh notes rather than preload them." Debug, admin, or audit surfaces may expose the selected budget explicitly later.

## Override Persistence

Performance Budget overrides are session-local by default. Wording such as "keep it fast," "quickly," or "for now" affects the current turn or session only. Durable budget preferences require explicit memory language such as "always keep responses fast" or "remember I prefer fast mode." Scoped wording such as "for this project/thread, use deep mode" may become a scoped preference only when the runtime can represent that scope; otherwise it remains session-local.

Inferred budget should be computed per turn. The runtime may keep optional session-local override state for phrases like "keep it fast for now," but it must not write inferred budget into durable profile or memory. Only explicit durable language, such as "remember I prefer concise fast answers," may create a durable budget preference.

## Performance Metrics

The first slice may record lightweight local diagnostics, but metrics are never preloaded into dynamic instructions. Useful metrics include selected budget tier, snapshot type and approximate size, exposed tool count when available, whether a cache-stable snapshot was reused, and generation latency if the runtime exposes it later. These metrics are for admin/debug/audit surfaces, not model context.

## Generation Controls

Performance Budget may control generation parameters when the runtime supports them, but this is deferred until after dynamic context budgeting.

- `fast` should prefer shorter maximum output, lower reasoning depth, and possibly cheaper or faster model routing when correctness floors allow.
- `balanced` should use normal defaults.
- `deep` may allow larger output and deeper reasoning.

Model routing must be conservative. The runtime must not downgrade tasks that require strong reasoning, evidence synthesis, or safety judgment merely because the user asked for speed.

## Failure Mode

If budget inference is uncertain or ADK context extraction fails, the runtime falls back to `balanced` with a stable tiny snapshot. It must not guess `deep`, dump all context, emit a warning into the model prompt, or write a diagnostic into normal user-visible chat. Optional diagnostics may be logged outside prompt context.

## Tool Surface Policy

The preferred implementation narrows tool exposure by Performance Budget and active Agent Mode when the runtime supports per-turn tool selection.

- `fast` exposes only core low-latency tools, and often no tools when the answer can be direct.
- `balanced` exposes tools for the inferred primary mode plus safe inspection tools.
- `deep` exposes broader synthesis, review, tutor, mentor, and multi-step support tools.

If the runtime cannot vary tool lists per turn, the fallback is to reduce tool-schema overhead by shortening tool descriptions, grouping related capabilities behind facade tools, and avoiding unbounded growth of the root-agent tool list.

## Durable Write Policy

Durable writes are gated by Performance Budget and evidence strength.

- `fast` permits durable writes only for explicit user commands such as "remember," "save note," or "add person."
- `balanced` permits durable writes for explicit user intent and high-confidence structured events.
- `deep` may produce candidate signals and projection updates, but durable preferences still require explicit confirmation or repeated evidence.

This reduces latency, file writes, graph invalidations, snapshot cache misses, and overfitting from weak signals.

## First Implementation Slice

The first implementation slice is dynamic context budgeting, not dynamic tool lists.

- Add `_infer_performance_budget(message/context) -> fast | balanced | deep`.
- Implement budget inference in two layers: `_infer_performance_budget_from_text(text: str, mode_hint: str = "") -> str` for testable core logic, and `_infer_performance_budget(ctx) -> str` to extract the latest user message and optional hints from ADK context.
- Add a small defensive latest-user-text extractor for `_infer_performance_budget(ctx)` that tries known ADK attributes or fields, returns `""` if unavailable, and never raises into prompt construction.
- Represent budget tiers as plain string literals (`"fast"`, `"balanced"`, `"deep"`) for the first slice, with a tiny validation helper if needed.
- Keep `_dynamic_instruction(ctx)` as the orchestrator, but split snapshot construction into `_build_balanced_snapshot()` and `_build_deep_snapshot()` helpers so tier rules remain readable and testable.
- Make `_dynamic_instruction(ctx)` return no dynamic snapshot for `fast`, a tiny stable overview for `balanced`, and a richer capped snapshot for `deep`.
- Remove recent notes and session metadata from `balanced`.
- Keep `_STATIC_INSTRUCTION` unchanged.
- Add tests proving consecutive `fast` and `balanced` turns keep identical dynamic instructions when durable state is unchanged.

The first slice is done when tests cover pure budget inference, dynamic snapshot content by tier, cache stability across consecutive `fast` and `balanced` turns, fallback behavior when context extraction fails, and a regression that `fast` returns an empty dynamic instruction.

Typed enums or value objects are deferred until Performance Budget starts crossing module boundaries into model routing, tool exposure, metrics, or UI/debug surfaces.

`fast` bypasses snapshot building entirely.

Dynamic tool lists are deferred until the ADK runtime path is understood well enough to vary tool exposure safely.

## Rationale

The agent already has cache-sensitive instructions, a dynamic context header, many tools, and several memory-writing paths. Treating performance as a runtime policy keeps static instructions stable, avoids volatile session state in system prompts, makes tool-surface size an explicit trade-off, and gives latency-sensitive turns a clear way to stay fast without weakening deep-reasoning turns.

## Consequences

- Static instructions remain truly static.
- Dynamic context becomes budgeted rather than automatic by default.
- Tool exposure can be grouped by mode or budget tier.
- Durable writes should be gated by meaningfulness and budget, not performed merely because a turn contains a weak signal.
- Fresh state should usually be fetched through tools when needed rather than preloaded into every turn.
