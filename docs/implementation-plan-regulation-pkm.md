# Regulation + Adaptive PKM Implementation Plan

**Status:** Ready for implementation  
**Architecture authority:** ADRs 0073–0137  
**Companion summary:** [grilling-session-summary.md](grilling-session-summary.md)  
**Initial runtime target:** Oracle VM, 1 OCPU, 6 GB RAM  
**First model route:** GPT-5 mini through a provider adapter

## How to use this document

Implement one ticket at a time. Do not combine tickets across milestones. Before starting a ticket, read the referenced ADRs and inspect the existing code. After each ticket, run its acceptance checks, record evidence, and commit the smallest coherent change.

Every implementation task must answer:

1. What user-visible or safety-relevant behavior changes?
2. Which domain rules are code-owned rather than model-owned?
3. Which data is persisted, where, with what sensitivity, and for how long?
4. What happens on restart, timeout, invalid input, duplicate request, and provider failure?
5. How can the Owner inspect, correct, export, and delete the result?

## Context-engineered implementation prompt

Use this prompt when delegating one ticket to an implementation agent:

```text
You are implementing exactly one bounded ticket in the Personal Knowledge Manager.

Repository: /Users/andrelawas/Documents/Codex/2026-07-01/add/research_paper_agent
Architecture authority: docs/adr/0073–0137; do not silently contradict an ADR.
Domain glossary: CONTEXT.md.
Product summary: docs/grilling-session-summary.md.
Current runtime target: Oracle VM, 1 OCPU, 6 GB RAM; no local LLM, no Redis,
no Celery, no standalone vector database, and no second agent.

Ticket: <PASTE ONE TICKET TITLE AND ACCEPTANCE CRITERIA>

Before editing:
1. Inspect the relevant existing modules, tests, configuration, and deployment files.
2. Identify the domain boundary, sensitivity class, persistence path, and failure modes.
3. State any ADR conflict or missing decision. Do not invent a new architecture.

While editing:
1. Keep model output advisory; code authorizes transitions, persistence, safety,
permissions, deletion, and delivery.
2. Preserve provenance and explicit user confirmation for identity-shaping or sensitive memory.
3. Keep Regulation data out of general retrieval and embeddings.
4. Make writes idempotent and restart-safe.
5. Use the smallest change that satisfies this ticket.

After editing:
1. Add or update focused tests before broad refactoring.
2. Run the ticket's exact verification commands.
3. Report changed files, behavior, test evidence, unresolved risks, and any
   follow-up ticket. Do not claim clinical efficacy or safety from passing tests.
```

## Milestone 1 — Foundation

### F1. Create shared event envelope

Add an append-only event envelope with event ID, owner ID, domain, event type, schema version, timestamp, sensitivity, provenance, payload checksum, and correlation ID.

Acceptance: malformed envelopes are rejected; IDs are unique; schema version is explicit; append and replay are deterministic; tests cover duplicate IDs and clock injection.

### F2. Add store boundaries

Create explicit repositories for operational data, general PKM data, and Regulation data. Do not let general search import the Regulation repository.

Acceptance: repository interfaces are typed; cross-store access requires an explicit authorized seam; tests prove Regulation records cannot enter general retrieval.

### F3. Add authenticated encryption and key loading

Implement AES-GCM or the approved authenticated-encryption primitive for sensitive records. Load keys from an external secret source; never commit keys or write plaintext sensitive payloads to logs.

Acceptance: tampering fails closed; wrong keys fail closed; key absence prevents startup of sensitive services; round-trip, rotation metadata, and deletion tests pass.

### F4. Add API, authentication, health, and audit seams

Create the minimal FastAPI service with Owner authentication, health/readiness endpoints, request correlation, and metadata-only access audit events.

Acceptance: unauthenticated requests cannot read or mutate stores; health does not reveal sensitive data; audit metadata omits content.

### F5. Add model-provider and spend adapters

Define a provider interface for structured generation, timeout, usage accounting, route selection, and failure classification. Configure GPT-5 mini as default and keep model IDs out of domain modules.

Acceptance: a fake provider supports deterministic tests; usage records include mode/workflow/model/input/output/cached tokens/cost; timeout and invalid-schema errors are typed.

## Milestone 2 — Offline Regulation

### R1. Define Regulation records

Create typed records for Trigger Session, facts, interpretations, emotions, urges, actions, outcomes, personal rules, and safety state. Store only explicit captures.

Acceptance: ordinary chat does not create a Regulation record; explicit capture does; each record has sensitivity and retention metadata.

### R2. Implement the state machine

Implement `start_trigger_check_in`, `record_trigger_response`, and `complete_trigger_check_in` with legal transitions, idempotency keys, and optimistic version checks.

Acceptance: invalid transitions fail without mutation; replay is safe; incomplete sessions can be resumed or expired; tests cover all states.

### R3. Implement deterministic emergency protocol

Build the offline flow: one-sentence event, known facts, imagined meaning, feared implication, current urge, reversible next action, and waiting interval. Keep language firm and non-reassuring.

Acceptance: provider absence still produces the flow; it never makes a truth verdict; it never suggests surveillance, retaliation, coercion, or repeated interrogation.

### R4. Implement safety branch

Add explicit detection and routing for self-harm, violence, abuse, and immediate danger. Provide local safety resources and emergency escalation instructions. Retain minimal safety metadata only.

Acceptance: safety branch overrides ordinary coaching; no identity learning occurs; tests cover false positives, repeated safety signals, and provider failure.

### R5. Add personal regulation rules and confirmed orientation

Implement rule strength (Hard Guardrail, Default Principle, Reflection Prompt), confirmation state, and the minimal Personal Orientation Snapshot required by Regulation.

Acceptance: non-overridable safety rules cannot be edited; confirmed rules are retrieved by task relevance; unconfirmed candidates cannot authorize behavior.

## Milestone 3 — GPT-assisted Regulation

### M1. Define structured model contract

Specify the model response schema: facts/questions, interpretations, uncertainty, emotion labels, urge, candidate actions, safety signal, and request for confirmation. Reject extra or missing fields.

Acceptance: schema validation is independent of the model; invalid output never persists or transitions a session.

### M2. Implement Context Budget and overflow policy

Assemble current task, safety state, relevant confirmed rules/values, active session, direct evidence, and recent commitments within the route budget. Add an explicit excluded-context notice.

Acceptance: raw Regulation history is not embedded; full conversation history is not sent by default; priority-order tests pass.

### M3. Implement authorization layer

Convert model proposals into allowed actions only through code-owned policy checks. Require explicit Owner confirmation for sensitive capture and high-impact actions.

Acceptance: a malicious or contradictory model response cannot bypass permissions, state transitions, retention, or safety branch.

### M4. Implement graceful model degradation

On timeout, rate limit, outage, malformed output, or spend limit, show the Deterministic Regulation Protocol. Do not silently substitute an unqualified cheap model.

Acceptance: outage tests pass with network disabled; the UI states reduced personalization; safety escalation remains available.

### M5. Build the private qualification set

Create versioned scenarios for uncertainty, jealousy, anger, reassurance seeking, genuine boundary concerns, incomplete information, values tension, ADHD-compatible delivery, and safety escalation.

Acceptance: each case has expected prohibited behaviors and allowed response properties; results are reproducible and stored as metadata, not intimate transcripts.

## Milestone 4 — Daily-use surfaces

### U1. Build minimal guided PWA

Implement one responsive Regulation flow with explicit steps, progress, pause/resume, capture confirmation, offline rules, and safety resources.

Acceptance: usable on a phone and weak connectivity; no destructive navigation loses an incomplete session; keyboard and screen-reader checks pass.

### U2. Add Discord rapid entry

Map “I’m spiraling” to a private linked session with explicit channel authorization and a short handoff to the PWA when needed.

Acceptance: unlinked channels cannot access private records; duplicate messages do not create duplicate sessions; provider outage falls back safely.

### U3. Add Data & Privacy Center basics

Provide inspect, correct, export, delete, retention, consent, and access-audit views for Regulation records.

Acceptance: deletion is verified by retrieval and restore tests; export is complete for the selected scope; sensitive content is not exposed in ordinary logs.

## Milestone 5 — Adaptability

### A1. Implement Memory Candidate extraction

Extract candidates with provenance, sensitivity, domain, confidence, expiry, and suppression fingerprint. Separate explicit facts from model inference.

Acceptance: candidates never become authoritative without required confirmation; conflicts become review items.

### A2. Implement Memory Inbox

Add batched review of approximately five candidates with accept, edit, defer, decline, and suppress actions. Expire weak candidates automatically.

Acceptance: no coercive badges or repeated declined suggestions; source excerpts and retrieval explanations are inspectable.

### A3. Implement selected historical backfill

Add source/date/domain selection, cost preview, payload preview, local redaction, per-batch consent, resumable processing, and cancellation/deletion.

Acceptance: default scope excludes Regulation and intimate relationship content; derived candidates are reversible; only selected excerpts leave the VM.

### A4. Implement Cognitive Support policies

Add capacity-aware chunking, choice limits, pause recovery, question parking, and commitment framing as user-correctable preferences—not diagnosis.

Acceptance: support changes delivery, not factual conclusions or permissions; settings can be inspected and corrected.

## Milestone 6 — Automation and review

### S1. Implement SQLite dispatcher

Add atomic claiming, idempotency, retries, quiet hours, timezone semantics, stale-job coalescing, permission/relevance rechecks, and separate delivery/seen/acted records.

Acceptance: restart and duplicate-delivery tests pass; downtime does not release a reminder burst; sensitive wording is generated at delivery.

### S2. Add daily and weekly reviews

Summarize denominators, uncertainty, minimum comparable sample, helpful/harmful behaviors, outcomes, and one provisional focus. Keep domains separate unless cross-domain synthesis is explicit.

Acceptance: insufficient samples are shown as insufficient; reviews never state personality conclusions as facts.

### S3. Add outcome follow-up

Implement permissioned Pending Outcomes with user-configurable follow-up, expiry, and acted/not-acted distinction.

Acceptance: no unsolicited intimate reminders; follow-up can be disabled and deleted.

## Verification commands

Run from the repository root after each ticket:

```bash
python -m pytest -q
python -m compileall -q .
```

For sensitive-store changes, also run the focused privacy and recovery suite once created:

```bash
python -m pytest -q tests/privacy tests/regulation tests/recovery
```

For PWA changes, run the frontend typecheck/build and a phone-sized browser smoke test. For deployment changes, run service restart, health, backup, and clean-restore tests against a staging directory—not the live data directory.

## Definition of done for the first daily-use release

The first release is complete only when Milestones 1–4 pass, the Daily-Use Readiness gate in ADR 0135 passes, and the seven-day Shadow Use in ADR 0136 completes without a severe safety or privacy failure. Milestones 5–6 remain subsequent slices unless explicitly brought forward by evidence.

## Change control

If implementation discovers a contradiction, stop at the affected ticket, document the evidence, and create a superseding ADR. Do not silently weaken safety, consent, store isolation, code authorization, or the deterministic fallback to make a test pass.
