# ADR 0036: Personal Notes Module Boundary

Personal Notes will be implemented in a dedicated `personal_notes.py` module, with `agent.py` exposing thin ADK tool wrappers and instruction updates. Notes require storage, extraction, Markdown rendering, search, correction, deletion, and Concept Graph integration; keeping that behavior out of `agent.py` preserves the main agent file as orchestration rather than another storage subsystem.

## Considered Options

- Put all note tools directly in `agent.py`: fastest initially, but makes an already-large file harder to reason about.
- Create a separate Personal Notes module: selected because notes have their own lifecycle and storage rules.
- Create a package with many submodules: cleaner eventually, but more structure than the first implementation needs.
