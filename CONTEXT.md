# Context Glossary

## Research Paper Agent

A local Google ADK agent that reads papers, extracts grounded concepts, answers questions with citations, and adapts to the user's recurring research interests and communication style.

## Paper

A source document placed in `papers/` for ingestion. Supported forms are `.txt`, `.md`, and optionally `.pdf`.

## Evidence Passage

A short, cited text span extracted from a paper. Evidence passages are the unit used for grounded answers.

## User Model

Local state that represents the user's explicit preferences, recurring interests, phrasing patterns, and useful adaptation rules.

## Interaction Signal

An observation drawn from a user message or feedback event. Interaction signals can suggest interests, question types, tone preferences, grammar patterns, or recurring workflows.

## Adaptation Rule

A user-facing behavior the agent should apply because it fits the user, such as preferring concise answers, asking fewer clarifying questions, or comparing papers by assumptions.

## Self-Improvement

The agent's local process of reviewing interaction signals, updating the User Model, and changing future behavior through tools and instructions. It does not rewrite code by itself.

## Adaptive Grill

A one-question-at-a-time interview loop where the next question is selected from both the User Model and the ingested text.

## Personalized Recommendation

A suggested next action that explains which user preference, interest, or text passage caused the suggestion.

## Text Understanding

The agent's source-grounded view of an ingested paper, represented by concepts, notes, evidence passages, and citations.

## Working Knowledge

Research material transformed into reusable understanding, personal questions, and agent-building ideas the user can act on.

## Grounded Transformation

Turning paper evidence into personal recommendations only after the source claim, support, and limitation are understood.

## Research Taste

The agent's ability to judge whether a paper is worth skimming, deep study, comparison, or discard for the user's current goals.

## Adjacent Possibility

A nearby idea the user did not directly ask for, surfaced because the source text strongly suggests it may matter to the user's goals.

## Evidence-First Pushback

A warm challenge when the user's interpretation, desired workflow idea, or stated goal goes beyond what the paper supports.

## Candidate Signal

A provisional preference or interest inferred from exploratory answers, kept weaker than an explicit instruction until it repeats or the user says to remember it.

## Recommendation Confidence

A plain-language label that says how strongly a personalized recommendation is supported by citations, user goals, and inference.

## Session Artifact

A compact durable output from a meaningful research interaction, such as concept cards, decision notes, open questions, agent-building ideas, or a reading queue.

## Artifact Offer

A specific proposal for a Session Artifact that names the intended shape before the agent creates it.

## Agent Mode

A named operating posture that tells the agent which research behavior to emphasize, such as reading faithfully, grilling, building, judging taste, producing artifacts, or updating the user profile.

## Session Goal

The user's current task or purpose for a research interaction, which takes priority over long-term profile preferences.

## Goal Clarification

A single question the agent asks only when the session goal is ambiguous enough to materially change the output.

## Improvement Proposal

A suggested change to the research agent, supported by evidence and confidence, that requires explicit approval before any code is modified.

## Concept Graph

A local bipartite graph connecting User Interests to Paper Concepts, stored in `user_model/concept_graph.json`. Edges carry a type (ingest, engaged, saved), a weight, a source paper reference, and a last-engaged timestamp. The graph drives personalized grill question ranking and paper-brief annotations.

## Graph Edge

A directed connection from a User Interest to a Paper Concept. Three edge types exist: **ingest** (passive keyword match created when a paper is ingested — never decays, weak signal), **engaged** (created or incremented when the user answers a grill question about the concept — decays after 30 days without re-engagement, drops to zero after 60), and **saved** (created when the user explicitly says to remember something — never decays, strongest signal).

## Concept Match

The agent's annotation of a paper concept with an interest-match label (high/medium/low) derived from the Concept Graph. Used in paper briefs to signal relevance to the user's stated interests.

## Tutor Mode

An Agent Mode where the agent teaches paper concepts through an explain-then-quiz loop, grades free-text answers via LLM, and adapts the curriculum to the user's mastery level. Defaults to alternating between weak-area drilling and interest-aligned exploration, with the user able to steer at any time.

## Tutor Session

A durable teaching interaction tracked in `user_model/tutor_progress.json` (concept-level mastery summary) and `user_model/tutor_sessions.jsonl` (full answer audit trail). Each entry records the concept, question, user answer, correctness verdict, and an optional mastery hint.

## Mastery Level

A per-concept score derived from `times_correct / max(1, times_asked)` stored in the Tutor Progress file. Concepts with mastery below 0.5 are considered weak and prioritized for drilling; concepts at 1.0 are considered mastered and deprioritized.

## Answer Grading

An internal LLM call that judges a free-text tutor answer against the cited passage, returning CORRECT or INCORRECT with a one-sentence reason and an optional mastery hint (e.g., "correct but confused retrieval with generation"). Not exposed as a user-facing tool.

## Curriculum Pathing

The tutor's concept-selection strategy. Alternates between the lowest-mastery concept (weak-area drilling) and the highest-interest unmastered concept (engagement). The user can override at any point by naming a concept or topic.
