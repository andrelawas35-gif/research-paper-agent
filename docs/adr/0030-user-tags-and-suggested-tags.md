# ADR 0030: User Tags and Suggested Tags

Personal Notes will distinguish User Tags from Suggested Tags. User Tags are intentional, durable organization chosen by the user; Suggested Tags are generated retrieval hints that can be regenerated or ignored. The agent must not silently promote Suggested Tags into User Tags.

## Considered Options

- Single tag list: simple, but hides whether a tag was user-authored or inferred.
- User tags only: clean, but loses useful generated retrieval metadata.
- Separate user and suggested tags: selected because it preserves intent while still helping search and browsing.
