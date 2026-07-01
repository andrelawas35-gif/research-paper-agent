# ADR 0038: Typed Concept Sources

The Concept Graph will add typed concept source references for Papers, Personal Notes, and Note Cards instead of overloading `source_papers` with note IDs. Existing `source_papers` can remain for backward compatibility, while note-aware graph behavior uses explicit source types to keep provenance clear.

## Considered Options

- Store note IDs in `source_papers`: easy, but semantically wrong and confusing for future graph code.
- Maintain a separate notes-only concept index: clean, but weakens cross-source backlinks.
- Add typed concept source references: selected because it keeps papers and notes connected through Concepts while preserving source type.
