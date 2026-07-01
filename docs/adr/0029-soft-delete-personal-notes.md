# ADR 0029: Soft-Delete Personal Notes

Personal Note deletion will be soft-delete by default. A soft-deleted note is hidden from normal search/list results and excluded from grill, tutor, and personalization ranking, but remains auditable so historical graph links and Candidate Signals can be explained. Permanent purging can be added as a separate explicit destructive operation.

## Considered Options

- Hard-delete by default: simple, but removes provenance for graph and signal history.
- Never delete: auditable, but frustrating for normal note management.
- Soft-delete by default with later purge: selected because it balances everyday cleanup with traceability.
