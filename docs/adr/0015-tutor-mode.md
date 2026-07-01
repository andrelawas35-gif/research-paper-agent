# ADR 0015: Tutor Mode

## Status

Accepted

## Context

The research paper agent already has six explicit modes (Reader, Grill, Builder, Taste, Artifact, Profile) defined in ADR 0011. The agent ingests papers, extracts concepts, tracks user interests via a concept graph, and runs adaptive grill sessions. These capabilities are the backbone of a tutor: teaching concepts from papers, quizzing the user, and adapting the curriculum to mastery.

A separate tutor agent would duplicate the entire ingest/search/user-model/concept-graph stack. A tutor mode within the existing agent reuses all of it.

## Decision

Add a **Tutor Mode** to the research paper agent. The tutor uses an explain-then-quiz loop, grades free-text answers via LLM, tracks concept-level mastery, and alternates between weak-area drilling and interest-aligned exploration. The user can steer the curriculum at any point by naming a concept or topic.

### Components

| Component | Decision |
|-----------|----------|
| Teaching posture | Explain-then-quiz by default; adaptive drill when quiz history exists |
| Progress tracking | `tutor_progress.json` (concept-level mastery summary) + `tutor_sessions.jsonl` (full answer audit trail) |
| Answer grading | LLM-mediated free-text grading (CORRECT/INCORRECT + mastery hint). Not multiple-choice — the LLM's judgment handles nuanced "kinda right" answers |
| Curriculum pathing | Alternating: one weak-concept drill, then one interest-aligned concept. User override at any point |
| Tool surface | One new tool (`record_tutor_answer`), one inspect tool (`get_tutor_progress`), two internal helpers (`_next_concept`, `_grade_answer`). Reuses `search_evidence`, `adaptive_grill`, `concept_graph.rank/link` |
| Storage | `user_model/tutor_progress.json` + `user_model/tutor_sessions.jsonl` — same pattern as `profile.json` + `interaction_log.jsonl` |

### Tutor loop

```
pick concept (_next_concept)
  → teach it (search_evidence + LLM)
    → ask question (adaptive_grill)
      → grade answer (_grade_answer via LLM)
        → record progress (record_tutor_answer)
          → pick next concept (_next_concept)
```

Concept graph edges are strengthened on every tutor answer (correct boosts the concept, incorrect also counts as engagement), making the graph smarter about what the user has studied.

## Consequences

- The agent gains a seventh mode without new dependencies, new files beyond JSON artifacts, or new modules.
- Tutor progress decays naturally: concepts not revisited for 30+ days lose mastery weight (via the existing concept graph decay mechanism).
- LLM grading adds one extra API call per question — negligible cost at current DeepSeek pricing.
- The tutor's quality depends on the LLM's grading accuracy. Misgraded answers could create incorrect mastery signals, but the audit log (`tutor_sessions.jsonl`) makes every grade inspectable and correctable.

## Alternatives Considered

- **Separate tutor agent**: cleaner separation of concerns, but duplicates the entire ingest/search/user-model stack. Rejected — mode-based routing is simpler and already designed in.
- **Multiple-choice only scoring**: deterministic, no extra LLM calls. Rejected — too limiting for conceptual understanding questions.
- **Pure Socratic tutoring**: never gives answers, only asks. Rejected — explain-then-quiz is more broadly useful and the user can request Socratic mode explicitly.
- **Concept dependency modeling**: would enable true curriculum sequencing (teach embeddings before vector search). Rejected for this pass — the concept graph doesn't model dependencies, and building that is a separate architectural decision.
