# ADR 0035: Initial Note Corrections

The first Personal Notes implementation will include three correction paths: edit a Personal Note's title/text/tags, reject an extracted Note Card, and reject a linked Note Concept. These cover the most common extraction mistakes after Save-First Note Extraction without requiring a full note-editing interface or automatic concept merging in the first pass.

## Considered Options

- No correction tools initially: fast to build, but makes extraction mistakes sticky.
- Full editing for every derived field: powerful, but too much surface area before the workflow is proven.
- Three focused correction paths: selected because they make the save summary actionable while keeping the first implementation compact.
