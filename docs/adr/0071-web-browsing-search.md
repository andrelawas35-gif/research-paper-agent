# ADR 0071: Web Browsing — Search-Augmented Q&A with Provenance Guardrails

Adds a `search_web` tool that performs LLM-rewritten web searches, fetches full page text from top results, and returns structured results with provenance tags and source quality indicators. Web content enters a fourth provenance lane distinct from paper evidence, personal notes, and inference.

## Decision

### One tool, one lane, explicit capture

- **`search_web(query, source="auto")`** — a single tool with dual search backends:
  - `source="scholar"` → queries the **Semantic Scholar API** (free, no key required). Returns structured paper metadata: title, authors, year, abstract, citation count, PDF URL. Results are tagged `[cited: paper, via Semantic Scholar]` with `source_quality: peer-reviewed`. These results can flow directly into the existing paper ingestion pipeline.
  - `source="web"` → queries **DuckDuckGo** (free instant answer API, no key required). Fetches full text from top 3 result pages, extracts readable text via HTML stripping. Results tagged `[from web: domain.com]` with appropriate `source_quality`.
  - `source="auto"` (default) → the LLM decides based on the query: questions about research, papers, methods, or findings route to scholar; how-to, product, or general knowledge queries route to web.
- The LLM rewrites the user's query into 1–3 optimized search queries before calling the appropriate API
- **Fourth provenance lane** — web results are tagged `[from web: domain.com]` and presented in their own lane, distinct from `[cited: paper]` (peer-reviewed), `[from your notes]` (personal), and `[inference]` (LLM synthesis)
- **Confidence cap** — web-sourced claims are capped at Medium confidence, never High. Even directly-cited web content is not peer-reviewed
- **Explicit save only** — web results are ephemeral by default. Content enters the Knowledge Management Loop only through an explicit `save_personal_note` action, matching Hybrid Learning Control (ADR 0052)

### Source quality indicators

Every web result carries a `source_quality` tag:

| Tag | Examples |
|---|---|
| `official-docs` | Python.org, MDN, framework docs |
| `peer-reviewed` | arXiv, conference proceedings |
| `technical-blog` | Engineering blogs, tutorials |
| `forum` | Stack Overflow, Reddit, Discourse |
| `vendor` | Product pages, corporate sites |
| `unknown` | Cannot determine |

The LLM classifies the domain at result time based on URL pattern matching and content signals.

### Query formulation

The LLM rewrites the user's query into 1–3 optimized search queries before calling the search API. Concept-graph augmentation (personalizing queries with high-weight concepts from the user's graph) is deferred to a later slice.

## Rationale

- Matches ADR 0003 (ground before transforming): web claims are always cited with source URLs
- Extends ADR 0023 (three-lane answers): web becomes a fourth lane with distinct trust properties
- Respects ADR 0006 (evidence-first pushback): web content is explicitly labeled as weaker evidence than papers
- Follows ADR 0052 (hybrid learning control): web content doesn't automatically enter the PKM
- Search is the highest-value, lowest-risk entry point (vs. deep page reading or autonomous research)
- Semantic Scholar is free, structured, and returns only academic papers — an ideal match for a research paper agent. Its structured JSON output (title, authors, year, abstract, citations, PDF URL) can be ingested directly, bypassing the HTML scraping needed for general web results.
- DuckDuckGo handles non-academic queries without requiring an API key or subscription

## New Glossary Terms

- **Web Evidence** — the fourth provenance lane. Tagged `[from web: domain.com]`, presented separately from paper evidence because the trust bar is lower, but still cited with source URLs
- **Source Quality** — a classification tag on web results indicating the type of source (`official-docs`, `peer-reviewed`, `technical-blog`, `forum`, `vendor`, `unknown`), used alongside Recommendation Confidence to signal trustworthiness
- **Web Search Pipeline** — the end-to-end flow: user query → LLM query rewriting → search API → fetch top 3 pages → HTML text extraction → structured results with source_quality tags

## Consequences

- New `search_web` tool added to the agent with `source` parameter (`"scholar"`, `"web"`, `"auto"`)
- New dependencies: `httpx` (likely already transitive via ADK), `duckduckgo-search` package for free web search
- Semantic Scholar API: free, no key required, returns structured JSON with paper metadata
- Instruction updated with fourth-lane guidance, confidence cap, source quality labeling, and dual-backend routing
- Scholar results tagged `source_quality: peer-reviewed` can skip the Medium confidence cap
- `fetch_page` and Research Mode deferred to later slices based on usage
