# ADR 0023: Three-Lane Note Answers

When answering with both papers and Personal Notes, the agent will separate Evidence, Your Notes, and Inference. Evidence contains cited paper passages; Your Notes contains relevant Personal Notes or Note Cards; Inference contains the agent's labeled synthesis between them. This preserves evidence-first behavior while allowing the user's own thinking to shape research synthesis.

## Considered Options

- Blend notes and papers into one answer: fluent, but risks treating personal reflections as evidence.
- Use notes only for ranking, never visible in answers: safe, but hides why the answer is personalized.
- Separate Evidence, Your Notes, and Inference: selected because provenance stays visible without losing synthesis.
