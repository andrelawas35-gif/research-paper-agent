# PKM Architecture Grilling Session Summary

**Status:** Approved architecture baseline for implementation  
**Baseline ADR:** [0137](adr/0137-pkm-architecture-baseline-is-approved-for-implementation.md)  
**Scope:** Personal Knowledge Manager, including Regulation, Values Compass, ADHD-aware Cognitive Support, memory adaptation, all modes, UI/UX, retrieval, model routing, deployment, privacy, scheduling, and release readiness.

## Executive decision

Keep one Personal Knowledge Manager agent and add Regulation as a self-contained module and user-facing mode. Do not create a second agent yet. The existing agent already owns the user model, personal rules, notes, relationship context, modes, and recurring-pattern infrastructure. A second agent would duplicate memory and produce conflicting interpretations.

The companion’s objective is not to decide whether a feared action is true. It helps the Owner choose the best user-aligned next action, even when truth remains uncertain:

```text
trigger → facts → interpretation → emotion → urge → action → outcome
```

It should be firm, avoid automatic reassurance, coach behavior rather than rumination, distinguish discomfort from danger, and complement rather than replace therapy or emergency services.

## Product and domain model

### Regulation Mode

`emotional_regulation.py` owns trigger sessions, internal sequences, outcomes, personal regulation rules, daily reviews, and weekly pattern reviews. It remains separate from `relationship_management.py`: relationship records describe people and interactions; Regulation records describe the Owner’s internal sequence.

The four user workflows are:

1. **Emergency trigger mode:** interrupt the spiral, separate facts from assumptions, identify the feared meaning and urge, then pause before action.
2. **Relationship reality check:** distinguish dishonesty, unclear communication, jealousy, ego injury, controlling behavior, and reasonable boundaries without diagnosing or issuing unsupported verdicts.
3. **Daily journal:** emotion, trigger, reaction, better response, and tomorrow’s action.
4. **Weekly review:** recurring triggers, thoughts, helpful and harmful behaviors, feared outcomes, and one provisional focus.

Regulation has an explicit code-owned state machine and a safety branch. Safety concerns override coaching; emergency records are minimally retained and do not train identity. The system never encourages surveillance, retaliation, coercion, repeated interrogation, or partner diagnosis.

### Values and orientation

Purpose, Core Values, Personal Principles, Goals, and Commitments are separate concepts. Core Values require explicit confirmation. Values are append-only with lifecycle states such as active, under review, retired, reframed, and superseded. Value tensions are preserved rather than flattened into one “true” value.

`personal_orientation.py` provides the single task-scoped Personal Orientation Snapshot used to ground responses in confirmed values, relevant rules, commitments, and approved preferences.

### ADHD-aware Cognitive Support

`cognitive_support.py` adapts delivery by observed behavioral need and context—not by treating a diagnostic label as an instruction. Support can adjust chunk size, pacing, re-entry after pauses, working-memory load, choice count, and commitment framing. It remains user-correctable and is not silently treated as a diagnosis.

The companion may remind the Owner of values, purpose, commitments, and relevant historical facts, but reminders are permission-tiered: contextual by default, event-driven through scoped opt-in, and scheduled only through explicit opt-in.

## Memory and adaptability

Conversation is not automatically memory. The pipeline is:

```text
conversation → candidate extraction → sensitivity/domain classification
→ provenance → duplicate/conflict detection → review when required
→ approved typed record → searchable projection → task-specific retrieval
```

Values, purpose, ADHD preferences, relationship interpretations, and recurring emotional patterns require confirmation. Low-risk explicit operational facts may be accepted automatically. Every candidate keeps source and timestamp provenance. Conflicts create review items; they do not silently overwrite existing records.

The Memory Inbox is quiet, batched, and non-coercive. It shows roughly five candidates at a time with source, date, confidence, domain, conflicts, and accept/edit/defer/decline/suppress actions. Weak candidates expire after 30 days; explicit statements remain reviewable for 90 days. Declined candidates leave only a suppression fingerprint and are not retrievable personal memory.

Historical backfill is selected, bounded, and reversible. The recommended first scope is the previous 30–60 days of study, projects, and explicit values conversations. Regulation and intimate relationship material are excluded by default. Backfill produces candidates, not accepted memories, and pauses when review capacity is reached.

Cloud processing requires per-batch consent and a payload preview. Local preprocessing removes metadata, unrelated messages, secrets, credentials, and unnecessary identifiers. Only selected excerpts are sent to GPT. On the current 1-OCPU/6-GB VM, “local-only” means deterministic extraction, filtering, FTS5, validation, and manual governance—not running a capable local conversational LLM.

## Data, privacy, and retrieval architecture

Use a shared event envelope and append infrastructure, with domain-owned payloads and reducers. Keep Regulation in a separate sensitive store, encrypted at rest from the first slice with an external key. Use tiered retention and per-record cryptographic deletion. The Owner must be able to inspect, correct, export, and delete recorded data.

The initial stack is Python 3.12, Google ADK, FastAPI, Pydantic, React, TypeScript, Vite, PWA support, Tailwind, and accessible headless components. SQLite WAL remains the primary store with strict boundaries for operational, general PKM, and Regulation data. Retrieval starts with SQLite FTS5 plus a replaceable local embedding index. A standalone vector database, PostgreSQL, Redis/Celery, distributed workers, and multi-VM HA are deferred until measured need justifies them.

Retrieval uses structure-aware typed chunks. Raw Regulation history is excluded from general embeddings. Every response has a retrievable, inspectable Retrieval Explanation showing eligibility, provenance, authority, relevance, and sensitivity constraints without exposing hidden reasoning.

## Model and cost policy

GPT-5 mini is the initial daily model for ordinary PKM chat, retrieval synthesis, study, values grounding, and model-assisted Regulation. GPT-5 is policy-gated for explicit deeper analysis, high-impact unresolved value conflicts, difficult broad reviews, consequential conflicting research, or approved workflows. Distress, repetition, reassurance seeking, and conversation length are never escalation signals.

Model identifiers remain configuration behind a provider adapter. Every model must pass a private qualification set covering structured output, rule adherence, reassurance resistance, coercion avoidance, calibrated uncertainty, ADHD-compatible delivery, values grounding, latency, and cost.

The gateway enforces a $20 monthly warning budget, $30 hard limit, and $5 background allowance initially, with warnings at 50%, 75%, and 90%. It attributes spend by mode, workflow, model, and interactive/background origin. At the hard limit, background inference stops; the deterministic Regulation protocol remains available.

Context budgets are task-specific: roughly 2–4K tokens for quick capture, 4–8K for normal conversation, 8–16K for study/writing/Regulation, and up to 32K for explicit synthesis. Overflow preserves current intent, safety, confirmed values/rules, active state, direct evidence, recent commitments, provisional patterns, and finally general history. The system tells the model when relevant context was excluded.

When GPT is unavailable, slow, rate-limited, or invalid, Regulation switches to the deterministic local protocol. It exposes the degradation, preserves safety resources and confirmed rules, and recommends only bounded reversible actions. It never pretends a cheap fallback model provides equivalent judgment.

## UI/UX and delivery surfaces

The primary surface is a private web/PWA; Discord is the rapid-entry surface. Modes live in unified workspaces: Now, Chat, Library, Work, People, Compass, Reviews, and Settings. The Now screen is sparse. Regulation uses a hybrid guided conversation, while all model suggestions remain visibly distinct from code-authorized transitions and persisted records.

The Data & Privacy Center is first-class and includes memory review, source inspection, consent, export, deletion, retention, access audit, and recovery controls. A global Quick Capture saves first and routes explicitly across stores. Work conversations produce durable Work Objects; Library unifies search without erasing provenance.

## Scheduling and deployment

The Owner Timezone begins as `Asia/Manila` and can be explicitly changed to `America/Los_Angeles`. Schedules declare local-time, fixed-instant, or named-location semantics. Timezone changes preview affected schedules.

One SQLite-backed dispatcher claims due jobs atomically, rechecks permission and relevance, applies quiet hours, uses idempotency keys, bounds retries, avoids bursts after downtime, generates sensitive wording only at delivery, and records delivery separately from seen and acted.

The production host is one hardened Oracle VM with private Tailscale access, separate systemd services, auto-recovery, offline safety access, graceful model/API degradation, encrypted off-VM backups, and no HA claim. Interactive work preempts bounded background jobs. The current 1-OCPU/6-GB VM is the initial target; 4 OCPU/24 GB is optional headroom, not a prerequisite.

## Implementation sequence

1. **Foundation:** event envelope, store boundaries, encryption, external key loading/deletion, API/auth/health, provider adapter, spend accounting.
2. **Offline Regulation:** state machine, safety branch, deterministic protocol, rules, minimal confirmed values, domain and safety tests.
3. **Model-assisted Regulation:** GPT-5 mini structured output, code validation/authorization, context assembly, qualification, timeout/failure handling.
4. **Daily-use surfaces:** guided PWA, offline resources, Discord entry, privacy and retrieval explanations.
5. **Adaptability:** Memory Candidates, Memory Inbox, Personal Orientation Snapshot, historical backfill, Cognitive Support policies.
6. **Automation and review:** dispatcher, permissioned reminders, daily/weekly reviews, pattern evidence, outcome follow-up.

Each milestone is a Tracer-Bullet Milestone: independently deployable, testable, and reversible. UI work follows an executable offline Regulation API or minimal harness.

## Release and shadow-use gates

Daily-Use Readiness requires representative Regulation scenarios, correct code-owned safety behavior, safe model failure, no sensitive leakage, working capture/correction/export/deletion, restart and duplicate handling, encrypted restore, offline access, and weak-connectivity phone usability.

The seven-day Shadow Use requires at least five naturally occurring check-ins, zero unsafe or coercive recommendations, zero unapproved captures, declared fallback behavior, at least 90% valid GPT-5 mini structured responses, approximately three-second median interactive latency excluding disclosed deep analysis, restart and provider-outage walkthroughs, at least 80% useful or appropriately cautious reviewed advice, and no observed increase in reassurance seeking. A severe safety or privacy failure resets the period. These are engineering thresholds, not clinical efficacy claims.

## Deferred by design

The following remain deferred until measured evidence crosses an explicit threshold:

- A separate Regulation agent
- Silent historical profile backfill
- Automatic identity or diagnosis inference
- Standalone vector database
- PostgreSQL migration
- Redis/Celery/Kafka or distributed scheduling
- Multi-VM high availability
- A local LLM on the production VM
- Broad scheduled coaching before the foundation is proven

## Source decisions

The detailed decisions are recorded in [ADRs 0073–0137](adr/), with the latest baseline approval in [ADR 0137](adr/0137-pkm-architecture-baseline-is-approved-for-implementation.md). The shared vocabulary and definitions are maintained in [CONTEXT.md](../CONTEXT.md).
