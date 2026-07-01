# ADR 0031: Markdown Note Mirror Shape

Markdown Note Mirrors will include frontmatter, the original note text, extracted Note Cards, Concepts, and related links. The mirror is readable and Obsidian-friendly, but it declares the canonical Notes Store path so future readers understand that structured agent state lives in JSONL.

## Considered Options

- Plain Markdown body only: readable, but weak for browsing and round-trip inspection.
- Full generated Markdown with frontmatter and derived sections: selected because it supports Obsidian-like use while preserving structured provenance.
- Treat Markdown as canonical: rejected because human edits would make IDs, extracted cards, graph links, and migrations brittle.
