# Best-Effort Projection Updates First

The first Projection Plumbing implementation will use synchronous Best-Effort Projection Updates after canonical writes, while preserving typed provenance for a future Projection Rebuild Path. Canonical writes must remain successful even if projection updates fail, because notes, relationship events, tutor progress, and user-model records are the source of truth.

## Considered Options

- Append-only projection events with replay from the start: more robust and auditable, but larger than the next slice needs and likely to slow down the write-path repair.
- Synchronous best-effort projection updates with typed provenance: selected because it fixes the immediate stale-graph problem while keeping the implementation small and leaving a rebuild path open.

## Consequences

- Tool wrappers should call projection updates after canonical writes succeed and report projection status without treating projection failure as total tool failure.
- Projection records should include `source_type`, `source_id`, and enough concept/person/note context to support later replay or rebuild.
- A later maintenance slice can add explicit projection event logs, rebuild tooling, and stale-projection diagnostics if best-effort updates prove insufficient.
