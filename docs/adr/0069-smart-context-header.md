# ADR 0069: Smart Context Header

**Date:** 2026-07-02
**Status:** Accepted
**Supersedes:** None (new mechanism)

## Context

The agent stores durable state across six storage backends (user profile,
concept graph, personal notes, tutor progress, interaction log, session
metadata) but none of it is preloaded into the LLM's context on each turn.
The LLM must remember to call tools (`get_user_profile`,
`get_concept_graph`, `list_personal_notes`, etc.) to access any of this
state. In practice, this means the agent frequently starts conversations
with a blank slate — it doesn't know the user's interests, notes, or
learning patterns until it explicitly fetches them.

Additionally, there is no context-window guard. The ADK appends all prior
turns to the LLM's message list with no summarization or compression. For
models with large context windows (~128K tokens) this is adequate for most
sessions, but very long conversations can eventually overflow.

Finally, `session_meta.jsonl` exists as a future re-anchoring input, but
ADR 0067 makes session metadata runtime-owned rather than model-called.
The smart context header may read session metadata when present, but it
does not make the LLM responsible for writing session boundaries.

## Decision

**Inject a compact context header into the system instruction on every
turn**, using the ADK's `InstructionProvider` callable interface. The
header is built fresh each turn from the agent's durable state and
prepended to the static instruction body.

### Mechanism

1. **`_build_snapshot(ctx)`** — reads profile (interests, style, polish,
   avoidances, quirks), recent personal notes (last 5 with top concepts),
   concept graph (top 5 concepts by edge count), tutor progress (weak
   concepts), and prior session metadata (for re-anchoring). Formats
   everything into ~300-500 tokens.

2. **`_dynamic_instruction(ctx)`** — the `InstructionProvider` callable
   passed as `instruction=` to the ADK `Agent`. Called before every model
   request. Returns the snapshot header while the cache-stable static
   instruction body remains in `_STATIC_INSTRUCTION`.

3. **Context-window guard** — if the session has >80 events (user +
   model + tool turns), injects a stable compaction hint: "long session —
   lead with the most relevant insight, be concise, avoid recapping
   distant history." The hint must not include the exact event count,
   because that would modify system instructions on every later turn.

4. **Session metadata read-only use** — the header reads the latest
   `session_meta.jsonl` row when available and uses unfinished prior
   sessions to support re-anchoring. `_write_session_meta` remains an
   internal runtime helper and is not exposed in the LLM tool list.

### Header format

```
[context snapshot]
user: interests: X, Y; style: Z; polish: moderate; avoid: A; quirks: B
recent notes: Title1 [concept1, concept2] | Title2 [concept3]
top concepts: bounded_rationality(5), design_science(3)
weak concepts: reinforcement_learning, bayesian_inference
prior session: paper comparison (unfinished, msg count 12)
long session — lead with the most relevant insight, be concise, avoid recapping distant history
```

## Consequences

- **Positive**: The agent always knows who it's talking to, what notes
  are recent, what concepts matter, and what prior session was about —
  without requiring tool calls. Eliminates the "forgot to call
  get_user_profile" failure mode.
- **Positive**: Long sessions get a compaction hint before the context
  window fills up.
- **Positive**: Session metadata, when written by runtime/application
  code, becomes available to the header for future engagement-adaptive
  behavior across sessions.
- **Negative**: ~300-500 tokens added to every request. This is
  negligible for a 128K context window but worth monitoring.
- **Negative**: The snapshot is a point-in-time reading at instruction
  build time; if the agent updates state mid-turn (e.g., saves a note),
  the next turn will reflect it since `_dynamic_instruction` is called
  fresh.
- **Mitigation**: The snapshot fingerprint excludes session metadata and
  the long-session hint is fixed text, avoiding per-turn system
  instruction changes from runtime counters or boundary records.
- **Neutral**: The static instruction body is extracted into
  `_STATIC_INSTRUCTION` and no longer inline in the `Agent()` constructor.
  This is a refactor, not a behavioral change.

## Alternatives considered

1. **Auto-inject profile/notes/graph into every user message** — rejected
   because it pollutes the conversation history with system content that
   doesn't belong in the chat transcript.
2. **Tool-call reminders in the instruction** — rejected because the LLM
   already has these and still forgets. Preloading is more reliable.
3. **Separate summarizer agent** — rejected as overengineered for the
   current scale. Revisit when sessions routinely exceed 100+ turns.
