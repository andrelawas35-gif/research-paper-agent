# ADR 0028: Versioned Personal Notes

Personal Notes will be editable, but edits will preserve version history in the Notes Store. The current note body, title, and tags can change, while prior versions remain auditable so graph links, extracted Note Cards, and Candidate Signals can be traced back to the wording that produced them.

## Considered Options

- In-place edits only: simple, but makes graph behavior harder to explain later.
- Immutable notes only: auditable, but too rigid for everyday note-taking.
- Editable notes with append-only versions: selected because it keeps capture flexible while preserving provenance.
