# ADR 0053: Knowledge Self-Audit Slice

The Knowledge Self-Audit slice replaces the basic `self_improvement_audit` tool with a full inspectable knowledge view and an explicit correction surface.

## Decision

`knowledge_self_audit` aggregates seven data sources into one view:

1. **Confirmed** — explicit preferences, avoidances, interests, and adaptation rules from `profile.json`
2. **Candidate Signals** — inferred but unconfirmed signal types with counts from `candidate_signals.jsonl`
3. **Concept Graph** — strongest, stale, and rejected concepts, plus merge suggestions when two concepts share ≥ 3 neighbors
4. **Tutor State** — mastered and weak concepts from `tutor_progress.json`
5. **Notes** — total note count and recent concept frequencies from `personal_notes.jsonl`
6. **Interaction Summary** — total interaction count and recent tag distribution from `interaction_log.jsonl`
7. **Correction Actions Available** — four actions the user can steer with

`self_audit_correction` supports the four correction actions from ADR #0050:

| Action | Effect |
|---|---|
| `confirm_signal` | Promotes a candidate signal into a durable preference, interest, or rule |
| `reject_signal` | Logs a rejection entry so the signal type stops resurfacing |
| `downgrade_preference` | Lowers confidence by 0.3 on a matching profile entry |
| `suppress_concept` | Calls `concept_graph.reject_concept` to suppress a concept in ranking |

`concept_graph.reject_concept` sets all matching interest→concept edges to `"rejected"` type, drops their weight to 10%, and records the rejection timestamp and reason.

## Rationale

- The old `self_improvement_audit` only checked profile gaps and gave static recommendations. The new audit is a live inspectable view of the agent's complete knowledge state.
- Separating audit (read) from correction (write) follows the same pattern as ADR #0048's automatic-vs-confirmed adaptation split.
- The correction actions give the user explicit steering control over the Self-Learning Knowledge Loop (ADR #0045), matching the hybrid learning control pattern from ADR #0052.
- Merge suggestions use neighbor-overlap heuristics (≥ 3 shared neighbors) rather than embedding similarity to stay dependency-free.

## Consequences

- The agent instruction now references `knowledge_self_audit` and `self_audit_correction` explicitly.
- `concept_graph.reject_concept` is a new public function with token-matched concept key lookup.
- The `self_improvement_audit` tool is removed — all references now use `knowledge_self_audit`.
- test_agent.py adds 8 new tests covering audit structure, profile data surfacing, all four correction actions, and error handling.
