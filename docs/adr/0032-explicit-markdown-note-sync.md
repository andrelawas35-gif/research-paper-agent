# ADR 0032: Explicit Markdown Note Sync

Markdown Note Mirror edits will be imported into the canonical Notes Store only through an explicit sync or import action. The agent must not silently ingest Markdown edits during unrelated prompts, because accidental edits, formatter churn, or half-written notes could otherwise mutate the Concept Graph and personalization state unexpectedly.

## Considered Options

- Automatic sync on every run: convenient, but too surprising for a memory system.
- Never import Markdown edits: simple, but makes the mirror less useful as an editable vault.
- Explicit sync/import: selected because it lets the user edit Markdown while keeping graph changes intentional.
