"""Web search tool — Semantic Scholar + DuckDuckGo with provenance.

Extracted from agent.py per Python Module Architecture Plan Phase 4.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# Inter-request throttle: Semantic Scholar allows ~1 req/s without an API key.
_SCHOLAR_LAST_REQUEST: float = 0.0
_SCHOLAR_MIN_INTERVAL: float = 1.2


def classify_source_quality(url: str) -> str:
    """Classify a URL into a source quality tag."""
    domain = url.lower()
    if any(d in domain for d in [
        "arxiv.org", "semanticscholar.org", "scholar.google", "acm.org",
        "ieee.org", "springer.com", "nature.com", "science.org",
        "pubmed", "doi.org",
    ]):
        return "peer-reviewed"
    if any(d in domain for d in [
        "python.org", "docs.python", "mdn.", "devdocs.io",
        "readthedocs.io", "docs.rs", "pkg.go.dev",
    ]):
        return "official-docs"
    if any(d in domain for d in ["github.com", "gitlab.com"]):
        return "vendor"
    if any(d in domain for d in [
        "stackoverflow.com", "stackexchange.com", "reddit.com",
        "discourse", "news.ycombinator.com",
    ]):
        return "forum"
    if any(d in domain for d in [".blog", "medium.com", "dev.to", "substack.com"]):
        return "technical-blog"
    return "unknown"


def _search_semantic_scholar(query: str, limit: int = 5) -> dict[str, Any]:
    """Search Semantic Scholar API for academic papers. Free, no key required."""
    global _SCHOLAR_LAST_REQUEST

    now = time.monotonic()
    gap = now - _SCHOLAR_LAST_REQUEST
    if gap < _SCHOLAR_MIN_INTERVAL:
        time.sleep(_SCHOLAR_MIN_INTERVAL - gap)

    encoded = urllib.parse.quote(query)
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={encoded}&limit={limit}"
        f"&fields=title,authors,year,abstract,citationCount,url,externalIds"
    )

    for attempt in range(4):
        _SCHOLAR_LAST_REQUEST = time.monotonic()
        try:
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "ResearchPaperAgent/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 3:
                retry_after = exc.headers.get("Retry-After") if hasattr(exc, "headers") else None
                wait = float(retry_after) if retry_after else 2 ** (attempt + 1)
                wait += time.monotonic() % 1.0
                logger.warning("Semantic Scholar 429 (attempt %d/4), waiting %.1fs", attempt + 1, wait)
                time.sleep(wait)
                continue
            return {
                "status": "error", "backend": "semantic_scholar",
                "message": f"HTTP {exc.code}",
            }
        except Exception as exc:
            return {"status": "error", "backend": "semantic_scholar", "message": str(exc)[:300]}

    papers = data.get("data", [])
    results = []
    for paper in papers:
        authors = [a.get("name", "") for a in paper.get("authors", [])]
        ext_ids = paper.get("externalIds", {})
        paper_url = paper.get("url") or (
            f"https://doi.org/{ext_ids.get('DOI')}" if ext_ids.get("DOI") else ""
        )
        results.append({
            "title": paper.get("title", "Unknown"),
            "authors": authors[:5],
            "year": paper.get("year"),
            "abstract": (paper.get("abstract") or "")[:600],
            "citations": paper.get("citationCount", 0),
            "url": paper_url,
            "source_quality": "peer-reviewed",
            "provenance": f"[cited: paper, via Semantic Scholar] — {paper.get('title', 'Unknown')[:120]}",
        })
    return {
        "status": "ok", "backend": "semantic_scholar", "query": query,
        "total_results": data.get("total", len(results)), "results": results,
    }


def _search_duckduckgo(query: str, limit: int = 5) -> dict[str, Any]:
    """Search DuckDuckGo using the ddgs package."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return _search_duckduckgo_fallback(query, limit)

    results = []
    try:
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=limit):
                href = result.get("href", "")
                if any(skip in href.lower() for skip in ["/definition/", "duckduckgo.com/?q="]):
                    continue
                results.append({
                    "title": (result.get("title") or "")[:200],
                    "abstract": (result.get("body") or "")[:600],
                    "url": href,
                    "source_quality": classify_source_quality(href),
                    "provenance": f"[from web: {href[:80]}] — {(result.get('title') or '')[:120]}",
                })
    except Exception:
        return _search_duckduckgo_fallback(query, limit)

    if not results:
        return _search_duckduckgo_fallback(query, limit)

    return {
        "status": "ok", "backend": "duckduckgo", "query": query,
        "total_results": len(results), "results": results[:limit],
    }


def _search_duckduckgo_fallback(query: str, limit: int = 5) -> dict[str, Any]:
    """Fallback: DuckDuckGo instant answers API."""
    encoded = urllib.parse.quote(query)
    url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ResearchPaperAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        return {"status": "error", "backend": "duckduckgo", "message": str(exc)[:300]}

    results = []
    abstract = (data.get("AbstractText") or "").strip()
    if abstract:
        results.append({
            "title": data.get("Heading", "Instant Answer"),
            "abstract": abstract[:800],
            "url": data.get("AbstractURL", ""),
            "source_quality": classify_source_quality(data.get("AbstractURL", "")),
            "provenance": f"[from web: duckduckgo.com] — {data.get('Heading', 'Instant Answer')[:120]}",
        })
    for topic in data.get("RelatedTopics", [])[:limit - len(results)]:
        text = (topic.get("Text") or "").strip()
        url = topic.get("FirstURL", "")
        if text and url:
            results.append({
                "title": text.split(" - ")[0][:120] if " - " in text else text[:120],
                "abstract": text[:600],
                "url": url,
                "source_quality": classify_source_quality(url),
                "provenance": f"[from web: {url.split('/')[2] if '//' in url else 'duckduckgo.com'}] — {text[:120]}",
            })
    return {
        "status": "ok", "backend": "duckduckgo_fallback", "query": query,
        "total_results": len(results), "results": results[:limit],
    }


def search_web(query: str, source: str = "auto") -> dict[str, Any]:
    """Search the web with dual backends for scholarly and general queries."""
    query = query.strip()
    if not query:
        return {"status": "error", "message": "search query is required"}

    if source == "auto":
        academic_signals = [
            "paper", "research", "study", "method", "finding", "abstract",
            "doi", "arxiv", "et al", "experiment", "baseline", "benchmark",
            "peer review", "citation", "conference", "journal",
        ]
        lower = query.lower()
        source = "scholar" if any(sig in lower for sig in academic_signals) else "web"

    if source == "scholar":
        return _search_semantic_scholar(query)
    return _search_duckduckgo(query)
