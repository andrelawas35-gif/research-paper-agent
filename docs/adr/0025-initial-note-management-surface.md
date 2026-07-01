# ADR 0025: Initial Note Management Surface

The first Personal Notes implementation will expose four tools: `save_personal_note`, `search_personal_notes`, `list_personal_notes`, and `get_personal_note`. This covers capture, retrieval, browsing, and inspection while keeping backlinks and graph exploration as behavior layered on top of search/list until the workflows prove they need dedicated tools.

## Considered Options

- Many Obsidian-style tools up front: expressive, but likely to overfit before real note workflows exist.
- Only save/search: minimal, but weak for browsing and debugging note state.
- Four core tools: selected because they give the agent a complete basic lifecycle without prematurely designing a full vault interface.
