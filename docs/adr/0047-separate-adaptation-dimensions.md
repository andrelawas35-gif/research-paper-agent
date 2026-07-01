# ADR 0047: Separate Adaptation Dimensions

The agent will adapt content selection, explanation style, and challenge level as separate dimensions. A user may prefer concise answers while still wanting advanced questions, or may be expert in one concept while needing scaffolding in another. Keeping these dimensions separate prevents the Self-Learning Knowledge Loop from reducing the user's intelligence or preferences to one global level.

## Considered Options

- One global user sophistication score: simple, but inaccurate and easy to overfit.
- Separate dimensions for content, style, and challenge: selected because it lets the agent adapt more precisely to task, concept, and user preference.
