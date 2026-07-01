# ADR 0022: Explicit Concept Merges

Concept deduplication for Personal Notes will be suggestion-first and approval-gated. The agent may identify similar Concepts and recommend a canonical name, but it must not silently merge them because a concept name represents the user's evolving interpretation, and a bad merge can distort future retrieval, grilling, and paper-note connections.

## Considered Options

- Automatic merge above a similarity threshold: convenient, but risky for personal knowledge where near-synonyms may carry meaningful distinctions.
- Never suggest merges: safe, but lets the graph fragment as random notes accumulate.
- Suggest merges and require approval: selected because it keeps graph hygiene visible while preserving the user's authority over meaning.
