# ADR 0027: Concept-Derived Backlinks

Backlinks for Personal Notes will be derived from shared Concepts in the Concept Graph before supporting manual wiki-style links. A note can show related notes, papers, and user interests because they connect through the same concept vocabulary, making backlinks an agent-native graph view rather than a manual linking chore.

## Considered Options

- Manual `[[wiki links]]` first: familiar for Obsidian users, but depends on careful user-authored links.
- Concept-derived backlinks first: selected because the agent already extracts concepts and can connect notes to papers automatically.
- Both from the start: useful eventually, but more surface area than the first implementation needs.
