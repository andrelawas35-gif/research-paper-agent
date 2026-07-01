# ADR 0054: Remaining ADR Implementation — Notes Mid-Slice + Graph + Answer Quality

Implements the 19 remaining gaps from the ADR audit (0053 audit) across four slices.

## Slice 1: Note Infrastructure (ADRs 0028, 0031, 0032, 0035, 0041)

- `edit_personal_note` — updates title/text/tags/concepts, preserves previous state as a version entry, re-extracts cards and suggested tags
- `reject_note_card` — marks a card `rejected: true` by 0-based index, excludes from search and mirrors
- `reject_note_concept` — removes a concept from the note and all its cards
- `render_note_markdown` — public API returning the full Markdown mirror for a note
- `import_markdown_notes` — explicit sync from `notes/*.md` back to JSONL, parsing frontmatter and versioning changes
- `notes/` directory created at runtime via markdown mirror writes (ADR 0041)

## Slice 2: Concept Graph Upgrades (ADRs 0022, 0027, 0038, 0039, 0040)

- `suggest_concept_merges` — non-destructive, returns merge candidates with similarity scores, shared papers/interests, and confidence labels
- `get_backlinks` — derives note-to-note backlinks from shared concepts in the concept graph
- `"note"` edge type added to `_EDGE_TYPES` with rank between ingest and engaged, weight bonus 0.8
- Typed concept sources — edges now carry a `sources` array with `{source_type, source_id}` alongside legacy `source_papers`
- Note signal decay — note edges stable for 90 days, lose half weight after 180 days, removed after 365 days
- `refresh_note_signal` — bumps `last_engaged_at` on note-type edges to prevent premature decay

## Slice 3: Agent Answer Quality (ADRs 0011, 0013, 0023, 0026, 0046, 0047)

- Three-lane answer instruction: **Evidence** / **Your Notes** / **Inference**
- Separate adaptation dimensions instruction: `content_selection`, `explanation_style`, `challenge_level` per concept
- Mode routing: instruction updated to detect mode from first message and switch posture
- `_infer_session_goal` — keyword-based session goal inference with confidence scoring
- Note-guided questioning: `adaptive_grill` now loads personal note concepts and generates note-derived questions
- Knowledge loop coordination: `_knowledge_loop_update` routes signals from grill/tutor/notes/interactions to the correct state stores

## Slice 4: Extraction + Coordination (ADRs 0033, 0045)

- `_extract_cards` upgraded to LLM-mediated extraction (DeepSeek API) with keyword fallback, 1–5 card limit, confidence threshold 0.4
- `_knowledge_loop_update` coordinates automatic writes to candidate signals, concept graph, and note signal refresh

## New Agent Tools

| Tool | ADR |
|---|---|
| `edit_personal_note` | 0028, 0035 |
| `reject_note_card` | 0035 |
| `reject_note_concept` | 0035 |
| `get_note_backlinks` | 0027 |
| `render_note_markdown` | 0031 |
| `import_markdown_notes` | 0032 |
| `suggest_concept_merges` | 0022 |

## Consequences

- 19 of 19 gaps from the ADR audit are now implemented
- 70/70 tests pass with zero regressions
- Agent instruction updated with three-lane answers, adaptation dimensions, mode detection, note editing, and knowledge loop guidance
