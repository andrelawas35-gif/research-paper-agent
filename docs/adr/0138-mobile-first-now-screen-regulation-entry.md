# ADR 0138: Mobile-first Now screen with Regulation entry state

- Status: Accepted
- Date: 2026-07-12

## Decision

Begin the PWA design with a sparse, mobile-first Now screen whose primary action opens Regulation Mode. The screen provides orientation and a few deliberate next actions; it does not use mood scores, streaks, gamification, or unsolicited psychological interpretation.

## Rationale

This first slice tests the highest-value interaction: helping the user pause and choose a values-consistent next action while establishing the responsive navigation and ADHD-friendly density model for the wider PKM.

## Consequences

The first frontend implementation should preserve the Now/Regulation hierarchy and treat the visual tokens as local PKM tokens, even though the Figma file subscribes to Material 3 and Simple Design System libraries.
