# ADR 0037: Personal Note Record Schema

The canonical Notes Store will use compact Personal Note Records with `schema_version`, stable `note_id`, title, text, timestamps, soft-delete state, User Tags, Suggested Tags, extracted Note Cards, linked Concepts, Candidate Signals, Markdown mirror path, and versions. This schema supports capture, search, correction, soft-delete, Markdown mirrors, Concept Graph integration, and auditability without requiring a database in the first implementation.

## Considered Options

- Minimal text-only records: simple, but unable to support graph links, corrections, and Markdown mirrors cleanly.
- Fully normalized multi-file records: extensible, but more complexity than the first implementation needs.
- Compact JSONL records with nested cards and versions: selected because it matches the existing local-file style while leaving room for migration.
