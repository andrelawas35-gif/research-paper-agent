# ADR 0001: Keep Personalization In A Local User Model

## Status

Accepted

## Context

The agent should improve around the user's interests, grammar, quirks, and recurring question types. That requires continuity across runs, but the agent is a local research assistant and should not silently depend on remote storage or hidden memory.

## Decision

Store personalization in local JSON files under `user_model/`. The agent exposes tools to learn from a message, record interactions, update explicit preferences, inspect the profile, and audit adaptation gaps.

## Consequences

- Personalization is inspectable and editable.
- Sensitive interaction traces stay local to the project folder.
- The agent can adapt without changing its own source code.
- The model is only as good as the interactions it is asked to record or learn from.

## Alternatives Considered

- Prompt-only personalization: simple, but lost between sessions.
- Hosted memory service: more powerful, but less transparent for a local prototype.
- Automatic source-code rewriting: too risky for early personalization and hard to audit.

