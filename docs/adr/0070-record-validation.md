# ADR 0070: Record Validation — TypedDict + Assert Guards at Load Boundaries

Adds runtime record validation at load boundaries using zero-dependency TypedDict schemas and assert guards in each module.

## Decision

Each data module defines a `TypedDict` for its persisted record shape and adds a `_validate_*` function called by the corresponding `load_*` or `_write_*` function. Malformed records are skipped with a warning, preserving the defensive `.get()` fallback behavior for minor issues while catching structural corruption.

Models per module:

| Module | Models |
|---|---|
| `personal_notes.py` | `PersonalNote`, `NoteCard` |
| `concept_graph.py` | `ConceptEdge`, `ConceptGraph` |
| `agent.py` | `UserProfile`, `CandidateSignal`, `TutorProgress` |

No Pydantic dependency. No new package. TypedDict is a stdlib feature (Python 3.8+) with zero runtime cost and full IDE/type-checker support.

Validation strategy:

- **On load** — `_validate_note(record)` runs inside `load_notes()`, checks required keys and types, skips malformed records with a log warning
- **On write** — assertion at the boundary of `save_note()`, `_write_notes()` catches programmer errors before they hit disk
- **On edit** — `edit_personal_note()` validates the record exists and the update keeps required fields intact
- **Migration path** — `schema_version` field is checked and can trigger migration functions in the future

## Rationale

- The system has zero record validation today — a malformed `personal_notes.jsonl` line silently corrupts downstream behavior
- TypedDict + assert guards is the lightest-weight option: zero new dependencies, zero import cost, trivial to test
- Pydantic is heavy for three flat schemas in a single-user local agent with no untrusted input
- The threat is data corruption over time (option B from the grill), not LLM output hallucination — validation belongs at the load boundary

## New Glossary Terms

- **Record Validation** — the guarantee that a loaded record matches its expected shape before any business logic touches it

## Consequences

- `personal_notes.py`: `PersonalNote` and `NoteCard` TypedDicts, `_validate_note()` called in `load_notes()`
- `concept_graph.py`: `ConceptEdge` TypedDict, `_validate_edge()` called in `load()`
- `agent.py`: `UserProfile` TypedDict, `_validate_profile()` called in `_load_user_profile()`
- Tests verify that malformed records are skipped, valid records pass through, and writes produce valid shapes
- Future: if LLM tool-output validation is needed, Pydantic can be added at that boundary without changing the stored-record layer
