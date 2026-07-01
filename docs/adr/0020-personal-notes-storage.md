# ADR 0020: Personal Notes Storage

Personal Notes will be stored canonically as structured JSONL records under the User Model, with optional Markdown mirrors for Obsidian-like reading and linking. JSONL gives the agent stable IDs, extracted Note Cards, timestamps, graph-link metadata, and safer migrations; Markdown gives the user portable files without making human-edited prose the only source of structured agent state.

## Considered Options

- Markdown only: more Obsidian-like, but brittle for IDs, card extraction, graph updates, and migrations.
- JSONL only: simplest for the agent, but loses the human-readable vault feel the feature is meant to provide.
- JSONL canonical with Markdown mirror: selected because it separates durable agent state from portable note presentation.
