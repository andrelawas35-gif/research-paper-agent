# ADR 0066: Writing Mode — Proactive Polish with Learned Adaptation

Fills in the name-only Writing Mode stub with behavioral instruction, a `polish_preferences` profile extension, and a per-context adaptation curve that starts proactive and learns from explicit corrections.

## Decision

### Writing Mode behavior

Writing Mode transforms the user's knowledge into prose with attention to voice, flow, expression, and audience. It operates at four polish levels:

| Level | Behavior |
|---|---|
| `none` | Keep user's wording exactly as written — no rewriting |
| `light` | Fix grammar, typos, and spelling only |
| `moderate` | Grammar + improve flow, clarity, and word choice |
| `full` | Significant restructuring — reorganize, rephrase, elevate prose |

### Adaptation curve

- **Starts proactive** — the agent defaults to `moderate` polish for all contexts until it learns otherwise
- **Learns from explicit corrections** — when the user says "keep my wording," "too formal," "that's not what I meant," the agent records a **Polish Preference** for that context
- **Per-context** — preferences are keyed to context: `"chat"`, `"technical"`, `"creative"`, `"default"`. The agent matches the current interaction to the closest context and applies the corresponding polish level
- **Uses existing infrastructure** — corrections flow through `learn_from_user_message` → `_knowledge_loop_update` → `polish_preferences` in `profile.json`. No new tool needed

### Profile extension

`profile.json` gains a `polish_preferences` dict:

```json
{
  "polish_preferences": {
    "default": "moderate",
    "chat": "light",
    "technical": "full",
    "creative": "moderate"
  }
}
```

## Rationale

- Writing Mode already exists in the mode taxonomy (ADR 0060) as a name-only stub — this fills it in
- Instruction-only implementation matches how Builder, Grill, and Tutor modes work
- The `polish_preferences` dict extends the existing `style_preferences` pattern rather than inventing a new mechanism
- Proactive start with learned back-off respects the user's request while matching Hybrid Learning Control (ADR 0052): automatic is provisional, explicit corrections are durable

## New Glossary Terms

- **Polish Preference** — a per-context adaptation setting controlling how much the agent rewrites the user's prose, from `none` to `full`. Learned from explicit corrections and stored in the User Model
- **Writing Mode** — an Agent Mode for transforming knowledge into prose with attention to voice, flow, expression, and audience

## Consequences

- Writing Mode instruction added to `agent.py`
- `polish_preferences` dict added to `_default_user_profile()` and `_validate_profile()`
- Instruction updated: agent starts proactive, learns Polish Preferences from explicit corrections
- No new tools, no new dependencies
