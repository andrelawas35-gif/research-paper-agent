# PKM PWA Frontend Design Grilling Summary

## Status

This document records the UX and design decisions made during the frontend grilling session. It is the design brief for Figma work and a future implementation handoff; it does not authorize frontend implementation in this repository yet.

The existing Figma file is connected at [PKM Figma design](https://www.figma.com/design/17GeILDPZGhcPisKTGW8H5/Untitled?node-id=3-38). The Starter-plan Figma MCP call limit was reached during the session, so new Figma mutations are paused until access resets or the plan changes.

## Product Thesis

The PWA is a single-owner, local-first Personal Knowledge Manager and companion. Its primary job is to help the user make a deliberate next move across reflection, regulation, work, study, research, writing, and personal direction—without creating reassurance loops, surveillance behavior, gamification, or hidden memory.

The initial production slice is not a generic chat app. It is the mobile Regulation flow, entered from a sparse Now workspace, supported by deterministic local behavior, explicit privacy controls, and graceful model/API degradation.

## Visual Direction

The dominant aesthetic is a **calm studio**, combined with quiet field-notebook evidence cues and command-center precision only when deciding or reviewing.

- Background: warm paper with true-white surfaces; no gradients or decorative texture.
- Primary color: deep teal for primary/action states.
- Caution: muted amber.
- Irreversible or safety-critical state: restrained red, never color alone.
- Surface style: hairline borders and minimal elevation, not a floating-card dashboard.
- Radius: 8px controls, 16px rows/fields, 20px panels, 28px screen shell.
- Icons: consistent outline icon family with a single stroke weight.
- Typography: Atkinson Hyperlegible for UI/body; Source Serif 4 only for rare Compass and Reviews headings.
- Motion: short, state-based dissolves/slides only where they clarify a transition; no pulsing, celebrations, shimmer, or ambient animation.
- Signature device: a quiet annotation margin/rail carrying sequence, provenance, active context, and privacy detail.

Light calm-studio mode is first. Dark mode is a true low-stimulation variant using the same semantic tokens, not a color inversion.

## Foundations and Accessibility

- Use named Figma variables for color, spacing, type, radius, and motion.
- Component variants use user-visible states: Default, Focused, Disabled, Draft, Confirmed, Candidate, Offline.
- Visible teal focus ring for keyboard/switch access.
- Support system text scaling plus a compact in-app readability control; layouts must reflow, never clip.
- Low-stimulation mode changes density, motion, and contrast while preserving the same information architecture.
- Important changes announce concise screen-reader status messages.
- Phone first; tablet retains a primary column plus an optional context panel; desktop adds a quiet contextual rail.

## Global Information Architecture

Primary navigation remains persistent on normal screens:

- Now
- Chat
- Work
- Compass
- Reviews

Now is the sparse landing workspace. Chat is a mode-aware conversation surface. Work holds durable work objects and context-rich next actions. Compass holds purpose, values, principles, goals, and commitments. Reviews holds domain-separated qualitative reflection. Library/Search and Data & Privacy are first-class workspaces, reachable through navigation or contextual action patterns.

Focused Regulation flows collapse global bottom navigation to an obvious Back control and quiet Safety Access. The user is never trapped.

## Now Workspace

The Now screen is mobile-first and intentionally sparse.

- Header: time, place/context, and a neutral initial/avatar marker; no metrics, streaks, or performative greeting.
- Orientation card: **What matters today**. It shows one confirmed value, commitment, or active-work reminder. It is dismissible/correctable and exposes **Why am I seeing this?** on demand.
- Regulation entry: a deep-teal quiet, high-confidence anchor. It is visually unmistakable but does not pulse, nag, or simulate emergency urgency.
- If unfinished Regulation exists, show a private draft card directly below the anchor with Resume, Change retention, and Discard.
- Action rows: outline icon, title, one-line purpose, chevron. Examples: Capture, Continue work, Study.
- Global New always opens the same save-first Capture sheet.

## Regulation Mode

Regulation is the critical first-slice flow. It is one prompt at a time:

```text
Facts → Story → Emotion → Urge → Action
```

- Orientation rail: thin vertical line with compact visible labels; active node is deep teal; completed nodes remain as evidence; no score, percentage, streak, or completion celebration.
- Prompt Field states: Default, Focused, Draft, Confirmed, Offline.
- Prompt Field: spacious text entry with optional, clearly labeled examples; the user’s wording is canonical.
- Offline copy: “Local protocol available. Model assistance is paused.”
- Safety Access: small text control, **Need immediate help?**. It becomes prominent only when relevant. Its panel prioritizes direct local safety actions, not diagnosis or debate.
- Exiting early: save a private draft within a short configurable retention window. It never counts as completed evidence or weekly pattern input.
- Reassurance loop: show a calm inline boundary card that names the loop, restates known facts once, and directs the user to one next action.
- End state: one smallest values-consistent next action, specific, time-bounded, and reversible where possible. Its card exposes Why this?, Accept, and Change. Change can alter scope/timing/wording without restarting the session.
- Outcome: optional delayed follow-up—helped, hurt, or changed nothing—rather than an immediate self-rating.
- Firmness: name a conflict with a confirmed rule or value, explain short-term relief versus longer-term cost, then preserve user choice.

## Companion, Personalization, and Memory

- Voice: Calm direct by default; optional presets are More concise and More challenging.
- Regulation may override tone only toward calmer, more direct safety language when needed.
- Reinforce autonomy only in high-stakes or repeated reassurance contexts.
- History-derived rules or values enter a reviewed candidate queue with evidence, plain-language strength, and Confirm/Edit/Decline.
- Declined candidates can be suppressed with **Don’t suggest this again**.
- Candidate review is batched weekly or opened from Compass, never pushed immediately after a conversation.
- When confirmed context influences a suggestion, expose **Using this context** on demand, with a direct **Correct this context** action.
- Limited context may be disclosed as **Using focused context** only when it materially affects the answer.
- Low-confidence responses provide a bounded answer and name the one fact, source, or permission that would improve it.

## Compass, Values, Rules, and Reviews

Compass uses a layered map:

```text
Purpose → Values → Principles → Goals → Commitments
```

- Every layer is explicit and inspectable; no personality profile is inferred.
- Empty Compass starts with a small articulation prompt saved as draft.
- Draft values are confirmed only after a later review with examples and lived use.
- Confirmed values are versioned with effective dates and optional rationale.
- Personal Rules have strength, scope, and exceptions. Creation follows Propose → Test against examples → Confirm.
- Confirmed and Candidate states use text plus a quiet visual difference; color is never the only signal.
- Daily Review is a skippable five-minute ritual: strongest emotion, trigger/reaction, better response for tomorrow.
- Weekly Review uses a small evidence table with denominators, uncertainty, source sessions, and **Correct this pattern**. It is qualitative, unscored, and provisional.

## Capture, Library, Research, Writing, and Work

### Capture

- Save first, route later.
- Opens as a focused bottom sheet with one large field and one Save action.
- After saving: Route now or later; default is later.
- Routing is always explicit; sensitive domains are never silently inferred.
- Attachments show local previews, type, origin, processing state, and remove action before saving or sending.
- OCR shows original plus editable extracted text and confidence.
- Sensitive cloud processing requires explicit per-batch choice and editable redaction preview.
- Attachment retention is domain-specific and visible.

### Library and Search

- Unified result stream with visible provenance, sensitivity, and source labels.
- Evidence-first detail: original content, provenance, timestamp, domain, and match rationale before synthesis.
- Search is a focused full-screen workspace.
- Filters prioritize source, sensitivity, then date range.
- Ranking is a transparent blend of exact match, recency, and selected filters with **Why this matched**.
- Restricted results appear as redacted shells until revealed.
- Recent search is local, optional, and clearable.

### Research

- Three visible lanes: Evidence, Notes, Synthesis.
- Add source is explicit for URL, file, note, or capture, with visible provenance and processing status.
- Evidence opens to the original source with highlights and linked notes.
- Notes are standalone user-authored objects with exact citations.
- Synthesis is an editable draft with inline citations, compact source previews, and quiet Needs support markers.
- Export has an explicit privacy/provenance review.

### Writing

- Visible layers: Source material, user draft, agent suggestions.
- Every pass has one explicit revision goal.
- Meaningful changes use field-level Accept/Edit/Reject.
- Versions use named checkpoints and compact diffs.

### Work and Builder

- Work objects are typed: draft, decision, experiment, or task. The model proposes; the user authorizes persistence.
- Review is a compact diff showing fields, excerpts, confidence, and Save/Edit/Discard.
- Tasks are context-rich next actions with optional semantic, timezone-aware timing.
- Task completion is quiet and preserved in history; deferral asks when it should return.
- Builder stages: purpose, constraints, candidates, decisions, risks, evidence, chosen experiment.
- Builder candidates are comparable trade-off cards. Parked Branches are collapsible, explain why they were parked, and provide a path to resume.

## People and Relationship Support

- People separates context, operations, and restricted links.
- Creating a person begins with name/label, relationship context, optional privacy level; no automatic extraction.
- Relationship events are user-authored and purpose-based, not automatic surveillance logs.
- Reality checks use Facts → interpretations → possible explanations → boundaries → next question.
- Evidence is shown as **Observed / Added meaning**.
- Boundaries are framed as a clear statement, present behavior, and one calm action—not relationship verdicts.
- Restricted relationship records require an explicit designation and just-in-time confirmation before linking into a session.

## Privacy, Safety, Local-first, and System States

- Data & Privacy is a first-class workspace with a domain map: Regulation, Values, Notes, Relationships, Work, Research, Session Metadata.
- Sensitive domains use quiet privacy cues and plain-language labels, not alarm-heavy warnings.
- Export is domain-selectable and human-readable by default, with a recovery archive optional.
- Irreversible deletion has a scope review, impact details, and explicit confirmation phrase.
- Recovery readiness is a quiet status card with last encrypted backup and Test recovery.
- Normal health remains invisible; degraded states state the available local fallback.
- Processing stamps distinguish Local protocol and Model-assisted · GPT.
- Offline first entry explains local capability and offers Capture or Regulation.
- App lock uses a configurable short timeout; unlock returns to the prior screen with sensitive fields still obscured until refocused.
- System includes a compact monthly model/API budget, task-class usage, adjustable cap, and local fallback if cap is reached.

## Notifications, Reminders, and Automations

- Notifications are only user-authorized reminders and safety-critical notices.
- Each has one primary action, Snooze, and Pause.
- Notification history is a compact privacy audit log, not an engagement inbox.
- Reminder tiers: off by default, occasional, active; every reminder has source disclosure and pause/correction controls.
- Study reminders are contextual and permissioned.
- Future automations are visible, pausable, domain-scoped, and recorded in a compact outcome log.

## Responsive and Interaction Rules

- Phone: thumb-reachable lower primary actions and safe-area spacing.
- Tablet: one primary column plus optional collapsible context panel.
- Desktop: preserve primary column and add a quiet context rail containing active task, source stamp, and one next-step reminder.
- Restore previous scroll position on return; show attention anchor only if context changed.
- External links show destination preview and explicit Open externally action.
- Reversible actions use inline Undo; archive is reversible and retains provenance.
- Empty states use plain explanation plus one useful action. Errors use plain explanation plus one repair action.
- Loading uses structural placeholders rather than shimmer.

## Figma Organization and Build Sequence

Organize the Figma file:

```text
Foundations → Components → Workspaces → Flows → Architecture handoff
```

Build Regulation primitives first:

- `Regulation/PromptField`
- `Regulation/OrientationRail`
- `Regulation/SafetyAccess`
- `Regulation/NextAction`
- `Regulation/DraftState`

Then build the complete mobile Regulation flow:

```text
Now → Facts → Story → Emotion → Urge → Action → Outcome
                         ↘ Exit → Private Draft → Resume/Discard
                         ↘ Safety Access
                         ↘ Offline local protocol
```

Validate it with three scripted walkthroughs:

1. Ordinary activation
2. Incomplete-information spiral
3. Genuine boundary concern

The flow passes only if the user can identify facts versus meaning, pause before action, reach safety help if required, and leave with one values-consistent next step. Record friction, safety ambiguity, cognitive-load issues, and one focused component change after each walkthrough.

## Implementation Gate

Do not begin frontend implementation until Figma includes:

1. Approved mobile Now and complete Regulation flow
2. Token foundation and Regulation component states
3. Offline, error, empty, draft, and safety states
4. Decision-critical prototype interactions
5. Walkthrough evidence and architecture annotations
6. Handoff containing Figma node links, token table, component/state inventory, interaction notes, accessibility notes, and ADR mappings

## Current Next Step

When Figma access is available again, create the Foundations page and the reusable Regulation primitives, then build the complete mobile Regulation flow and run the three walkthroughs above. The repository should remain design-only until this gate is satisfied.
