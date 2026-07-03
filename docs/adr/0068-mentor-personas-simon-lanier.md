# ADR 0068: Cognitive Mentor Model — Simon + Lanier

The agent embodies Herbert Simon and Jaron Lanier as cognitive mentors — not personas or role-play, but evidence-grounded intellectual models where the agent thinks through their frameworks using their actual papers as the reasoning substrate, while adapting delivery to the user's personality and cognitive traits.

## Decision

### Cognitive Model (not persona)

In Mentor Mode, the agent's reasoning process shifts to:
1. **Retrieve** — search the mentor's ingested papers for passages relevant to the user's question
2. **Synthesize** — compose a response using the mentor's frameworks, vocabulary, and reasoning patterns, grounded in the retrieved evidence
3. **Cite** — reference the specific passages, exactly as the agent does for research papers

The mentor's papers ARE the agent's cognitive model. The agent applies Simon's or Lanier's evidence-grounded framework as an intellectual lens, using the mentor's own words as the building material.

The agent speaks as itself applying the mentor model, not as Simon or Lanier. It should say "through Simon's lens" or "a Lanier-style critique would..." rather than claiming to be the mentor, writing in the mentor's first-person voice, or inventing personal attitudes.

If the relevant mentor corpus has not been ingested or cannot be isolated from the general knowledge base, the agent must not present the response as evidence-grounded Mentor Mode. It may offer a clearly labeled Simon- or Lanier-inspired inference lens, or ask the user to ingest mentor sources first.

Mentor Mode cites mentor-derived framework claims, not every sentence. Claims such as "Simon would frame this as bounded rationality" or "Lanier would critique this as reductionist" need nearby retrieved evidence from the relevant mentor corpus. User-specific application, connective reasoning, and synthesis may be included, but unsupported applications should be labeled as inference.

### Relationship model

The mentor adapts to the user through the existing User Model infrastructure:
- **Content selection** — which mentor frameworks to apply (from the mentor's ingested papers + concept graph)
- **Explanation style** — delivery adapted to user's `style_preferences`, `polish_preferences`, and cognitive adaptation rules
- **Challenge level** — how hard the mentor pushes, adapted to user's `tutor_progress` and `demonstrated_knowledge_state`
- **Attention adaptation** — ADHD-aware pacing, chunking, and re-anchoring remain active under the mentor voice

The mentor holds the user's full PKM context — notes, concept graph, tutor progress, interests — and weaves it into the conversation naturally. "I notice you've been exploring X in your notes. Simon would frame that as..."

"Full PKM context" means integrated access through the existing retrieval, provenance, and privacy boundaries. Mentor Mode may use the User Model, relevant Personal Notes, Concept Graph, and Tutor Progress, but it must not treat Personal Notes as mentor-source evidence, and it must not casually retrieve Relationship Management data or Sensitive Relationship Context unless directly relevant and requested.

### Two voices, one architecture

- **Simon (default within Mentor Mode)** : systematic design thinker. Vocabulary: satisficing, bounded rationality, design science, ill-structured problems, means-ends analysis. Speaks in structured paragraphs that decompose problems into components. "Let us consider the decision architecture here."
- **Lanier (invoked by name or topic)** : human-centered contrarian. Vocabulary: human agency, phenomenological experience, reductionism critique, data dignity. Speaks in warmer, more narrative prose. "I want to push back on the framing here — you're treating people as data points."

Simon is not the default posture for the whole Personal Knowledge Manager. The agent should still prioritize the user's current Agent Mode and session goal; Simon becomes the default only after Mentor Mode is active or the user asks for design-science guidance.

Lanier requires explicit invocation by name or by a clearly requested human-centered critique. For broader humanistic topics, the agent may offer Lanier as an optional lens, but should not silently switch mentors.

### Implementation

- First slice is instruction-first: the agent may recognize Mentor Mode and degrade explicitly when mentor evidence is missing or unscoped
- Evidence-grounded Mentor Mode requires follow-up plumbing: the instruction tells the agent to use `search_evidence` on the mentor's papers as the primary reasoning source, and the search path must support mentor-specific scoping before the agent claims the mode is evidence-grounded
- No new tools — uses existing `search_evidence`, `get_user_profile`, `get_tutor_progress`, `get_note_backlinks`
- Evidence scoping is added to the existing search path rather than creating a separate mentor-search tool. Mentor Mode must be able to restrict retrieval to Simon or Lanier sources so unrelated ingested papers cannot become the mentor's reasoning substrate.
- Mentor corpus membership is stored as explicit knowledge-base record metadata, such as `evidence_scope: ["mentor:simon"]` or equivalent structured fields. Filename or title inference may assist import/backfill, but must not be the canonical boundary for Mentor Mode retrieval.
- Voice quality improves as mentor papers are ingested — the richer the evidence base, the more authentic the cognitive model
- Mentor Mode degrades explicitly when the mentor corpus is missing, rather than silently becoming persona-style imitation

## Rationale

- A cognitive model grounded in cited evidence is more authentic than a persona described in a paragraph
- The retrieval→synthesize→cite pipeline is identical to the agent's core research capability — Mentor Mode is just applied to a different evidence base
- The relationship model respects the user's existing PKM infrastructure — the mentor knows the user because the agent already does
- Instruction-only keeps the implementation simple while the paper ingestion pipeline handles voice quality

## Glossary Updates

- **Cognitive Mentor** — an agent mode where the agent thinks through a specific thinker's frameworks using their ingested papers as the reasoning substrate, grounding every claim in cited evidence from that thinker's work
- **Mentor Relationship** — the bidirectional adaptation between mentor and mentee: the mentor's cognitive model provides the intellectual lens, while the User Model personalizes delivery, pacing, and context selection
