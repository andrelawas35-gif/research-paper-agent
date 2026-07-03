# Concept Graph As Typed Knowledge Projection

The Concept Graph will be a rebuildable typed projection over separate canonical stores, not the canonical owner of papers, Personal Notes, People, Relationship Events, User Model entries, or Tutor Progress. This preserves privacy, deletion, correction, and provenance boundaries while still allowing graph-powered ranking, backlinks, retrieval, questioning, reconnection, and synthesis across domains.

## Considered Options

- Make the Concept Graph the canonical typed knowledge graph: simpler traversal, but too much ownership moves into one file and relationship/note deletion semantics become harder to reason about.
- Keep separate stores and use the Concept Graph as a lightweight projection: selected because the Personal Knowledge Manager already has distinct stores with different sensitivity, audit, and correction rules.

## Consequences

- Future graph implementation should write typed source references such as `paper`, `personal_note`, `note_card`, `person`, `relationship_event`, `user_interest`, and `tutor_progress` rather than overloading `source_papers`.
- Public graph inspection should expose projection nodes and edges while keeping canonical records in their owning stores.
- The knowledge loop should coordinate projection updates after canonical writes, but canonical writes must not depend on the graph being perfectly current.
