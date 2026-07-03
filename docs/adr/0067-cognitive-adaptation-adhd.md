# ADR 0067: Cognitive Adaptation — ADHD-Aware Instruction + Session Metadata

Adds ADHD-aware behavioral rules to the agent instruction and introduces `session_meta.jsonl` for lightweight behavioral signal tracking as a bridge to future passive engagement inference.

## Decision

### ADHD-aware instruction (first slice, implemented now)

The agent follows five ADHD-aware interaction principles:

| Trait | Adaptation |
|---|---|
| **Attention drift** | When resuming after a pause, re-anchor with "You were exploring X. Want to continue or pivot?" No judgment, no recap dump |
| **Working memory** | Chunk long answers into labeled sections. Signal structure upfront: "Three things to know about X." Check comprehension before continuing |
| **Hyperfocus variability** | Vary pacing: rapid-fire when engaged, gentle when quiet. Ask "want me to go deeper or keep it brief?" at natural breaks |
| **Dopamine motivation** | Lead every answer with the most personally relevant insight. Connect concepts to user's interests before providing full explanation |
| **Executive function** | Offer concrete next actions after meaningful answers. "Here's what you can do with this: [1] [2] [3]." Default to actionable over abstract |

These principles are a scalable baseline, not a required response template. Simple tool results, admin confirmations, acknowledgments, direct command outputs, and terse factual answers may apply them lightly; complex learning, synthesis, design, mentoring, review, and planning answers should make the structure, relevance-first framing, pacing checks, and one to three next actions more visible.

Cognitive Adaptation should not store diagnostic labels about the user unless the user explicitly asks the agent to remember one. Durable user-model entries should be behaviorally grounded, such as "prefers chunked answers," "benefits from re-anchoring after pauses," or "likes concrete next actions," rather than recording "has ADHD" as an inferred fact.

### Session metadata (bridge to Slice C; scaffold now, runtime integration pending)

`session_meta.jsonl` records lightweight session summaries:

```json
{
  "session_id": "sess_20260702_001",
  "started_at": "2026-07-02T15:00:00Z",
  "ended_at": "2026-07-02T15:22:00Z",
  "message_count": 8,
  "inferred_goal": "study / learning",
  "topic_stability": 0.85,
  "completion_status": "ended_naturally",
  "question_depth_trajectory": "deepening"
}
```

The current implementation may include the path and helper scaffold, but production session metadata behavior is not complete until runtime/application code supplies real session boundaries, inactivity detection, explicit-end detection, schema validation, and session segmentation on intentional pivots.

Fields:
- `session_id` — stable identifier
- `started_at` / `ended_at` — session boundaries
- `message_count` — engagement volume
- `inferred_goal` — from `_infer_session_goal()`
- `topic_stability` — 0.0–1.0, ratio of messages on primary topic
- `completion_status` — `ended_naturally`, `abandoned`, `timeout`
- `question_depth_trajectory` — `deepening`, `shallowing`, `stable`

Session metadata writes validate this schema at the append boundary. `topic_stability` must stay within 0.0–1.0, `completion_status` must be one of the declared values, and `question_depth_trajectory` must be `deepening`, `shallowing`, or `stable` unless a future ADR introduces an explicit `unknown` state.

The writer should accept runtime-provided `started_at` and `ended_at` values rather than deriving both at append time. `ended_at` may default to the current time if omitted, but `started_at` must come from the runtime session state. Writes should validate that `started_at <= ended_at` so future engagement inference can use real duration.

`topic_stability` measures drift within a session goal, not whether the user intentionally changed goals. When the user explicitly pivots or begins a clearly different task, the runtime should close the previous session segment and start a new one rather than lowering the previous segment's stability score.

The session metadata file is written by runtime/application code when the user explicitly ends a session or when the runtime detects inactivity/timeout. The LLM may help infer fields such as goal or question-depth trajectory, but it should not be instructed to directly call the write helper because session boundaries, timestamps, message counts, abandonment, and timeout are runtime facts. It enables the future passive engagement model (Slice C) without requiring real-time inference.

Explicit endings should use `completion_status: "ended_naturally"`. Runtime inactivity should use `completion_status: "timeout"` or `completion_status: "abandoned"` when the runtime can distinguish them. A timeout must not be recorded as a natural ending.

Attention Drift Recovery should be triggered by runtime-provided elapsed-time context, not by the LLM guessing from conversation content. A conservative default is to re-anchor after more than 30 minutes of inactivity in the same thread, and always after a cross-day resume. Short gaps of a few minutes should not trigger re-anchoring.

## Rationale

- Instruction-only ADHD adaptation gives immediate benefit with zero infrastructure
- Session metadata follows the same append-only JSONL pattern as `interaction_log.jsonl`, `candidate_signals.jsonl`, and `personal_notes.jsonl`
- Session metadata is runtime-owned rather than model-called, so operational records reflect actual session boundaries instead of opportunistic tool calls
- The instruction establishes the behavioral baseline; the metadata enables future personalization
- This respects Hybrid Learning Control (ADR 0052): the instruction is automatic (provisional), session data enables future durable adaptation

## New Glossary Terms

- **Cognitive Adaptation** — agent behavior adjustments that account for cognitive traits like attention variability, working memory constraints, and motivation drivers
- **Session Metadata** — lightweight per-session summary fields (timing, topic stability, completion status) enabling future engagement inference without real-time tracking
- **Attention Drift Recovery** — the agent's pattern for re-engaging after a pause: acknowledge the gap, offer the anchoring context, ask whether to continue or pivot

## Consequences

- ADHD-aware instruction paragraph added to `agent.py`
- `SESSION_META_PATH` and `_write_session_meta()` scaffold added to `agent.py`, with production writes owned by runtime/application code rather than the LLM tool loop
- Runtime integration remains required for real session boundaries, validation, inactivity detection, and pivot-based session segmentation
- `CONTEXT.md` updated with Cognitive Adaptation glossary terms
- Session metadata infrastructure ready for future passive engagement model (Slice C)
