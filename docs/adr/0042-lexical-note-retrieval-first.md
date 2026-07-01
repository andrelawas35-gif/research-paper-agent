# ADR 0042: Lexical Note Retrieval First

Personal Note retrieval will start with lexical search plus Concept Graph boosts rather than embeddings or a vector database. This matches the existing paper evidence search style, avoids new dependencies, and leaves room to swap in embeddings later if lexical search and graph similarity become insufficient.

## Considered Options

- Add embeddings immediately: better semantic recall, but adds dependencies and storage complexity before the note workflow is proven.
- Reuse lexical search and graph boosts first: selected because it fits the current architecture and keeps the first implementation local-file friendly.
