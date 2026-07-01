# ADR 0043: Personal Notes Vertical Slices

Personal Notes will be implemented as thin vertical slices rather than one large feature drop. The slices should start with local save/list/get/search, then add extraction, Markdown mirrors, Concept Graph note signals and typed sources, Three-Lane Answers, Adaptive Grill and Tutor ranking, and finally edit/reject/soft-delete/sync polish.

## Considered Options

- Build the whole notes system before exposing it: coherent, but high risk and hard to test incrementally.
- Ship isolated infrastructure first: tidy, but not useful until many layers are complete.
- Deliver vertical slices: selected because each step creates usable behavior while keeping graph and learning integrations testable.
