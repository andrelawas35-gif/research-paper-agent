# Expose Projection Status In Tool Results

Tools that perform Best-Effort Projection Updates should expose a compact `projection_status` field in their result. Projection failures should not roll back successful canonical writes, but they should be visible immediately so stale retrieval, backlinks, recommendations, or audits can be explained without digging through hidden logs.

## Considered Options

- Log projection failures only: keeps tool results tidy, but makes stale graph behavior mysterious when the projection fails.
- Expose compact Projection Status: selected because it preserves best-effort semantics while giving the user and future debugging tools an inspectable signal.

## Consequences

- Tool results for note, tutor, grill, relationship, and future projection-aware writes should include `projection_status` when projection work is attempted.
- `projection_status` should be small and stable, such as `{status, updated_edges, skipped_reason, error}` rather than a full graph dump.
- User-facing responses can usually omit successful projection status, but failed or skipped projection updates should be easy to surface when explaining stale retrieval or audit output.
