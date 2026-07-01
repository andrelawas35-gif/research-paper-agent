# ADR 0045: Knowledge Management Loop

Personal Notes are one input channel into a broader Knowledge Management system, not the whole system. The agent should self-learn through local state updates across Personal Notes, Interaction Signals, Candidate Signals, the User Model, Concept Graph, and Tutor Progress so future retrieval, questions, explanations, and recommendations better match the user's quirks, intelligence, interests, and knowledge level.

The agent may make itself smarter by updating local knowledge state and behavior rules, but it must not silently rewrite its own code. Code changes remain Improvement Proposals until the user explicitly approves implementation.
