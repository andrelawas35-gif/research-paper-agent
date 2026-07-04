# Shared Agent Infrastructure — Reusable Modules

**Created:** 2026-07-04
**Status:** Stable (132 tests, 0 failures)

The `agent_runtime/` package beneath `research_paper_agent/` is domain-agnostic
infrastructure.  A new agent (trading, writing, coding, etc.) imports these
modules and provides its own instruction text, mode taxonomy, and tools.

---

## Reusable Modules

### `agent_runtime/paths.py`

Shared path constants and utilities.  Any new agent should create its own
`paths.py` (or reuse these if co-located).

| Export | Signature | Notes |
|---|---|---|
| `ensure_dirs()` | `() -> None` | Creates standard data directories |
| `now_iso()` | `() -> str` | Current UTC time as ISO 8601 |
| `APP_DIR` / `USER_MODEL_DIR` / etc. | `Path` | Path constants |

### `agent_runtime/dynamic_context.py`

Performance Budget engine (ADR 0072).  Controls how much context the LLM
sees per turn and gates runtime behavior.

| Export | Signature | Notes |
|---|---|---|
| `build_dynamic_instruction(ctx)` | `(Any) -> str` | Drop-in `instruction=` callable for ADK `Agent` |
| `build_before_model_callback()` | `() -> Callable` | Drop-in `before_model_callback=` for ADK `Agent` |
| `_infer_performance_budget(ctx)` | `(Any) -> str` | Returns `"fast"`, `"balanced"`, or `"deep"` |
| `_infer_performance_budget_from_text(text, mode_hint="")` | `(str, str) -> str` | Pure function — testable budget inference |
| `write_allowed(action_type, budget, evidence_strength)` | `(str, str, str) -> bool` | Gating helper for durable writes |
| `state_fingerprint()` | `() -> str` | Hash of durable state files (for cache keys) |
| `_SNAPSHOT_CACHE` | `dict` | Budget-aware snapshot cache |
| `FAST` / `BALANCED` / `DEEP` | `str` | Budget tier constants |

**Usage pattern for a new agent:**

```python
from research_paper_agent.agent_runtime.dynamic_context import (
    build_dynamic_instruction,
    build_before_model_callback,
)

agent = Agent(
    model=MyLlm(),
    name="trading_agent",
    static_instruction=MY_STATIC_INSTRUCTION,
    instruction=build_dynamic_instruction,
    before_model_callback=build_before_model_callback(),
    tools=[...],
)
```

### `agent_runtime/retrieval.py`

Text utilities and evidence search.  Generic — works on any ingested passages.

| Export | Signature | Notes |
|---|---|---|
| `tokenize(text)` | `(str) -> list[str]` | Word tokenizer with stopword filtering |
| `sentences(text)` | `(str) -> list[str]` | Sentence splitter (>40 char minimum) |
| `keywords(text, limit=30)` | `(str, int) -> list[str]` | Top words by frequency |
| `citation(source, page, passage_id)` | `(str, int|None, str) -> str` | Standard citation formatter |
| `score_passage(query_terms, passage, doc_count, doc_freq)` | `(...) -> float` | TF-IDF + bonuses |
| `search_evidence(query, max_passages, evidence_scope)` | `(str, int, str) -> dict` | Ranked passage search |
| `STOPWORDS` | `frozenset[str]` | Stopword list |
| `SECTION_PATTERNS` | `dict[str, str]` | Regex patterns for paper sections |

### `agent_runtime/papers.py`

Paper/file ingestion and management.  Generic — works on any txt/md/pdf files.

| Export | Signature | Notes |
|---|---|---|
| `list_papers()` | `() -> dict` | List available files |
| `ingest_paper(file_name, evidence_scope)` | `(str, str) -> dict` | Read + index one file |
| `ingest_all_papers()` | `() -> dict` | Batch ingest |
| `rename_paper(old, new)` | `(str, str) -> dict` | Atomic rename (file + KB + graph) |
| `delete_paper(file_name, dry_run)` | `(str, bool) -> dict` | Delete with preview |
| `organize_papers(mapping)` | `(dict) -> dict` | Batch rename/move |
| `list_concepts()` | `() -> dict` | Concepts grouped by source |
| `paper_brief(source)` | `(str) -> dict` | Compact summary |
| `compare_papers(topic)` | `(str) -> dict` | Cross-paper comparison |
| `make_study_guide(source, question_count)` | `(str, int) -> dict` | Citation-backed study questions |

### `agent_runtime/web_search.py`

External search with provenance tagging.

| Export | Signature | Notes |
|---|---|---|
| `search_web(query, source="auto")` | `(str, str) -> dict` | Dual-backend: scholar or web |
| `classify_source_quality(url)` | `(str) -> str` | `peer-reviewed`, `official-docs`, `forum`, etc. |

---

## Domain Modules (Reference Patterns)

These modules contain domain-specific logic that would be different for a
trading agent.  They serve as patterns to follow, not as reusable code.

### `agent_runtime/grill.py`

Personalized question generation.  Pattern: imports profile + records →
generates ranked questions → records session.

**Trading equivalent:** Signal generation — imports market data + strategy
config → generates ranked trade ideas → logs signals.

### `agent_runtime/tutor.py`

Progress tracking, answer grading, next-concept selection.

**Trading equivalent:** Backtest result tracking, trade grading (win/loss
analysis), next-strategy selection.

### `agent_runtime/audit.py`

Inspectable knowledge state across all channels.

**Trading equivalent:** Portfolio audit — inspect P&L, win rate, Sharpe,
drawdown, strategy performance, signal accuracy.

---

## Standalone Domain Modules (Reusable As-Is)

These are in the root package, domain-agnostic, and importable directly.

| Module | What it does | Trading use |
|---|---|---|
| `personal_notes.py` | JSONL note store + Markdown mirrors | Trade journal, strategy notes, backtest observations |
| `concept_graph.py` | Bipartite interest↔concept graph | "mean reversion" → "pairs trading" → "cointegration" |
| `relationship_management.py` | People + interaction tracking | Track analysts, mentors, trading partners |

---

## How to Build a New Agent on This Infrastructure

### Step 1: Create the package

```
trading_agent/
├── __init__.py
├── agent.py              ← Agent construction (2-3 screens)
├── agent_runtime/
│   ├── __init__.py
│   ├── paths.py          ← Trading-specific paths
│   ├── market_data.py    ← yfinance, Alpaca, Polygon
│   ├── backtest.py       ← Backtesting engine
│   ├── signals.py        ← Signal generation (grill.py pattern)
│   └── portfolio.py      ← Position + P&L tracking
├── knowledge_base/       ← Financial paper records
├── papers/               ← Trading whitepapers, SEC filings
├── user_model/           ← Trading preferences
├── tests/
└── requirements.txt
```

### Step 2: Write `agent.py`

```python
from google.adk.agents.llm_agent import Agent
from research_paper_agent.agent_runtime.dynamic_context import (
    build_dynamic_instruction,
    build_before_model_callback,
)
from research_paper_agent.agent_runtime.papers import (
    ingest_paper, list_papers, paper_brief, search_evidence,
)
from research_paper_agent.agent_runtime.web_search import search_web
from research_paper_agent import personal_notes, concept_graph

from .agent_runtime.market_data import fetch_quotes, fetch_financials
from .agent_runtime.backtest import run_backtest
from .agent_runtime.signals import generate_signals

_TRADING_INSTRUCTION = """You are an algorithmic trading research agent..."""

trading_agent = Agent(
    model=DeepSeekLlm(),
    name="trading_agent",
    static_instruction=_TRADING_INSTRUCTION,
    instruction=build_dynamic_instruction,
    before_model_callback=build_before_model_callback(),
    tools=[
        # Shared infrastructure
        ingest_paper, list_papers, paper_brief, search_evidence,
        search_web, personal_notes.save_note, concept_graph.get_concept_graph,
        # Trading-specific
        fetch_quotes, fetch_financials, run_backtest, generate_signals,
    ],
)
```

### Step 3: Write the instruction

The `_STATIC_INSTRUCTION` is where the domain lives.  Key trading-specific
sections:

- **Mode taxonomy:** Backtest, Signal, Portfolio, Risk, Research, Journal
- **Evidence rules:** Price data is time-stamped, backtests are synthetic,
  live markets are ground truth
- **Risk guardrails:** Never suggest position sizes, always cite drawdown
  risk, distinguish in-sample from out-of-sample
- **Provenance lanes:** `[price data: source]`, `[backtest: config]`,
  `[paper: citation]`, `[inference]`

---

## What NOT to Reuse

| Component | Reason |
|---|---|
| `_STATIC_INSTRUCTION` | Deeply domain-specific — write a new one |
| Mode taxonomy | Grill/Tutor/Mentor don't apply to trading |
| `agent_runtime/grill.py` | Grill questions are paper-specific |
| `agent_runtime/tutor.py` | Tutor grading is pedagogy, not P&L |
| `agent_runtime/audit.py` | Audit views are paper-knowledge, not portfolio |
| User profile schema | Add `risk_tolerance`, `time_horizon`, `asset_classes` |
| `root_agent` construction | Build a new `Agent` instance |
