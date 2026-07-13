# PKM PWA Frontend Design Implementation Plan

## Purpose

Implement the calm-studio PWA design described in [the frontend design grilling summary](frontend-design-grilling-summary.md). The frontend must use the existing React/Vite/Tailwind app and current FastAPI contracts. Figma is reference-only; do not generate or import implementation code from Figma.

## First-slice boundary

Build only these interactive surfaces:

1. Now
2. Regulation
3. Data & Privacy
4. Offline, degraded, safety, draft, error, and empty states related to those surfaces

Do not make Search, Library, Work, Research, Writing, Compass, Reviews, or People interactive until an explicit backend API and authorized store seam exist. Do not create client-side substitutes for Regulation, rules, privacy records, retention, or safety state.

## Milestone 1 — Establish the design foundation

1. Add a Tailwind configuration file that maps semantic names to CSS variables; use names such as `paper`, `surface`, `ink`, `muted`, `action`, `action-soft`, `caution`, `danger`, `focus`, and `border`.
2. Split styling into token/theme, global base/accessibility, primitive, and workspace layers. Keep `index.css` as the import point rather than a growing implementation file.
3. Define light calm-studio tokens:
   - paper `#F6F3EC`
   - surface `#FFFFFF`
   - ink `#1F2429`
   - muted `#596166`
   - action `#1A5752`
   - action-soft `#E0F1EE`
   - caution `#9A651D`
   - danger `#A33A3A`
4. Define low-stimulation dark semantic tokens now, but do not add detailed dark workspace screens yet.
5. Define the 4px spacing scale: 4, 8, 12, 16, 24, 32, 48, 64px.
6. Define radius tokens: 8px control, 16px row/field, 20px panel, 28px app shell.
7. Self-host Atkinson Hyperlegible and Source Serif 4 WOFF2 files. Use Atkinson for UI/body; reserve Source Serif for future Compass and Reviews headings.
8. Define type tokens: 12, 14, 16, 20, 24, 32px; use only 400, 600, and 700 weights.
9. Define motion tokens: 120ms inline/focus, 180ms state change, 240ms sheet/context transition. Use one restrained ease-out curve.
10. Add a `prefers-reduced-motion` rule that makes state changes instant while retaining focus, status text, and stable layout.
11. Replace old slate/indigo global defaults and update the PWA manifest to light calm-studio metadata. Make browser chrome theme-aware when low-stimulation dark mode is selected.

Acceptance criteria:

- No new JSX uses literal color classes or hard-coded palette values.
- The app has a stable light theme before any workspace refactor begins.
- Increased system text size reflows without clipping.

## Milestone 2 — Build reusable primitives

1. Add `Button` with Primary, Secondary, Tertiary, and Destructive variants; expose loading and disabled as states, not variants.
2. Add `Field` as the accessible base for labels, help text, focus, disabled, error, and status messaging.
3. Add domain wrappers only where meaning changes: `RegulationPromptField`, `CaptureField`, and `SearchField` later.
4. Add `Surface`, `Row`, and `EvidenceBlock`; do not create a generic universal card component.
5. Add `SourceStamp` with compact default metadata: source type, domain, and date. Expand for source, processing, sensitivity, and import-batch details.
6. Add `StatusNotice` variants: Capability, Caution, Safety, Error, and Confirmation.
7. Add `AnnotationRail` that renders compact in-content metadata on phone and contextual rail content on larger layouts.
8. Add `Sheet` for bottom-sheet mobile and side-sheet tablet/desktop behavior.
9. Add `Dialog` only for irreversible confirmation; do not use dialogs for ordinary capture or navigation.
10. Add `AppNav` for normal workspaces and `FocusedFlowNav` for Regulation. `FocusedFlowNav` exposes Back and Safety Access only.
11. Use native semantic controls first. Add ARIA only where native elements cannot express the needed behavior.
12. Standardize interactive states: default, hover, active, focus-visible, disabled. Add Draft, Confirmed, Candidate, Offline, and Restricted only as meaningful component states.

Acceptance criteria:

- Every primitive has visible keyboard focus.
- Dialogs and sheets manage focus correctly and close predictably.
- Primitive styles are reusable without screen-specific color overrides.

## Milestone 3 — Align the API client with backend truth

1. Keep `frontend/src/api/client.ts` as the only browser boundary to FastAPI.
2. Preserve the existing API types and calls for regulation sessions, safety resources, personal rules, privacy summary/export/deletion, retention, consent, health, and audit data.
3. Add frontend view-model adapters only when needed to convert existing API responses into primitive props. Do not duplicate or reinterpret backend state machines in the browser.
4. Map backend Regulation `state`, `safety_state`, `is_private`, `sensitivity`, `retention_days`, and `completed_at` directly to UI state.
5. Map model assist fields directly:
   - `is_degraded` and `degradation` → Capability or Caution notice
   - `has_authorized_response` and `authorizations` → model-assisted source stamp
   - `blocked_items` and `requires_owner_confirm` → explicit review or blocked-action UI
6. Map `/offline` protocol responses to the local Regulation experience. Use the approved copy: “Local protocol available. Model assistance is paused.”
7. Surface only backend-confirmed health and capability information. Never imply cloud/model processing when the server returns degradation or local-only state.
8. Preserve backend store boundaries: Regulation content is restricted and must not become a general-retrieval result or default cross-domain context.

Acceptance criteria:

- The UI does not create a local persistence path for protected Regulation or Privacy records.
- API 401, timeout, degraded, spend-limit, and offline responses produce distinct, truthful user-facing states.

## Milestone 4 — Refactor the Now workspace

1. Replace the current placeholder home route with a mobile-first Now workspace.
2. Add the orientation header: local time, place/context, and neutral initial marker. Do not show metrics, streaks, or greeting copy.
3. Add the What Matters Today orientation surface as a data-safe placeholder until confirmed-values and active-work APIs exist. It must show draft/static copy only; do not infer values from history in the client.
4. Add the deep-teal Regulation Anchor as the primary action. It must be calm and stable: no pulse, animation loop, or emergency styling.
5. Add the private Regulation draft card below the anchor when the existing session list reports an unfinished private session. Actions: Resume, Change retention, Discard. Use existing session/retention APIs only.
6. Add Now action rows for currently supported actions. Do not render unimplemented destinations as working controls.
7. Add `AppNav` with Now, Chat, Work, Compass, Reviews only when routes have an intentional state. Until then, use disabled/non-interactive visual placeholders or omit unavailable destinations.
8. Add quiet contextual Capability notices when the backend or browser is offline/degraded.

Acceptance criteria:

- Now works at phone, tablet, and desktop breakpoints.
- The primary Regulation action is visually dominant but non-alarming.
- Private draft status is not presented as completed evidence.

## Milestone 5 — Refactor the complete Regulation flow

1. Preserve the current server-owned session lifecycle; create a session before recording any step.
2. Render one step at a time: Facts → Story → Emotion → Urge → Action.
3. Replace generic progress UI with the approved vertical `AnnotationRail`: compact visible labels, deep-teal active node, quieter completed nodes, neutral future nodes; no score or percentage.
4. Use `RegulationPromptField` states: Default, Focused, Draft, Confirmed, Offline.
5. Submit each step using existing session endpoints; use returned session content as the source of truth after every mutation.
6. Render Safety Access as small **Need immediate help?** text. Escalate its prominence only from server-backed safety state or explicit user action.
7. Render safety resources from the existing safety endpoint. Do not diagnose, debate, or substitute generic advice before the safety branch is addressed.
8. On exit, use existing expiration/draft behavior and retention data. Render Resume, Change retention, and Discard only where the backend supports those actions; otherwise document the missing contract rather than faking persistence.
9. Render degraded/local-only state from the offline protocol endpoint; hide or disable model-assist affordances when unavailable.
10. Render model-assisted results as provisional blocks with source stamps and Accept/Edit/Route/Discard only where backend authorization exists. Do not persist client-generated proposals.
11. Render the next-action outcome as one explicit, values-consistent action. Keep accept/change decisions visible and avoid a multi-option advice list.
12. Record delayed outcomes through the existing outcomes endpoint, never as a live score or streak.

Acceptance criteria:

- Back/Safety remains available throughout focused Regulation.
- Each API response updates the visible step state without relying on client-only progression.
- Offline and safety paths remain usable without model access.

## Milestone 6 — Refactor Data & Privacy

1. Use existing privacy summary, session list/inspection, export, deletion, retention, consent, and audit endpoints.
2. Build a first-slice domain map using only backend-supported Regulation, Rules, Audit, and operational data. Clearly label future domains as unavailable rather than inventing counts or records.
3. Show quiet privacy cues: source/sensitivity stamps, restricted labels, retention information, and plain human audit messages.
4. Create export review using the server’s supported scopes; show scope and consequences before sending the export request.
5. Create deletion review using the selected session or all-session API. Require an explicit confirmation phrase for irreversible actions.
6. Render recovery and model-budget cards only after corresponding backend endpoints are available; do not fabricate these system metrics in the client.
7. Keep normal health invisible. Show a small actionable degraded notice only when `/health/ready` or an API request reports degradation.

Acceptance criteria:

- Export, inspection, retention, consent, audit, and deletion UI are all backed by existing API results.
- No sensitive content appears in global status or audit UI by default.

## Milestone 7 — Verify and gate future workspace work

1. Add component tests for primitives, keyboard focus, reduced motion, sheet/dialog focus handling, status announcements, and theme selection.
2. Add API integration tests for Regulation and Privacy client operations, including 401, offline protocol, safety screen, degradation, retention, export, and deletion.
3. Capture browser screenshots at phone, tablet, and desktop sizes for Now, Regulation, Privacy, offline, and safety states.
4. Run the three scripted Regulation walkthroughs from the grilling summary:
   - ordinary activation
   - incomplete-information spiral
   - genuine boundary concern
5. Record observed friction, safety ambiguity, cognitive-load issues, and one component-level change for each walkthrough.
6. Do not start interactive Search, Library, Work, Research, Writing, Compass, Reviews, or People until their API contracts, storage domains, provenance, and privacy boundaries are designed and implemented.

## Completion criteria

The first slice is ready when:

1. The calm-studio design system is applied consistently across Now, Regulation, and Privacy.
2. The frontend displays backend-owned safety, retention, degradation, and authorization state truthfully.
3. Regulation works with local/offline fallback and no fake model success states.
4. Core responsive, keyboard, reduced-motion, and screenshot checks pass.
5. The three Regulation walkthroughs meet the behavioral pass criteria from the grilling summary.
