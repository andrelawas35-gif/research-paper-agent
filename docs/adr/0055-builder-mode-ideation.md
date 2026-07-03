# ADR 0055: Builder Mode — Cohesive Idea Formation

Builder Mode is a Socratic ideation partner for turning loose ideas into more cohesive designs. Its success condition is not implementation by default; it is a clearer thesis, a component map that hangs together, visible trade-offs, labeled provenance, and a chosen next move.

## Decision

Builder Mode activates for design, invention, comparison, brainstorming, and stress-testing requests, including explicit "Builder Mode" prompts. It should not hijack direct implementation, paper reading, tutoring, or note-capture requests.

Builder Mode follows this flow:

1. **Clarify** — ask one high-leverage Socratic question about the most important missing constraint. Ask one additional clarifier only if idea generation would otherwise be materially wrong.
2. **Generate** — produce three competing Builder Ideas by default: a conservative fastest path, a robust long-term architecture, and a weird-adjacent high-upside experiment. Use five ideas only for broad or explicitly exploratory brainstorming.
3. **Recommend and choose** — recommend one idea with a brief rationale, then let the user choose an idea, combine pieces, sharpen the set, or pick another next move.
4. **Co-author** — treat cohesive ideas as co-authored with the user. Check what feels alive, wrong, worth preserving, or closest to the user's intent.
5. **Grill when useful** — after the user chooses an idea or component, stress-test decision-bearing components one at a time. The preferred sequence is purpose, boundary, risk, trade-off, evidence/provenance, user fit, and next-move test, but stop probing once the major uncertainty is resolved.

A Builder Idea includes a name, thesis, 3-6 decision-bearing components, why it fits the user, key risks, at least one idea-fitting novel move, and a Builder Next Move. The Builder Thesis is the spine: it explains what the idea is really betting on, why components belong together, what novelty must serve, and what the grill should test.

Builder Mode optimizes for coherence first, personal fit second, grounding third, and idea-fitting novelty fourth. Novelty is required, but it must strengthen the idea rather than add unrelated cleverness. Weird-adjacent ideas may bend framing, workflow, architecture, or user surface, but must still respect hard user constraints.

Knowledge sources are layered per ADR 0003 (Ground Before Transforming) and ADR 0023 (Three-Lane Answers). Components get Ideation Provenance tags: `[from your notes]`, `[cited: source]`, and/or `[inference]`. `[cited: source]` requires retrieved evidence. Personal Notes can shape taste, vocabulary, constraints, and components, but they are not factual evidence. Relationship Management data may shape Builder Mode only when the idea is relationship-related or the user explicitly asks to use it.

Builder Mode can preserve unresolved forks during exploration, but must converge before artifact or implementation handoff, or explicitly mark a fork as unresolved. If an idea is weak or incoherent, the agent should preserve the user's core desire, name the conflict, and offer stronger framings. It may say an idea is not worth pursuing in its current form, but should include a salvage path.

Builder Mode remains instruction-only for now. It uses existing profile, notes, evidence, tutor-progress, and code-inspection tools rather than adding a dedicated `generate_builder_ideas` tool. A tool becomes justified only if idea format, provenance tagging, selected-idea tracking, or resumability proves inconsistent.

## Rationale

- Builder Mode already exists in the instruction, so this sharpens its contract without creating another mode.
- The user wants the agent to help formulate ideas and make them cohesive, not merely push every idea toward implementation.
- The one-question clarification budget avoids questionnaire sprawl while still giving the agent enough context to generate useful options.
- Component-level provenance extends the Three-Lane Answer pattern into design work without making every sentence over-labeled.
- Instruction-only implementation keeps the first version lightweight while the interaction pattern stabilizes.

## Consequences

- Builder Mode should update `agent.py` with one concise instruction replacement after this ADR is accepted.
- Builder sessions are conversational by default; no durable builder session store is added in the first version.
- Builder Mode does not auto-save brainstorms or infer durable preferences. After a meaningful cohesion point, it may offer a specific artifact such as a Personal Note, PRD, issue list, ADR, research queue, or parked idea card.
- When the idea targets this codebase, Builder Mode should inspect current code, docs, tests, and worktree constraints. For external ideas, it can stay conceptual unless implementation is requested.
- If output drift appears in practice, add a dedicated builder tool or session store in a later slice.
