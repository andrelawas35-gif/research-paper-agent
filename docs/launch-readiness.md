# PKM PWA Launch Readiness

Status: **hardened production candidate; not approved for daily-use launch**.

The current release can be installed on one Oracle VM, built with Node 24 LTS
(enforcing Node 20.19+), reached privately through Tailscale, restarted without
losing durable Regulation sessions, and recovered from an encrypted Restic
backup using a separately held Regulation key. It does not claim high
availability.

## Verified in this slice

- Owner API authentication gates online Regulation and Privacy routes.
- Browser credentials are tab-scoped and the workspace has an explicit lock.
- Unauthenticated offline access is limited to the bundled Regulation protocol.
- Model unavailability degrades to deterministic guidance.
- Private drafts are memory-only and discard removes them from memory.
- Durable Regulation events are encrypted at rest and replay after restart.
- Caddy and FastAPI bind to loopback; Tailscale provides private HTTPS.
- Restic excludes live secrets and requires separately held recovery material.
- Backend tests, frontend tests, lint, production build, PWA generation, shell
  syntax, dependency audit, and a fresh-browser unlock failure are verified.

## Daily-use launch gates

Complete these in order; each item must add an automated test and operator
evidence before it can be marked done.

1. Replace production JSONL Regulation persistence with the ADR-selected SQLite
   WAL repository and enforce domain boundaries in repository adapters.
2. Store only the approved compact Regulation Record durably; purge raw trigger,
   facts, interpretation, emotion, and urge narrative after closure.
3. Encrypt each durable record with its own data-encryption key and prove that
   deleting the key makes live data and retained backup snapshots unreadable.
4. Replace the VM-resident live key file with the selected protected external
   key-provider flow, including startup failure and recovery tests.
5. Add expiring server-side owner sessions with recent-auth requirements for
   export, deletion, and key rotation.
6. Build a consented offline Orientation Snapshot containing confirmed values,
   personal rules, approved grounding actions, commitments, and regional safety
   resources. Add offline inspect/export/delete and deferred-capture behavior.
7. Install separate systemd units for web/API, background dispatcher, and the
   approved Discord rapid-entry path, or explicitly amend the ADR scope.
8. Prove duplicate-request handling, interrupted-write recovery, and a true
   clean-environment restore rather than replay through the live release.
9. Complete keyboard, focus, reduced-motion, responsive, weak-network, and three
   scripted Regulation walkthroughs on phone and desktop.
10. Rotate the previously exposed provider credential, then complete the
    seven-day shadow-use period without treating the app as an emergency service.

Do not relabel this candidate as daily-use ready until all ten gates are closed
or the governing ADRs are explicitly superseded.
