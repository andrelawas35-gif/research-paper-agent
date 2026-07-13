# ADR 0065-0072 Implementation Plan

**Created:** 2026-07-03
**Status:** Complete (verified 2026-07-12) — all ADRs 0065-0072 implemented and covered by tests.

Integrates the Python Module Architecture Plan with the Performance Budget
Implementation Plan. All phases 0-4 are implemented.

---

## Verified Status of ADRs 0065-0071

| ADR | Title | Status | Notes |
|---|---|---|---|
| 0065 | Web Search + Projection Plumbing + Mode Taxonomy | ✅ Done | All 14 modes + Mentor in instruction; projection wired into 4 tools |
| 0066 | Writing Mode | ✅ Done | Polish preferences + adaptation curve wired in user_profile.py; learn_from_user_message handles corrections |
| 0067 | Cognitive Adaptation ADHD | ✅ Done | Runtime integration deferred by design |
| 0068 | Mentor Personas Simon/Lanier | ✅ Done | Evidence scoping supports mentor:simon + mentor:lanier |
| 0069 | Smart Context Header | ✅ Done | Snapshot, dynamic instruction, cache, compaction hint all present |
| 0070 | Record Validation | ✅ Done | TypedDicts + validators in personal_notes.py, concept_graph.py, user_profile.py, agent.py |
| 0071 | Web Browsing/Search | ✅ Done | `search_web` with dual backends, source quality, fourth provenance lane |
| 0072 | Performance Budget | ✅ Done | Slice 1: dynamic_context.py (budget inference, snapshots, cache). Slice 2: runtime controls (write gating, tool surface, before_model_callback, generation controls, diagnostics) |

---

## Architecture Plan Integration

The Python Module Architecture Plan (`docs/python-module-architecture-plan.md`)
prescribes 5 phases. We interleave ADR work with module extraction:

```
Arch Phase 1 ──► Phase 0+1: Extract dynamic_context.py + ADR 0072 Slice 1
Arch Phase 2 ──► Phase 2+3: Extract user_profile.py + session_memory.py; fix ADRs 0066/0070
Arch Phase 3 ──► Future: Extract papers.py + retrieval.py (no ADR gap)
Arch Phase 4 ──► Future: Extract web_search, audit, grill, tutor (no ADR gap)
Arch Phase 5 ──► Final: agent.py reduced to composition
```

---

## Phase 0: Module Architecture Scaffold ✅

- [x] Create `agent_runtime/__init__.py`
- [x] Create `agent_runtime/paths.py` — extract all `*_PATH` constants from `agent.py`
- [x] Update `agent.py` imports

**Files:** `agent_runtime/__init__.py`, `agent_runtime/paths.py`, `agent.py`

---

## Phase 1: ADR 0072 Slice 1 — Dynamic Context Budgeting ✅

Implement into `agent_runtime/dynamic_context.py` (not agent.py directly):

- [x] Budget inference: `_infer_performance_budget_from_text()`, `_infer_performance_budget()`
- [x] User text extractor: `_extract_latest_user_text()`, mode hint: `_extract_mode_hint()`
- [x] Split snapshot builders: `_build_balanced_snapshot()`, `_build_deep_snapshot()`
- [x] Budget-aware cache: `dict[(state_fingerprint, budget_tier), snapshot_text]`
- [x] `build_dynamic_instruction(ctx)` — orchestrator: infer → cache check → build → return
- [x] Move `_state_fingerprint()` from agent.py
- [x] Update `agent.py` to import and delegate to the new module
- [x] Budget tests: inference, snapshot content per tier, cache stability

**Files:** `agent_runtime/dynamic_context.py`, `agent.py`, `tests/test_agent.py`

---

## Phase 2: Fix ADR 0066 — Polish Preference Learning ✅

- [x] Add polish correction detection to `_infer_message_signals()`
- [x] Update `learn_from_user_message()` to handle polish corrections
- [x] Update `_validate_profile()` to check `polish_preferences`
- [x] Polish preference learning tests

**Files:** `agent.py` (or `agent_runtime/user_profile.py` if Arch Phase 2 done first), `tests/test_agent.py`

---

## Phase 3: Fix ADR 0070 — Agent TypedDicts + Validators ✅

- [x] Add `UserProfile`, `CandidateSignal`, `TutorProgress` TypedDicts to `agent.py`
- [x] Add `_validate_candidate_signal()`, `_validate_tutor_progress()` at load boundaries
- [x] Update `_validate_profile()` to check `polish_preferences`
- [x] Validation tests

**Files:** `agent.py` (or `agent_runtime/user_profile.py` + `agent_runtime/session_memory.py`), `tests/test_agent.py`

---

## Phase 4: ADR 0072 Slice 2 — Runtime Controls ✅

- [x] Inspect ADK for per-turn tool selection (`build_before_model_callback`)
- [x] Tool surface policy by budget (`_allowed_tool_names`, FAST/SAFE/WRITE/HEAVY groups)
- [x] Durable write gating (`write_allowed` with evidence strength tiers)
- [x] External lookup policy (web search gated in SAFE_TOOLS, not FAST)
- [x] Diagnostics outside prompt context (logger.debug for budget/snapshot/tool filter)
- [x] Generation controls (max_output_tokens, temperature per budget in callback)

---

## Verification

After each phase: `python -m pytest` — all existing + new tests must pass.
