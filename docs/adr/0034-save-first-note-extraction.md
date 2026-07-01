# ADR 0034: Save-First Note Extraction

Explicitly captured Personal Notes will be saved immediately, and the agent will return an extraction summary showing Note Cards, linked Concepts, and Suggested Tags. Because `note:` or `save note:` already signals intent, a second confirmation step would make capture slower; instead, the response should make correction commands obvious.

## Considered Options

- Preview before every save: safer, but too much friction for quick capture.
- Save silently: fast, but hides extraction mistakes.
- Save first with correction summary: selected because it preserves capture flow while keeping graph changes inspectable.
