# Projection Plumbing Before Audit Contract

The next graph implementation slice should wire Projection Plumbing before expanding the graph inspection and Knowledge Self-Audit contract. Note save/edit/search, tutor answers, grill answers, and relationship events should first emit typed projection updates; then `get_concept_graph` and `knowledge_self_audit` can expose and consume the richer projected shape.

## Considered Options

- Fix graph inspection first: useful for visibility, but it risks designing an audit shape around incomplete or stale projection data.
- Fix Projection Plumbing first: selected because the audit should describe actual state flow, not an aspirational graph shape.

## Consequences

- The first implementation target is write coordination through canonical store wrappers and `_knowledge_loop_update`.
- The graph inspection contract should be revised only after typed projection updates exist for the main knowledge channels.
- Tests should prove that canonical writes survive graph update failures and that projection data is refreshed after successful writes.
