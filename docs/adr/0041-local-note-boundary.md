# ADR 0041: Local Note Boundary

Personal Notes will be stored locally under the workspace, with structured state in `user_model/` and Markdown mirrors in `notes/`. The agent may use the configured model backend for extraction during explicit note save or sync operations, but it must not send the full notes vault during unrelated prompts; retrieval should start with local lexical search and only include relevant note snippets when needed.

## Considered Options

- Keep note extraction fully local: strongest privacy, but weaker extraction unless a local model is added.
- Send the whole vault for personalization: powerful, but too broad for a personal memory system.
- Local storage with explicit, scoped model extraction: selected because it matches the current paper-agent architecture while keeping note exposure intentional.
