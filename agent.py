from __future__ import annotations

import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from google.adk.agents.llm_agent import Agent

logger = logging.getLogger(__name__)
from google.adk.labs.openai import OpenAILlm
from openai import AsyncOpenAI
from openai import OpenAI

from . import concept_graph, personal_notes, relationship_management
from .agent_runtime import dynamic_context as _dynamic_ctx
from .agent_runtime.paths import ensure_dirs as _ensure_dirs_impl

# ── Architecture Plan Phase 3: paper tools + retrieval from agent_runtime ─
from .agent_runtime.retrieval import (  # noqa: E402, F401
    search_evidence as _rt_search_evidence,
)
from .agent_runtime.papers import (  # noqa: E402, F401
    compare_papers as _rt_compare_papers,
    delete_paper as _rt_delete_paper,
    ingest_all_papers as _rt_ingest_all_papers,
    ingest_paper as _rt_ingest_paper,
    list_concepts as _rt_list_concepts,
    list_papers as _rt_list_papers,
    make_study_guide as _rt_make_study_guide,
    organize_papers as _rt_organize_papers,
    paper_brief as _rt_paper_brief,
    rename_paper as _rt_rename_paper,
)

# Override public paper/search tools with agent_runtime implementations.
search_evidence = _rt_search_evidence
compare_papers = _rt_compare_papers
delete_paper = _rt_delete_paper
ingest_all_papers = _rt_ingest_all_papers
ingest_paper = _rt_ingest_paper
list_concepts = _rt_list_concepts
list_papers = _rt_list_papers
make_study_guide = _rt_make_study_guide
organize_papers = _rt_organize_papers
paper_brief = _rt_paper_brief
rename_paper = _rt_rename_paper

# ── Architecture Plan Phase 4: mode-specific modules ───────────────────────────────────
from .agent_runtime.web_search import (  # noqa: E402
    classify_source_quality as _ws_classify_source_quality,
    search_web as _ws_search_web,
)
from .agent_runtime.audit import (  # noqa: E402
    knowledge_self_audit as _audit_knowledge_self_audit,
    self_audit_correction as _audit_self_audit_correction,
)
from .agent_runtime.grill import (  # noqa: E402
    adaptive_grill as _grill_adaptive_grill,
    respond_to_adaptive_grill as _grill_respond_to_adaptive_grill,
)
from .agent_runtime.tutor import (  # noqa: E402
    _grade_answer as _tutor_grade_answer,
    _load_tutor_progress as _tutor_load_tutor_progress,
    _next_concept as _tutor_next_concept,
    _save_tutor_progress as _tutor_save_tutor_progress,
    _validate_tutor_progress as _tutor_validate_tutor_progress,
)

search_web = _ws_search_web
_classify_source_quality = _ws_classify_source_quality
knowledge_self_audit = _audit_knowledge_self_audit
self_audit_correction = _audit_self_audit_correction
adaptive_grill = _grill_adaptive_grill
respond_to_adaptive_grill = _grill_respond_to_adaptive_grill
_grade_answer = _tutor_grade_answer
_load_tutor_progress = _tutor_load_tutor_progress
_next_concept = _tutor_next_concept
_save_tutor_progress = _tutor_save_tutor_progress
_validate_tutor_progress = _tutor_validate_tutor_progress


APP_DIR = Path(__file__).resolve().parent
PAPERS_DIR = APP_DIR / "papers"
KNOWLEDGE_DIR = APP_DIR / "knowledge_base"
USER_MODEL_DIR = APP_DIR / "user_model"
USER_PROFILE_PATH = USER_MODEL_DIR / "profile.json"
INTERACTION_LOG_PATH = USER_MODEL_DIR / "interaction_log.jsonl"
GRILL_LOG_PATH = USER_MODEL_DIR / "adaptive_grill_sessions.jsonl"
CANDIDATE_SIGNALS_PATH = USER_MODEL_DIR / "candidate_signals.jsonl"
CONCEPT_GRAPH_PATH = USER_MODEL_DIR / "concept_graph.json"
TUTOR_PROGRESS_PATH = USER_MODEL_DIR / "tutor_progress.json"
TUTOR_SESSIONS_PATH = USER_MODEL_DIR / "tutor_sessions.jsonl"
PERSONAL_NOTES_PATH = USER_MODEL_DIR / "personal_notes.jsonl"
PEOPLE_PATH = USER_MODEL_DIR / "people.jsonl"
SESSION_META_PATH = USER_MODEL_DIR / "session_meta.jsonl"

# Inter-request throttle: Semantic Scholar allows ~1 req/s without an API key.
# Each call to _search_semantic_scholar drains the token bucket before sending.
_SCHOLAR_LAST_REQUEST: float = 0.0
_SCHOLAR_MIN_INTERVAL: float = 1.2  # seconds between requests (little margin above 1.0)


# ── ADR 0070: Record schemas ────────────────────────────────────────


class UserProfile(TypedDict, total=False):
    schema_version: int
    updated_at: str
    summary: str
    interests: list[dict[str, Any]]
    style_preferences: list[dict[str, Any]]
    adaptation_rules: list[dict[str, Any]]
    avoidances: list[dict[str, Any]]
    polish_preferences: dict[str, str]
    grammar_and_quirks: list[dict[str, Any]]
    question_patterns: list[dict[str, Any]]
    last_learned_from: str
    recovery_note: str


class CandidateSignal(TypedDict, total=False):
    timestamp: str
    source: str
    signals: list[dict[str, Any]]


class TutorProgress(TypedDict, total=False):
    schema_version: int
    updated_at: str
    concepts: dict[str, dict[str, Any]]
    last_session: str
    recovery_note: str


STOPWORDS = {
    "about",
    "abstract",
    "after",
    "again",
    "against",
    "and",
    "are",
    "also",
    "among",
    "because",
    "before",
    "between",
    "can",
    "could",
    "figure",
    "first",
    "for",
    "from",
    "have",
    "into",
    "more",
    "most",
    "other",
    "paper",
    "results",
    "section",
    "show",
    "shows",
    "such",
    "table",
    "than",
    "that",
    "the",
    "their",
    "these",
    "this",
    "through",
    "using",
    "were",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}

SECTION_PATTERNS = {
    "abstract": r"\babstract\b",
    "introduction": r"\bintroduction\b",
    "methods": r"\b(method|approach|model|architecture|dataset|experiment|training|evaluation|implementation)\b",
    "findings": r"\b(result|finding|improve|outperform|demonstrate|show|evidence|accuracy|performance)\b",
    "limitations": r"\b(limitation|limited|challenge|risk|failure|bias|constraint|threat|future work)\b",
    "open_questions": r"\b(open question|future|unknown|unclear|further research|remains|next step)\b",
}


def _deepseek_max_tokens() -> int:
    raw_value = os.getenv("DEEPSEEK_MAX_TOKENS", "4096")
    try:
        return int(raw_value)
    except ValueError:
        return 4096


class DeepSeekLlm(OpenAILlm):
    """OpenAI-compatible ADK model wrapper for the DeepSeek API."""

    model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    max_tokens: int = _deepseek_max_tokens()

    @property
    def api_key(self) -> str | None:
        return os.getenv("DEEPSEEK_API_KEY")

    @property
    def base_url(self) -> str:
        return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    @property
    def _openai_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)


def _ensure_dirs() -> None:
    _ensure_dirs_impl()


def _read_pdf_pages(path: Path) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF support requires pypdf. Install project dependencies with: "
            "python3.13.exe -m pip install -r research_paper_agent\\requirements.txt"
        ) from exc

    reader = PdfReader(str(path))
    pages = []
    ocr_attempted = False  # lazy init — only import OCR deps if needed

    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        # OCR fallback: when pypdf returns no text, try Tesseract on a
        # rendered page image.  This handles scanned/image-based PDFs.
        if not text.strip():
            if not ocr_attempted:
                try:
                    import fitz  # PyMuPDF — self-contained PDF renderer
                    import pytesseract
                    from PIL import Image  # noqa: F401 — validates Pillow is present

                    # Point pytesseract at the Tesseract OCR engine.
                    _TESSERACT_PATHS = [
                        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                    ]
                    for tp in _TESSERACT_PATHS:
                        if Path(tp).exists():
                            pytesseract.pytesseract.tesseract_cmd = tp
                            break

                    ocr_attempted = True
                    _ocr_available = True
                except ImportError:
                    _ocr_available = False
                    ocr_attempted = True
                except Exception:
                    _ocr_available = False
                    ocr_attempted = True

            if _ocr_available:
                try:
                    doc = fitz.open(str(path))
                    page_obj = doc.load_page(index - 1)  # fitz is 0-indexed
                    pix = page_obj.get_pixmap(dpi=300)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    text = pytesseract.image_to_string(img)
                    doc.close()
                except Exception:
                    pass  # OCR failed for this page — skip it

            if not text.strip():
                continue  # nothing extractable from this page

        pages.append({"page": index, "text": text})

    return pages


def _read_paper_pages(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return [{"page": None, "text": text}]
    if suffix == ".pdf":
        return _read_pdf_pages(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def _tokenize(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
        if word not in STOPWORDS
    ]


def _sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", compact)
        if len(sentence.strip()) > 40
    ]


def _keywords(text: str, limit: int = 30) -> list[str]:
    counts = Counter(_tokenize(text))
    return [word for word, _ in counts.most_common(limit)]


def _citation(source: str, page: int | None, passage_id: str) -> str:
    if page is None:
        return f"{source}, {passage_id}"
    return f"{source}, page {page}, {passage_id}"


def _extract_metadata(source: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    text = "\n".join(page["text"] for page in pages)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = source
    for line in lines[:20]:
        if 8 <= len(line) <= 180 and not re.match(r"^(abstract|introduction)\b", line, re.I):
            title = line
            break

    doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", text, re.I)
    arxiv_match = re.search(r"\barXiv[:\s]+(\d{4}\.\d{4,5}(?:v\d+)?)\b", text, re.I)
    year_match = re.search(r"\b(19|20)\d{2}\b", text)

    return {
        "title": title,
        "source": source,
        "year": year_match.group(0) if year_match else None,
        "doi": doi_match.group(0) if doi_match else None,
        "arxiv_id": arxiv_match.group(1) if arxiv_match else None,
    }


def _make_passages(source: str, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    passages = []
    counter = 1
    for page in pages:
        sentence_buffer: list[str] = []
        for sentence in _sentences(page["text"]):
            sentence_buffer.append(sentence)
            joined = " ".join(sentence_buffer)
            if len(joined) >= 450 or len(sentence_buffer) >= 3:
                passage_id = f"P{counter:04d}"
                passages.append(
                    {
                        "id": passage_id,
                        "source": source,
                        "page": page["page"],
                        "citation": _citation(source, page["page"], passage_id),
                        "text": joined[:1400],
                        "keywords": _keywords(joined, 12),
                    }
                )
                sentence_buffer = []
                counter += 1
        if sentence_buffer:
            passage_id = f"P{counter:04d}"
            joined = " ".join(sentence_buffer)
            passages.append(
                {
                    "id": passage_id,
                    "source": source,
                    "page": page["page"],
                    "citation": _citation(source, page["page"], passage_id),
                    "text": joined[:1400],
                    "keywords": _keywords(joined, 12),
                }
            )
            counter += 1
    return passages[:240]


def _extract_candidate_notes(text: str, passages: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, str]]] = {
        "abstract": [],
        "methods": [],
        "findings": [],
        "limitations": [],
        "open_questions": [],
    }

    for passage in passages:
        passage_text = passage["text"]
        for bucket, pattern in SECTION_PATTERNS.items():
            if bucket == "introduction":
                continue
            if re.search(pattern, passage_text, re.IGNORECASE) and len(buckets[bucket]) < 12:
                buckets[bucket].append(
                    {"citation": passage["citation"], "text": passage_text[:700]}
                )

    concepts = []
    for keyword in _keywords(text, 40):
        supporting_passage = next(
            (p for p in passages if keyword in p["keywords"] or keyword in p["text"].lower()),
            None,
        )
        concepts.append(
            {
                "name": keyword,
                "citation": supporting_passage["citation"] if supporting_passage else None,
            }
        )

    return {
        "concepts": concepts[:30],
        "methods": buckets["methods"],
        "findings": buckets["findings"],
        "limitations": buckets["limitations"],
        "open_questions": buckets["open_questions"],
    }


def _paper_record_path(paper_path: Path) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", paper_path.stem)
    return KNOWLEDGE_DIR / f"{safe_name}.json"


def _normalize_evidence_scopes(value: str | list[str] | tuple[str, ...] | None = None) -> list[str]:
    """Normalize user/tool supplied evidence scope labels."""
    if value is None:
        raw_items: list[str] = []
    elif isinstance(value, str):
        raw_items = re.split(r"[,;\s]+", value)
    else:
        raw_items = [str(item) for item in value]

    scopes: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        scopes.append(normalized)
    return scopes


def _infer_evidence_scopes(file_name: str) -> list[str]:
    """Suggest scopes from import location/name; stored metadata remains canonical."""
    parts = [part.lower() for part in Path(file_name).parts]
    joined = " ".join(parts)
    scopes: list[str] = []
    if "simon" in joined:
        scopes.append("mentor:simon")
    if "lanier" in joined or "jaron" in joined:
        scopes.append("mentor:lanier")
    return scopes


def _record_evidence_scopes(record: dict[str, Any]) -> set[str]:
    """Return canonical scope labels stored on a knowledge-base record."""
    scopes = set(_normalize_evidence_scopes(record.get("evidence_scope")))

    metadata = record.get("metadata", {})
    if isinstance(metadata, dict):
        scopes.update(_normalize_evidence_scopes(metadata.get("evidence_scope")))
        collection = str(metadata.get("collection", "")).strip().lower()
        mentor = str(metadata.get("mentor", "")).strip().lower()
        if collection:
            scopes.add(collection)
        if collection == "mentor" and mentor:
            scopes.add(f"mentor:{mentor}")

    collection = str(record.get("collection", "")).strip().lower()
    mentor = str(record.get("mentor", "")).strip().lower()
    if collection:
        scopes.add(collection)
    if collection == "mentor" and mentor:
        scopes.add(f"mentor:{mentor}")
    return scopes


def _filter_records_by_scope(
    records: list[dict[str, Any]],
    evidence_scope: str | list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    scopes = set(_normalize_evidence_scopes(evidence_scope))
    if not scopes:
        return records
    return [record for record in records if scopes.intersection(_record_evidence_scopes(record))]


def _load_records() -> list[dict[str, Any]]:
    """Load ingested paper records, cached in memory after first read."""
    cache = getattr(_load_records, "_cache", None)
    if cache is not None:
        return cache
    _ensure_dirs()
    records = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    _load_records._cache = records  # type: ignore[attr-defined]
    return records


def _all_passages(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [passage for record in records for passage in record.get("passages", [])]


def _score_passage(query_terms: list[str], passage: dict[str, Any], document_count: int, doc_freq: Counter) -> float:
    text = passage["text"].lower()
    passage_terms = Counter(_tokenize(text))
    if not passage_terms:
        return 0.0

    score = 0.0
    for term in query_terms:
        tf = passage_terms.get(term, 0)
        if not tf:
            continue
        idf = math.log((document_count + 1) / (doc_freq.get(term, 0) + 1)) + 1
        score += (1 + math.log(tf)) * idf

    query_phrase = " ".join(query_terms)
    if query_phrase and query_phrase in text:
        score += 3.0

    for keyword in passage.get("keywords", []):
        if keyword in query_terms:
            score += 0.35

    return round(score, 4)


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Delegates to agent_runtime.paths.now_iso.
    """
    from .agent_runtime.paths import now_iso as _paths_now_iso

    return _paths_now_iso()


def _parse_iso_datetime(value: str, field_name: str, errors: list[str]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} must be an ISO 8601 timestamp")
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _default_user_profile() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": _now_iso(),
        "summary": (
            "The user is building a local research-paper agent and values direct, "
            "iterative improvements that become runnable quickly."
        ),
        "interests": [
            {
                "name": "research agents",
                "evidence": "Asked for an agent that reads papers, extracts concepts, and answers questions.",
                "confidence": 0.8,
            },
            {
                "name": "self-improving local assistants",
                "evidence": "Asked for the agent to improve itself around interests, grammar, quirks, and question patterns.",
                "confidence": 0.75,
            },
        ],
        "question_patterns": [
            {
                "pattern": "short directive requests",
                "evidence": "Uses prompts such as 'okay go improve it' and 'how do I talk to the agent'.",
                "confidence": 0.7,
            }
        ],
        "style_preferences": [
            {
                "preference": "prefer direct implementation over long planning",
                "evidence": "Repeatedly asks to make or improve the agent.",
                "confidence": 0.75,
            },
            {
                "preference": "give more lengthy, personality-shaped answers for explanations, synthesis, and recommendations",
                "evidence": "User asked for more lengthy answers based on their personality.",
                "confidence": 0.9,
            },
            {
                "preference": "keep run commands concrete",
                "evidence": "Asked how to talk to the agent after it was built.",
                "confidence": 0.65,
            },
        ],
        "grammar_and_quirks": [
            {
                "observation": "casual lowercase phrasing is normal",
                "evidence": "Examples include 'how do I improve the agent' and 'okay go improve it'.",
                "confidence": 0.65,
            }
        ],
        "adaptation_rules": [
            {
                "rule": "When a request is actionable, implement first and summarize what changed.",
                "source": "conversation pattern",
                "confidence": 0.8,
            },
            {
                "rule": "Offer concrete commands and file locations when discussing how to use the agent.",
                "source": "conversation pattern",
                "confidence": 0.7,
            },
            {
                "rule": "For research answers, ground claims in cited paper passages.",
                "source": "research-agent purpose",
                "confidence": 0.9,
            },
            {
                "rule": "For research synthesis and personalized recommendations, answer with more depth, context, and interpretive connective tissue before ending with concrete next steps.",
                "source": "conversation pattern",
                "confidence": 0.9,
            },
        ],
        "avoidances": [
            {
                "rule": "Do not treat casual grammar as an error unless the user asks for writing feedback.",
                "source": "personalization request",
                "confidence": 0.7,
            }
        ],
        "polish_preferences": {
            "default": "moderate",
        },
    }


def _validate_profile(profile: dict[str, Any]) -> bool:
    """Return True if the profile has all required top-level fields."""
    if not isinstance(profile.get("schema_version"), int):
        return False
    if not isinstance(profile.get("interests"), list):
        return False
    if not isinstance(profile.get("style_preferences"), list):
        return False
    if not isinstance(profile.get("adaptation_rules"), list):
        return False
    if not isinstance(profile.get("avoidances"), list):
        return False
    polish = profile.get("polish_preferences")
    if polish is not None and not isinstance(polish, dict):
        return False
    return True


def _load_user_profile() -> dict[str, Any]:
    """Load the user profile, cached in memory after first read."""
    cache = getattr(_load_user_profile, "_cache", None)
    if cache is not None:
        return cache
    _ensure_dirs()
    if not USER_PROFILE_PATH.exists():
        profile = _default_user_profile()
        USER_PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        return profile
    try:
        profile = json.loads(USER_PROFILE_PATH.read_text(encoding="utf-8"))
        if not _validate_profile(profile):
            logger.warning("Profile failed validation, restoring defaults")
            profile = _default_user_profile()
            profile["recovery_note"] = "profile.json failed validation and defaults were restored."
            USER_PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        _load_user_profile._cache = profile  # type: ignore[attr-defined]
        return profile
    except json.JSONDecodeError:
        profile = _default_user_profile()
        profile["recovery_note"] = "profile.json was unreadable and defaults were restored."
        USER_PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        _load_user_profile._cache = profile  # type: ignore[attr-defined]
        return profile


def _save_user_profile(profile: dict[str, Any]) -> None:
    _ensure_dirs()
    profile["updated_at"] = _now_iso()
    USER_PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    _load_user_profile._cache = profile  # type: ignore[attr-defined]


def _append_unique_signal(profile: dict[str, Any], bucket: str, key: str, item: dict[str, Any]) -> bool:
    existing = profile.setdefault(bucket, [])
    normalized = str(item.get(key, "")).strip().lower()
    if not normalized:
        return False
    for current in existing:
        if str(current.get(key, "")).strip().lower() == normalized:
            current["confidence"] = max(
                float(current.get("confidence", 0.5)),
                float(item.get("confidence", 0.55)),
            )
            current["evidence"] = item.get("evidence", current.get("evidence", ""))
            return False
    existing.append(item)
    return True


def _infer_message_signals(message: str) -> dict[str, list[dict[str, Any]]]:
    lower = message.lower()
    words = _tokenize(message)
    signals: dict[str, list[dict[str, Any]]] = {
        "interests": [],
        "question_patterns": [],
        "style_preferences": [],
        "grammar_and_quirks": [],
        "polish_corrections": [],
    }

    topic_map = {
        "agent": "agents and assistant behavior",
        "paper": "research papers",
        "papers": "research papers",
        "concept": "concept extraction",
        "question": "question answering",
        "grammar": "personal writing style",
        "quirk": "personal communication quirks",
        "interest": "personalization around interests",
        "improve": "iterative self-improvement",
        "docs": "documented design decisions",
    }
    for trigger, interest in topic_map.items():
        if trigger in lower:
            signals["interests"].append(
                {
                    "name": interest,
                    "evidence": message[:240],
                    "confidence": 0.6,
                }
            )

    if re.match(r"^\s*(how|what|why|where|when|can|do|does)\b", lower):
        signals["question_patterns"].append(
            {
                "pattern": "plain-language direct question",
                "evidence": message[:240],
                "confidence": 0.62,
            }
        )
    if len(words) <= 12:
        signals["question_patterns"].append(
            {
                "pattern": "short high-context prompt",
                "evidence": message[:240],
                "confidence": 0.64,
            }
        )
        signals["style_preferences"].append(
            {
                "preference": "respond with concrete next steps, adding more depth when the request asks for explanation, synthesis, or personality fit",
                "evidence": message[:240],
                "confidence": 0.58,
            }
        )
    if message and message[:1].islower():
        signals["grammar_and_quirks"].append(
            {
                "observation": "often starts messages in lowercase",
                "evidence": message[:240],
                "confidence": 0.55,
            }
        )
    if "go " in lower or lower.startswith(("make ", "add ", "improve ", "fix ")):
        signals["style_preferences"].append(
            {
                "preference": "when intent is clear, take action without a long preamble",
                "evidence": message[:240],
                "confidence": 0.68,
            }
        )

    # ── ADR 0066: Polish preference corrections ─────────────────────
    if any(phrase in lower for phrase in [
        "keep my wording", "don't rewrite", "leave my words",
        "don't change my wording", "that's not what i meant",
        "you changed what i said", "exact wording",
    ]):
        signals["polish_corrections"].append(
            {"context": "default", "level": "none",
             "evidence": message[:240], "confidence": 0.75}
        )
    if any(phrase in lower for phrase in [
        "too formal", "just fix grammar", "only fix errors",
        "don't change the style",
    ]):
        signals["polish_corrections"].append(
            {"context": "default", "level": "light",
             "evidence": message[:240], "confidence": 0.75}
        )
    if any(phrase in lower for phrase in [
        "too casual", "make it flow better", "polish this up",
        "make this sound better", "can you improve this",
    ]):
        signals["polish_corrections"].append(
            {"context": "default", "level": "full",
             "evidence": message[:240], "confidence": 0.7}
        )
    # Context-specific corrections.
    for ctx_word, ctx_key in [("chat", "chat"), ("technical", "technical"),
                               ("creative", "creative")]:
        if ctx_word in lower:
            for corr in signals["polish_corrections"]:
                corr["context"] = ctx_key

    return signals


def _profile_signal_summary(profile: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "interests": [item.get("name", "") for item in profile.get("interests", [])[:8]],
        "question_patterns": [
            item.get("pattern", "") for item in profile.get("question_patterns", [])[:5]
        ],
        "style_preferences": [
            item.get("preference", "") for item in profile.get("style_preferences", [])[:5]
        ],
        "quirks": [
            item.get("observation", "") for item in profile.get("grammar_and_quirks", [])[:5]
        ],
    }


def _note_cards_for_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards = []
    for record in records:
        title = record.get("metadata", {}).get("title", record["source"])
        notes = record.get("notes", {})
        for bucket in ["methods", "findings", "limitations", "open_questions"]:
            for item in notes.get(bucket, [])[:4]:
                cards.append(
                    {
                        "source": record["source"],
                        "title": title,
                        "bucket": bucket,
                        "citation": item.get("citation"),
                        "text": item.get("text", ""),
                    }
                )
        for concept in notes.get("concepts", [])[:8]:
            cards.append(
                {
                    "source": record["source"],
                    "title": title,
                    "bucket": "concept",
                    "citation": concept.get("citation"),
                    "text": concept.get("name", ""),
                }
            )
    return cards


def _try_annotate_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Best-effort concept-graph annotation; returns brief unchanged on failure."""
    try:
        profile = _load_user_profile()
        user_interests = [item.get("name", "") for item in profile.get("interests", [])]
        return concept_graph.annotate(brief, user_interests)
    except Exception:
        return brief


def _adaptive_question(
    question_id: str,
    question: str,
    recommendation: str,
    reason: str,
    source: str = "",
    citation: str | None = None,
    profile_signal: str = "",
) -> dict[str, Any]:
    return {
        "id": question_id,
        "question": question,
        "recommendation": recommendation,
        "why_this_question": reason,
        "source": source or None,
        "citation": citation,
        "profile_signal": profile_signal or None,
    }


def _append_grill_session(session: dict[str, Any]) -> None:
    _ensure_dirs()
    with GRILL_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(session) + "\n")


def _record_candidate_signals(event: dict[str, Any]) -> None:
    _ensure_dirs()
    if not _validate_candidate_signal(event):
        logger.warning("Rejecting malformed candidate signal: %s", event.get("timestamp", "unknown"))
        return
    with CANDIDATE_SIGNALS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def _validate_candidate_signal(record: dict[str, Any]) -> bool:
    """Return True if a candidate signal record has required fields."""
    if not isinstance(record.get("timestamp"), str):
        return False
    if not isinstance(record.get("signals"), list):
        return False
    return True


def _is_explicit_memory_request(text: str) -> bool:
    lower = text.lower()
    return any(
        phrase in lower
        for phrase in [
            "remember this",
            "remember that",
            "save this",
            "store this",
            "make this a preference",
            "this is my preference",
            "always",
            "never",
        ]
    )


def list_papers() -> dict[str, Any]:
    """List supported papers available for ingestion, scanning subdirectories recursively."""
    _ensure_dirs()
    files = sorted(
        str(path.relative_to(PAPERS_DIR))
        for path in PAPERS_DIR.rglob("*")
        if path.suffix.lower() in {".txt", ".md", ".pdf"} and path.is_file()
    )
    subdirs = sorted(
        str(d.relative_to(PAPERS_DIR)).replace("\\", "/")
        for d in PAPERS_DIR.iterdir()
        if d.is_dir()
    )
    return {"papers_dir": str(PAPERS_DIR), "subdirectories": subdirs, "papers": files}


def rename_paper(old_name: str, new_name: str) -> dict[str, Any]:
    """Rename a paper file and update all dependent records atomically.

    Migrates:
    1. The file in ``papers/``
    2. The corresponding ``knowledge_base/*.json`` record (renames file + patches ``source``)
    3. Concept-graph edges referencing the old filename

    Rolls back on failure at any step.
    """
    _ensure_dirs()
    old_path = (PAPERS_DIR / old_name).resolve()

    # Security: prevent path traversal outside papers/
    if PAPERS_DIR.resolve() not in old_path.parents or not old_path.is_file():
        return {"status": "error", "message": f"Source file not found in papers/: {old_name}"}

    new_path = (PAPERS_DIR / new_name).resolve()
    if PAPERS_DIR.resolve() not in new_path.parents:
        return {"status": "error", "message": f"Target path must stay within papers/: {new_name}"}

    if not new_path.parent.exists():
        new_path.parent.mkdir(parents=True, exist_ok=True)

    if new_path.exists():
        return {"status": "error", "message": f"Target file already exists: {new_name}"}

    # --- Step 1: Rename the file ---
    try:
        old_path.rename(new_path)
    except OSError as exc:
        return {"status": "error", "message": f"File rename failed: {exc}"}

    # --- Step 2: Rename and patch the KB record ---
    old_kb_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(old_name).stem)
    new_kb_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(new_name).stem)
    old_kb_path = KNOWLEDGE_DIR / f"{old_kb_name}.json"
    new_kb_path = KNOWLEDGE_DIR / f"{new_kb_name}.json"

    kb_renamed = False
    if old_kb_path.exists():
        try:
            record = json.loads(old_kb_path.read_text(encoding="utf-8"))
            record["source"] = new_name
            if "metadata" in record:
                record["metadata"]["source"] = new_name
            new_kb_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            old_kb_path.unlink()
            kb_renamed = True
        except Exception as exc:
            # Roll back file rename
            try:
                new_path.rename(old_path)
            except OSError:
                pass
            return {
                "status": "error",
                "message": f"KB record migration failed (file rename rolled back): {exc}",
            }

    # --- Step 3: Migrate concept-graph edges ---
    graph_result = {"edge_updates": 0, "dependency_updates": 0}
    try:
        graph_result = concept_graph.rename_source_paper(old_name, new_name)
    except Exception as exc:
        # Roll back KB rename + file rename
        if kb_renamed:
            try:
                new_kb_path.rename(old_kb_path)
            except OSError:
                pass
        try:
            new_path.rename(old_path)
        except OSError:
            pass
        return {
            "status": "error",
            "message": f"Concept-graph migration failed (file and KB rolled back): {exc}",
        }

    # Invalidate caches
    _load_records._cache = None  # type: ignore[attr-defined]

    return {
        "status": "ok",
        "old_name": old_name,
        "new_name": new_name,
        "kb_record_migrated": kb_renamed,
        "concept_graph_edges_updated": graph_result["edge_updates"],
        "concept_graph_dependencies_updated": graph_result["dependency_updates"],
    }


def delete_paper(file_name: str, dry_run: bool = True) -> dict[str, Any]:
    """Delete a paper file and its knowledge-base record.

    Args:
        file_name: Path relative to ``papers/``.
        dry_run: When True (default), preview what would be deleted without
                 making changes.  Set to False to actually delete.

    Returns a preview when dry_run=True; performs the deletion otherwise.
    """
    _ensure_dirs()
    path = (PAPERS_DIR / file_name).resolve()

    if PAPERS_DIR.resolve() not in path.parents:
        return {"status": "error", "message": f"Path outside papers/: {file_name}"}

    if not path.is_file():
        return {"status": "error", "message": f"File not found: {file_name}"}

    kb_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(file_name).stem)
    kb_path = KNOWLEDGE_DIR / f"{kb_name}.json"
    kb_exists = kb_path.exists()

    file_size = path.stat().st_size
    file_size_str = f"{file_size} bytes" if file_size else "0 bytes (empty)"

    preview = {
        "dry_run": dry_run,
        "file": file_name,
        "file_size": file_size_str,
        "kb_record_exists": kb_exists,
        "kb_record_path": str(kb_path) if kb_exists else None,
    }

    if dry_run:
        return {
            "status": "preview",
            "message": (
                f"Would delete: {file_name} ({file_size_str})"
                + (f" + knowledge_base/{kb_path.name}" if kb_exists else "")
                + ". Set dry_run=False to execute."
            ),
            "preview": preview,
        }

    # --- Perform deletion ---
    errors = []

    try:
        path.unlink()
    except OSError as exc:
        errors.append(f"file delete: {exc}")

    if kb_exists:
        try:
            kb_path.unlink()
        except OSError as exc:
            errors.append(f"KB record delete: {exc}")

    # Clean up concept-graph references
    graph_result = {"edge_removals": 0, "dependency_removals": 0}
    try:
        graph_result = concept_graph.remove_source_paper(file_name)
    except Exception as exc:
        errors.append(f"concept graph cleanup: {exc}")

    # Invalidate caches
    _load_records._cache = None  # type: ignore[attr-defined]

    if errors:
        return {
            "status": "partial",
            "message": f"Deleted with {len(errors)} issue(s): {'; '.join(errors)}",
            "file_deleted": not path.exists(),
            "kb_record_deleted": not kb_path.exists(),
            "graph_edge_removals": graph_result["edge_removals"],
            "errors": errors,
        }

    return {
        "status": "ok",
        "message": f"Deleted {file_name} and its knowledge-base record.",
        "file_deleted": True,
        "kb_record_deleted": kb_exists,
        "graph_edge_removals": graph_result["edge_removals"],
        "graph_dependency_removals": graph_result["dependency_removals"],
    }


def organize_papers(mapping: dict[str, str]) -> dict[str, Any]:
    """Rename and/or move multiple papers according to a mapping.

    Args:
        mapping: Dict of ``{current_filename: new_filename}``.  New filenames
                 may include subdirectory paths (e.g. ``abm/Angere_2010.pdf``).
                 Subdirectories are created automatically.

    Each rename is performed via ``rename_paper``, so KB records and concept-graph
    edges are migrated atomically per file.  If any rename fails, previously
    completed renames are NOT rolled back (each is independently atomic).
    """
    if not mapping:
        return {"status": "error", "message": "mapping must be a non-empty dict of {old: new}"}

    results = []
    succeeded = 0
    failed = 0

    for old_name, new_name in mapping.items():
        try:
            result = rename_paper(old_name, new_name)
            results.append(result)
            if result.get("status") == "ok":
                succeeded += 1
            else:
                failed += 1
        except Exception as exc:
            results.append({"status": "error", "old_name": old_name, "new_name": new_name, "message": str(exc)})
            failed += 1

    return {
        "status": "ok" if failed == 0 else "partial",
        "total": len(mapping),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


def _infer_dependencies(concepts: list[dict[str, Any]], source_paper: str) -> int:
    """Ask the LLM to infer prerequisite hints among the extracted concepts.

    Returns the number of prerequisite edges created.  Best-effort — failures
    are silent and never block ingest.
    """
    concept_names = [c.get("name", "") for c in concepts if c.get("name")]
    if len(concept_names) < 2:
        return 0  # need at least two concepts to infer a relationship

    try:
        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        prompt = (
            "You are helping build a curriculum for a research-paper tutor.\n\n"
            "Here are concepts extracted from a paper:\n"
            + "\n".join(f"- {name}" for name in concept_names)
            + "\n\n"
            "For each concept that pedagogically depends on another (the prerequisite should "
            "be taught first for better understanding), output one line in this exact format:\n"
            "  concept_name ← prerequisite_name\n\n"
            "Only output lines for genuine pedagogical dependencies, not every possible pair. "
            "A dependency means understanding the prerequisite significantly helps grasp the "
            "dependent concept. If there are no clear dependencies, output nothing.\n\n"
            "Output format (one per line, nothing else):\n"
            "vector search ← embeddings\n"
            "transformer ← attention\n"
        )
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.0,
        )
        text = response.choices[0].message.content or ""
    except Exception:
        return 0  # silent failure — dependencies are best-effort

    created = 0
    for line in text.strip().splitlines():
        line = line.strip()
        if "←" not in line and "<-" not in line:
            continue
        # Normalise both arrow styles.
        parts = line.replace("<-", "←").split("←")
        if len(parts) != 2:
            continue
        concept = parts[0].strip().lower()
        prerequisite = parts[1].strip().lower()
        if not concept or not prerequisite or concept == prerequisite:
            continue
        # Verify both names appear in the original concept list.
        known = {c.get("name", "").strip().lower() for c in concepts}
        if concept not in known or prerequisite not in known:
            continue
        try:
            concept_graph.link_prerequisite(concept, prerequisite, source_paper)
            created += 1
        except Exception:
            continue

    return created


def ingest_paper(file_name: str, evidence_scope: str = "") -> dict[str, Any]:
    """Read one paper from papers/ and save metadata, concepts, notes, and cited passages."""
    _ensure_dirs()
    path = (PAPERS_DIR / file_name).resolve()
    if not path.is_file() or PAPERS_DIR.resolve() not in path.parents:
        return {"status": "error", "message": f"Paper not found in papers/: {file_name}"}

    pages = _read_paper_pages(path)
    text = "\n\n".join(page["text"] for page in pages)
    if not text.strip():
        return {"status": "error", "message": f"No extractable text found in {file_name}"}

    passages = _make_passages(path.name, pages)
    notes = _extract_candidate_notes(text, passages)
    scopes = _normalize_evidence_scopes(evidence_scope) or _infer_evidence_scopes(file_name)
    record = {
        "schema_version": 2,
        "metadata": _extract_metadata(path.name, pages),
        "source": path.name,
        "characters": len(text),
        "page_count": len(pages),
        "keywords": _keywords(text),
        "notes": notes,
        "passages": passages,
    }
    if scopes:
        record["evidence_scope"] = scopes
    output_path = _paper_record_path(path)
    output_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    # Invalidate cached records so next reader picks up the new paper.
    _load_records._cache = None  # type: ignore[attr-defined]

    # --- concept graph: link extracted concepts to user interests ---
    try:
        profile = _load_user_profile()
        for interest in profile.get("interests", []):
            interest_name = interest.get("name", "")
            if not interest_name:
                continue
            for concept in notes["concepts"]:
                concept_name = concept.get("name", "")
                if not concept_name:
                    continue
                sim = concept_graph._similarity(interest_name, concept_name)
                if sim > 0:
                    concept_graph.link(
                        interest_name, concept_name, path.name,
                        edge_type="ingest", similarity_score=sim,
                    )
    except Exception:
        pass  # graph linking is best-effort; never block ingest

    # --- concept graph: infer prerequisite hints among extracted concepts ---
    prereq_count = 0
    try:
        prereq_count = _infer_dependencies(notes["concepts"], path.name)
    except Exception:
        pass  # dependency inference is best-effort

    return {
        "status": "ok",
        "source": path.name,
        "title": record["metadata"]["title"],
        "saved_to": str(output_path),
        "concept_count": len(notes["concepts"]),
        "passage_count": len(passages),
        "page_count": len(pages),
        "prerequisite_edges_created": prereq_count,
    }


def ingest_all_papers() -> dict[str, Any]:
    """Ingest every supported paper in papers/; one bad file does not kill the batch."""
    papers = list_papers()["papers"]
    results = []
    for name in papers:
        try:
            results.append(ingest_paper(name))
        except Exception as exc:
            results.append({"status": "error", "source": name, "message": str(exc)})
    return {"ingested": results, "count": len(results)}


def list_concepts() -> dict[str, Any]:
    """List extracted concepts grouped by source paper, including citations when available."""
    records = _load_records()
    return {
        "sources": [
            {
                "source": record["source"],
                "title": record.get("metadata", {}).get("title", record["source"]),
                "concepts": record.get("notes", {}).get("concepts", []),
                "keywords": record.get("keywords", []),
            }
            for record in records
        ]
    }


def search_evidence(query: str, max_passages: int = 8, evidence_scope: str = "") -> dict[str, Any]:
    """Search ingested evidence passages with weighted lexical ranking and citations."""
    query_terms = _tokenize(query)
    if not query_terms:
        return {"query": query, "evidence_scope": evidence_scope or None, "matches": []}

    records = _filter_records_by_scope(_load_records(), evidence_scope)
    passages = _all_passages(records)
    doc_freq: Counter = Counter()
    for passage in passages:
        for term in set(_tokenize(passage["text"])):
            doc_freq[term] += 1

    matches = []
    for passage in passages:
        score = _score_passage(query_terms, passage, len(passages), doc_freq)
        if score > 0:
            matches.append(
                {
                    "source": passage["source"],
                    "citation": passage["citation"],
                    "score": score,
                    "keywords": passage.get("keywords", []),
                    "passage": passage["text"],
                }
            )

    matches.sort(key=lambda item: item["score"], reverse=True)
    return {
        "query": query,
        "evidence_scope": evidence_scope or None,
        "matches": matches[:max(1, min(max_passages, 20))],
    }


def paper_brief(source: str = "") -> dict[str, Any]:
    """Return a compact source-grounded brief for one paper or all papers."""
    records = _load_records()
    if source:
        records = [
            record
            for record in records
            if source.lower() in record["source"].lower()
            or source.lower() in record.get("metadata", {}).get("title", "").lower()
        ]

    return {
        "briefs": [
            _try_annotate_brief(
                {
                    "source": record["source"],
                    "metadata": record.get("metadata", {}),
                    "top_concepts": record.get("notes", {}).get("concepts", [])[:12],
                    "methods": record.get("notes", {}).get("methods", [])[:4],
                    "findings": record.get("notes", {}).get("findings", [])[:4],
                    "limitations": record.get("notes", {}).get("limitations", [])[:4],
                    "open_questions": record.get("notes", {}).get("open_questions", [])[:4],
                }
            )
            for record in records
        ]
    }


def compare_papers(topic: str = "") -> dict[str, Any]:
    """Compare ingested papers by concepts, methods, findings, limitations, and optional topic evidence."""
    records = _load_records()
    concept_sources: dict[str, set[str]] = defaultdict(set)
    for record in records:
        for concept in record.get("notes", {}).get("concepts", []):
            concept_sources[concept["name"]].add(record["source"])

    shared_concepts = [
        {"concept": concept, "sources": sorted(sources)}
        for concept, sources in concept_sources.items()
        if len(sources) > 1
    ][:20]

    comparison = []
    for record in records:
        notes = record.get("notes", {})
        entry = {
            "source": record["source"],
            "title": record.get("metadata", {}).get("title", record["source"]),
            "concepts": notes.get("concepts", [])[:10],
            "methods": notes.get("methods", [])[:3],
            "findings": notes.get("findings", [])[:3],
            "limitations": notes.get("limitations", [])[:3],
        }
        if topic:
            topic_matches = search_evidence(f"{topic} {record['source']}", 5)["matches"]
            entry["topic_evidence"] = [
                match for match in topic_matches if match["source"] == record["source"]
            ][:3]
        comparison.append(entry)

    return {
        "topic": topic or None,
        "shared_concepts": shared_concepts,
        "papers": comparison,
    }


def make_study_guide(source: str = "", question_count: int = 8) -> dict[str, Any]:
    """Create a citation-backed study guide with concepts and recall questions."""
    briefs = paper_brief(source)["briefs"]
    questions = []
    for brief in briefs:
        title = brief["metadata"].get("title", brief["source"])
        for concept in brief["top_concepts"][: max(1, question_count // max(1, len(briefs)))]:
            questions.append(
                {
                    "question": f"Explain how '{concept['name']}' matters in {title}.",
                    "citation": concept.get("citation"),
                    "source": brief["source"],
                }
            )
        for limitation in brief["limitations"][:2]:
            questions.append(
                {
                    "question": f"What limitation or caveat does {title} raise?",
                    "citation": limitation.get("citation"),
                    "source": brief["source"],
                }
            )

    deduped_questions = []
    seen_questions = set()
    for question in questions:
        key = question["question"].lower()
        if key in seen_questions:
            continue
        seen_questions.add(key)
        deduped_questions.append(question)
        if len(deduped_questions) >= max(1, min(question_count, 20)):
            break

    return {
        "study_guides": briefs,
        "recall_questions": deduped_questions,
    }


def get_user_profile() -> dict[str, Any]:
    """Inspect the local user model used for personalization."""
    profile = _load_user_profile()
    return {
        "profile_path": str(USER_PROFILE_PATH),
        "profile": profile,
    }


def learn_from_user_message(message: str, context: str = "") -> dict[str, Any]:
    """Analyze one user message and update interests, question patterns, style, and quirks."""
    profile = _load_user_profile()
    signals = _infer_message_signals(message)
    added: dict[str, int] = {}
    for bucket, items in signals.items():
        added[bucket] = 0
        # ADR 0066: Polish corrections update a dict, not a list.
        if bucket == "polish_corrections":
            if items:
                polish_prefs = profile.setdefault("polish_preferences", {})
                for correction in items:
                    ctx = correction.get("context", "default")
                    level = correction.get("level", "moderate")
                    polish_prefs[ctx] = level
                added[bucket] = len(items)
            continue
        key = {
            "interests": "name",
            "question_patterns": "pattern",
            "style_preferences": "preference",
            "grammar_and_quirks": "observation",
        }[bucket]
        for item in items:
            if context:
                item["context"] = context[:240]
            if _append_unique_signal(profile, bucket, key, item):
                added[bucket] += 1

    profile["last_learned_from"] = message[:500]
    _save_user_profile(profile)
    return {
        "status": "ok",
        "profile_path": str(USER_PROFILE_PATH),
        "added": added,
        "signals": signals,
    }


def record_interaction(
    user_message: str,
    agent_response: str = "",
    outcome: str = "",
    tags: str = "",
) -> dict[str, Any]:
    """Append an interaction event to the local personalization log."""
    _ensure_dirs()
    event = {
        "timestamp": _now_iso(),
        "user_message": user_message,
        "agent_response": agent_response,
        "outcome": outcome,
        "tags": [tag.strip() for tag in tags.split(",") if tag.strip()],
    }
    with INTERACTION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    return {"status": "ok", "log_path": str(INTERACTION_LOG_PATH), "event": event}


# ── ADR 0067: Session metadata for cognitive adaptation ──────────────


def _write_session_meta(
    message_count: int,
    inferred_goal: str = "",
    topic_stability: float = 1.0,
    completion_status: str = "ended_naturally",
    question_depth: str = "stable",
    started_at: str = "",
    ended_at: str = "",
) -> dict[str, Any]:
    """Write a lightweight session summary to session_meta.jsonl."""
    _ensure_dirs()
    errors: list[str] = []

    try:
        message_count_int = int(message_count)
    except (TypeError, ValueError):
        message_count_int = 0
        errors.append("message_count must be an integer")
    if message_count_int < 0:
        errors.append("message_count must be non-negative")

    try:
        topic_stability_float = float(topic_stability)
    except (TypeError, ValueError):
        topic_stability_float = -1.0
        errors.append("topic_stability must be a number")
    if not 0.0 <= topic_stability_float <= 1.0:
        errors.append("topic_stability must be between 0.0 and 1.0")

    allowed_statuses = {"ended_naturally", "abandoned", "timeout"}
    if completion_status not in allowed_statuses:
        errors.append(
            "completion_status must be one of: "
            + ", ".join(sorted(allowed_statuses))
        )

    allowed_depth = {"deepening", "shallowing", "stable"}
    if question_depth not in allowed_depth:
        errors.append(
            "question_depth must be one of: "
            + ", ".join(sorted(allowed_depth))
        )

    ended_at_value = ended_at or _now_iso()
    if not started_at:
        errors.append("started_at must be provided by runtime session state")
    started_dt = _parse_iso_datetime(started_at, "started_at", errors) if started_at else None
    ended_dt = _parse_iso_datetime(ended_at_value, "ended_at", errors)
    if started_dt is not None and ended_dt is not None and started_dt > ended_dt:
        errors.append("started_at must be before or equal to ended_at")

    if errors:
        return {"status": "error", "message": "; ".join(errors)}

    meta = {
        "session_id": f"sess_{started_at[:10].replace('-', '')}_{message_count_int:03d}",
        "started_at": started_at,
        "ended_at": ended_at_value,
        "message_count": message_count_int,
        "inferred_goal": inferred_goal or "general exploration",
        "topic_stability": round(topic_stability_float, 2),
        "completion_status": completion_status,
        "question_depth_trajectory": question_depth,
    }
    with SESSION_META_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(meta) + "\n")
    return {"status": "ok", "session_id": meta["session_id"]}


def set_user_preference(category: str, value: str, evidence: str = "", confidence: float = 0.9) -> dict[str, Any]:
    """Add an explicit user preference or correction to the local user model."""
    allowed = {
        "interest": ("interests", "name"),
        "question_pattern": ("question_patterns", "pattern"),
        "style": ("style_preferences", "preference"),
        "quirk": ("grammar_and_quirks", "observation"),
        "adaptation_rule": ("adaptation_rules", "rule"),
        "avoidance": ("avoidances", "rule"),
    }
    normalized = category.strip().lower()
    if normalized not in allowed:
        return {
            "status": "error",
            "message": f"Unknown category '{category}'. Use one of: {', '.join(sorted(allowed))}.",
        }

    bucket, key = allowed[normalized]
    profile = _load_user_profile()
    item = {
        key: value,
        "evidence": evidence or "Explicitly provided by the user.",
        "confidence": max(0.0, min(float(confidence), 1.0)),
    }
    changed = _append_unique_signal(profile, bucket, key, item)
    _save_user_profile(profile)
    return {
        "status": "ok",
        "changed": changed,
        "profile_path": str(USER_PROFILE_PATH),
        "category": normalized,
        "item": item,
    }


def save_personal_note(
    text: str,
    title: str = "",
    user_tags: str = "",
    concepts: str = "",
) -> dict[str, Any]:
    """Save an explicit personal note locally.

    Use for prompts such as ``note:``, ``save note:``, ``remember note:``,
    or when the user directly asks to store a personal/knowledge-management
    note. Do not use this for ordinary unmarked chat.
    """
    result = personal_notes.save_note(
        text=text,
        title=title,
        user_tags=user_tags,
        concepts=concepts,
        path=PERSONAL_NOTES_PATH,
    )
    if result.get("status") == "ok":
        return _projection_status(result, "personal_note", result.get("note_id", ""))
    return result


def list_personal_notes() -> dict[str, Any]:
    """List non-deleted personal notes with summary metadata."""
    return personal_notes.list_notes(path=PERSONAL_NOTES_PATH)


def get_personal_note(note_id: str) -> dict[str, Any]:
    """Return one full personal note by id."""
    return personal_notes.get_note(note_id=note_id, path=PERSONAL_NOTES_PATH)


def search_personal_notes(query: str, max_notes: int = 10) -> dict[str, Any]:
    """Search personal notes by text, title, tags, concepts, and note cards."""
    return personal_notes.search_notes(
        query=query,
        max_notes=max_notes,
        path=PERSONAL_NOTES_PATH,
    )


def delete_personal_note(note_id: str) -> dict[str, Any]:
    """Soft-delete a personal note. It remains on disk but is hidden from list/search."""
    return personal_notes.soft_delete_note(note_id=note_id, path=PERSONAL_NOTES_PATH)


# ── ADR 0028 + 0035: Note editing, versioning, corrections ─────────────


def edit_personal_note(
    note_id: str,
    text: str = "",
    title: str = "",
    user_tags: str | list[str] | None = None,
    concepts: str | list[str] | None = None,
) -> dict[str, Any]:
    """Edit a personal note. Previous state is preserved as a version entry."""
    result = personal_notes.edit_personal_note(
        note_id=note_id, text=text, title=title,
        user_tags=user_tags, concepts=concepts,
        path=PERSONAL_NOTES_PATH,
    )
    # ADR 0040: refresh graph signals so note edges don't decay.
    if result.get("status") == "ok":
        try:
            concept_graph.refresh_note_signal(note_id)
        except Exception:
            pass
        return _projection_status(result, "personal_note", note_id)
    return result


def reject_note_card(note_id: str, card_index: int) -> dict[str, Any]:
    """Reject an extracted Note Card by its 0-based index."""
    return personal_notes.reject_note_card(
        note_id=note_id, card_index=card_index, path=PERSONAL_NOTES_PATH,
    )


def reject_note_concept(note_id: str, concept_name: str) -> dict[str, Any]:
    """Reject a linked Concept from a personal note."""
    return personal_notes.reject_note_concept(
        note_id=note_id, concept_name=concept_name, path=PERSONAL_NOTES_PATH,
    )


# ── ADR 0027 + 0031 + 0032: Backlinks, markdown, import ───────────────


def get_note_backlinks(note_id: str) -> dict[str, Any]:
    """Return notes that share concepts with this note (concept-derived backlinks)."""
    return personal_notes.get_backlinks(note_id=note_id, path=PERSONAL_NOTES_PATH)


def render_note_markdown(note_id: str) -> dict[str, Any]:
    """Return the full Markdown mirror for a personal note."""
    return personal_notes.render_note_markdown(note_id=note_id, path=PERSONAL_NOTES_PATH)


def import_markdown_notes() -> dict[str, Any]:
    """Sync Markdown mirror edits back into the canonical JSONL store."""
    return personal_notes.import_markdown_notes(path=PERSONAL_NOTES_PATH)


# ── ADR 0056–0058: Relationship Management first slice ────────────────


def add_person(
    display_name: str,
    relationship_type: str = "unknown",
    aliases: str = "",
    context_note: str = "",
    tags: str = "",
    concepts: str = "",
    cadence_days: int | None = None,
) -> dict[str, Any]:
    """Create a Person record through explicit relationship capture."""
    return relationship_management.add_person(
        display_name=display_name,
        relationship_type=relationship_type,
        aliases=aliases,
        context_note=context_note,
        tags=tags,
        concepts=concepts,
        cadence_days=cadence_days,
        path=PEOPLE_PATH,
    )


def list_people() -> dict[str, Any]:
    """List non-deleted people with summary metadata."""
    return relationship_management.list_people(path=PEOPLE_PATH)


def get_person(person_id_or_name: str) -> dict[str, Any]:
    """Return one Person record by id, display name, or alias."""
    return relationship_management.get_person(person_id_or_name, path=PEOPLE_PATH)


def search_people(query: str, max_people: int = 10) -> dict[str, Any]:
    """Search people by name, aliases, relationship context, interactions, tags, and concepts."""
    return relationship_management.search_people(
        query=query,
        max_people=max_people,
        path=PEOPLE_PATH,
    )


def add_relationship_note(
    person_id_or_name: str,
    text: str,
    concepts: str = "",
    tags: str = "",
    linked_note_ids: str = "",
    open_loop: str = "",
    sensitive: bool | None = None,
) -> dict[str, Any]:
    """Save explicit Relationship Context for a Person."""
    return relationship_management.add_relationship_note(
        person_id_or_name=person_id_or_name,
        text=text,
        concepts=concepts,
        tags=tags,
        linked_note_ids=linked_note_ids,
        open_loop=open_loop,
        sensitive=sensitive,
        path=PEOPLE_PATH,
    )


def log_relationship_interaction(
    person_id_or_name: str,
    summary: str,
    happened_at: str = "",
    channel: str = "",
    concepts: str = "",
    open_loop: str = "",
) -> dict[str, Any]:
    """Log an interaction with a Person."""
    return relationship_management.log_relationship_interaction(
        person_id_or_name=person_id_or_name,
        summary=summary,
        happened_at=happened_at,
        channel=channel,
        concepts=concepts,
        open_loop=open_loop,
        path=PEOPLE_PATH,
    )


def recommend_reconnections(max_people: int = 5) -> dict[str, Any]:
    """Recommend who to reconnect with and why."""
    return relationship_management.recommend_reconnections(
        max_people=max_people,
        path=PEOPLE_PATH,
    )


def forget_person(person_id_or_name: str) -> dict[str, Any]:
    """Soft-delete a Person record from normal relationship retrieval."""
    return relationship_management.forget_person(person_id_or_name, path=PEOPLE_PATH)


# ── ADR 0013: Session goal inference ────────────────────────────────────


def _infer_session_goal(message: str) -> dict[str, Any]:
    """Infer the user's session goal from their first message.

    Returns a structured goal with a label and confidence.  The agent
    instruction says to infer by default and ask one clarifying question
    only when ambiguity would materially change the output.
    """
    lower = message.lower()
    patterns = [
        ("paper ingestion", ["ingest", "read the paper", "add paper", "load paper"]),
        ("evidence search", ["search for", "find evidence", "what does the paper say", "look up"]),
        ("paper comparison", ["compare", "difference between", "versus", "vs"]),
        ("study / learning", ["study guide", "quiz", "teach me", "explain", "recall"]),
        ("personalization", ["remember", "prefer", "my style", "about me", "profile"]),
        ("note management", ["note:", "save note", "my notes", "search notes", "edit note"]),
        ("knowledge audit", ["audit", "what do you know", "self audit", "inspect"]),
        ("grill / questioning", ["grill", "question me", "ask me"]),
    ]
    for label, triggers in patterns:
        if any(t in lower for t in triggers):
            return {"session_goal": label, "confidence": 0.8, "source": "keyword_match"}

    return {"session_goal": "general exploration", "confidence": 0.4, "source": "no_strong_signal"}


# ── ADR 0045 + 0046: Knowledge loop coordination ───────────────────────


def _knowledge_loop_update(source: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Route a signal from any input channel to the appropriate state store.

    Called automatically by interaction handlers (grill, tutor, notes,
    profile updates).  This is the coordination point for the Self-Learning
    Knowledge Loop — it ensures signals flow to the right place without
    duplicating routing logic across handlers.
    """
    now = _now_iso()
    routed: list[str] = []

    # ── explicit preferences → profile.json (durable, user-gated) ──
    if source == "explicit_preference":
        set_user_preference(
            category=payload.get("category", "style"),
            value=payload.get("value", ""),
            source=payload.get("source", "")[:400],
            confidence=payload.get("confidence", 0.8),
        )
        routed.append("profile.json")

    # ── inferred patterns → candidate_signals.jsonl (automatic, weak) ──
    if source in ("grill_answer", "interaction", "note_signal", "tutor_answer"):
        signals = _infer_message_signals(payload.get("text", ""))
        if signals:
            _record_candidate_signals({
                "timestamp": now,
                "source": source,
                "signals": signals,
                "context": payload.get("context", "")[:300],
            })
            routed.append("candidate_signals.jsonl")

    # ── concept engagement → concept_graph (automatic weight updates) ──
    if source in ("grill_answer", "tutor_answer", "note_save"):
        for concept_name in payload.get("concepts", []):
            for interest in _load_user_profile().get("interests", []):
                interest_name = interest.get("name", "")
                if interest_name:
                    try:
                        concept_graph.link(
                            interest_name, concept_name, source,
                            edge_type="engaged" if source != "note_save" else "note",
                        )
                    except Exception:
                        pass
        routed.append("concept_graph")

    # ── note interaction → refresh note signal (ADR 0040) ──
    if source == "note_edit" and payload.get("note_id"):
        try:
            concept_graph.refresh_note_signal(payload["note_id"])
            routed.append("note_signal_refresh")
        except Exception:
            pass

    return {
        "status": "ok",
        "source": source,
        "routed_to": routed,
        "timestamp": now,
    }


# ── ADR 0061-0064: Projection plumbing ───────────────────────────────


def _emit_projection_update(
    source_type: str,
    source_id: str,
    context: str = "",
) -> dict[str, Any]:
    """Best-effort typed projection update after a canonical write.

    Adds typed source references to concept graph edges when the write
    involves concepts.  Failure here does not fail the canonical write
    (ADR 0063: best-effort, synchronous, not blocking).
    """
    try:
        profile = _load_user_profile()
        concepts: list[str] = []
        if source_type == "personal_note":
            note_result = personal_notes.get_note(source_id, path=PERSONAL_NOTES_PATH)
            if note_result.get("status") == "ok":
                concepts = note_result["note"].get("concepts", [])
        elif source_type == "tutor_progress":
            progress = _load_tutor_progress()
            entry = progress.get("concepts", {}).get(source_id.strip().lower(), {})
            concepts = [entry.get("concept", source_id)] if entry else [source_id]
        elif source_type == "grill_answer":
            concepts = [context[:80]] if context else []

        updated = 0
        for concept_name in concepts:
            for interest in profile.get("interests", []):
                interest_name = interest.get("name", "")
                if not interest_name:
                    continue
                try:
                    concept_graph.link(
                        interest_name, concept_name, source_id,
                        edge_type="note" if source_type == "personal_note" else "engaged",
                    )
                    updated += 1
                except Exception:
                    pass
        return {"status": "ok", "updated_edges": updated}
    except Exception as exc:
        return {"status": "skipped", "reason": str(exc)[:200], "updated_edges": 0}


def _projection_status(result: dict[str, Any], source_type: str, source_id: str, context: str = "") -> dict[str, Any]:
    """Attach projection_status to a tool result dict."""
    proj = _emit_projection_update(source_type, source_id, context)
    result["projection_status"] = proj
    return result


# ── ADR 0071: Web search tool (Semantic Scholar + DuckDuckGo) ─────────


def _classify_source_quality(url: str) -> str:
    """Classify a URL into a source quality tag."""
    domain = url.lower()
    if any(d in domain for d in ["arxiv.org", "semanticscholar.org", "scholar.google", "acm.org", "ieee.org", "springer.com", "nature.com", "science.org", "pubmed", "doi.org"]):
        return "peer-reviewed"
    if any(d in domain for d in ["python.org", "docs.python", "mdn.", "devdocs.io", "readthedocs.io", "docs.rs", "pkg.go.dev"]):
        return "official-docs"
    if any(d in domain for d in ["github.com", "gitlab.com"]):
        return "vendor"
    if any(d in domain for d in ["stackoverflow.com", "stackexchange.com", "reddit.com", "discourse", "news.ycombinator.com"]):
        return "forum"
    if any(d in domain for d in [".blog", "medium.com", "dev.to", "substack.com"]):
        return "technical-blog"
    return "unknown"


def _search_semantic_scholar(query: str, limit: int = 5) -> dict[str, Any]:
    """Search Semantic Scholar API for academic papers. Free, no key required.

    Enforces inter-request throttling (~1 req/s) and uses Retry-After headers
    when rate-limited.  Without an API key the public endpoint allows roughly
    1 request per second; this module-level throttle prevents the LLM from
    firing rapid-fire calls that would all 429.
    """
    import time
    import urllib.request
    import urllib.parse
    import urllib.error

    global _SCHOLAR_LAST_REQUEST

    # ── inter-request throttle ──────────────────────────────────────────
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
        _SCHOLAR_LAST_REQUEST = time.monotonic()  # stamp before send
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ResearchPaperAgent/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 3:
                # Prefer the Retry-After header; fall back to exponential.
                retry_after = exc.headers.get("Retry-After") if hasattr(exc, "headers") else None
                if retry_after is not None:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        wait = 2 ** (attempt + 1)
                else:
                    wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                # Add jitter so concurrent callers don't sync up.
                wait += time.monotonic() % 1.0
                logger.warning(
                    "Semantic Scholar 429 (attempt %d/4), waiting %.1fs",
                    attempt + 1, wait,
                )
                time.sleep(wait)
                continue
            return {
                "status": "error", "backend": "semantic_scholar",
                "message": f"HTTP {exc.code} — Semantic Scholar returned an error",
            }
        except Exception as exc:
            return {
                "status": "error", "backend": "semantic_scholar",
                "message": str(exc)[:300],
            }

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
        "status": "ok",
        "backend": "semantic_scholar",
        "query": query,
        "total_results": data.get("total", len(results)),
        "results": results,
    }


def _search_duckduckgo(query: str, limit: int = 5) -> dict[str, Any]:
    """Search DuckDuckGo using the ddgs package (HTML scraping).

    The api.duckduckgo.com instant-answer API returns empty results or
    dictionary definitions for many queries.  The ``ddgs`` package scrapes
    the actual DuckDuckGo HTML search results page.

    Falls back to the instant-answer API if ddgs is not installed or fails.
    """
    try:
        from ddgs import DDGS  # duckduckgo_search was renamed to ddgs
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # legacy package name
        except ImportError:
            return _search_duckduckgo_fallback(query, limit)

    results = []
    try:
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=limit):
                href = result.get("href", "")
                # Filter out dictionary definitions, disambiguation pages.
                if any(skip in href.lower() for skip in ["/definition/", "duckduckgo.com/?q="]):
                    continue
                results.append({
                    "title": (result.get("title") or "")[:200],
                    "abstract": (result.get("body") or "")[:600],
                    "url": href,
                    "source_quality": _classify_source_quality(href),
                    "provenance": f"[from web: {href[:80]}] — {(result.get('title') or '')[:120]}",
                })
    except Exception:
        return _search_duckduckgo_fallback(query, limit)

    if not results:
        return _search_duckduckgo_fallback(query, limit)

    return {
        "status": "ok",
        "backend": "duckduckgo",
        "query": query,
        "total_results": len(results),
        "results": results[:limit],
    }


def _search_duckduckgo_fallback(query: str, limit: int = 5) -> dict[str, Any]:
    """Fallback: DuckDuckGo instant answers API (limited, often returns empty)."""
    import urllib.request
    import urllib.parse

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
            "source_quality": _classify_source_quality(data.get("AbstractURL", "")),
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
                "source_quality": _classify_source_quality(url),
                "provenance": f"[from web: {url.split('/')[2] if '//' in url else 'duckduckgo.com'}] — {text[:120]}",
            })
    return {
        "status": "ok",
        "backend": "duckduckgo_fallback",
        "query": query,
        "total_results": len(results),
        "results": results[:limit],
    }


def search_web(query: str, source: str = "auto") -> dict[str, Any]:
    """Search the web for information, with dual backends for scholarly and general queries.

    Args:
        query: The search query (will be used as-is; the LLM should rewrite before calling).
        source: "scholar" for academic papers (Semantic Scholar), "web" for general
                (DuckDuckGo), or "auto" to let the tool decide based on query signals.

    Returns structured results with provenance tags, source_quality classification,
    and URLs for citation. Web-sourced claims should be capped at Medium confidence.
    """
    query = query.strip()
    if not query:
        return {"status": "error", "message": "search query is required"}

    if source == "auto":
        # Heuristic: academic signals → scholar, otherwise → web.
        academic_signals = [
            "paper", "research", "study", "method", "finding", "abstract",
            "doi", "arxiv", "et al", "experiment", "baseline", "benchmark",
            "peer review", "citation", "conference", "journal",
        ]
        lower = query.lower()
        if any(sig in lower for sig in academic_signals):
            source = "scholar"
        else:
            source = "web"

    if source == "scholar":
        return _search_semantic_scholar(query)
    return _search_duckduckgo(query)


def knowledge_self_audit() -> dict[str, Any]:
    """Inspectable view of what the agent has learned across all knowledge channels.

    Surfaces confirmed preferences, candidate (inferred) signals, concept-graph
    health, tutor mastery, note-derived signals, and available correction actions.
    """
    profile = _load_user_profile()
    now = _now_iso()

    # ── confirmed preferences ──────────────────────────────────────────
    confirmed = {
        "preferences": [
            {"type": "style", "value": p.get("preference", ""), "source": p.get("source", "")[:200]}
            for p in profile.get("style_preferences", [])
        ],
        "avoidances": [
            {"type": "avoidance", "value": a.get("preference", ""), "source": a.get("source", "")[:200]}
            for a in profile.get("avoidances", [])
        ],
        "interests": [
            {"name": i.get("name", ""), "confidence": i.get("confidence", 0.0), "evidence": i.get("evidence", "")[:200]}
            for i in profile.get("interests", [])
        ],
        "adaptation_rules": profile.get("adaptation_rules", []),
    }

    # ── candidate signals ──────────────────────────────────────────────
    candidate_signals: list[dict[str, Any]] = []
    candidate_count = 0
    if CANDIDATE_SIGNALS_PATH.exists():
        try:
            raw = [json.loads(line) for line in CANDIDATE_SIGNALS_PATH.open("r", encoding="utf-8") if line.strip()]
            candidate_count = len(raw)
            # Show the 8 most recent + most frequent signal types.
            signal_types: Counter = Counter()
            for entry in raw[-40:]:
                for sig in entry.get("signals", []):
                    signal_types[sig.get("type", "unknown")] += 1
            candidate_signals = [
                {"type": st, "count": c, "status": "candidate — not yet confirmed"}
                for st, c in signal_types.most_common(8)
            ]
        except Exception:
            candidate_signals = [{"error": "Could not parse candidate signals file."}]

    # ── concept graph health ───────────────────────────────────────────
    concept_health: dict[str, Any] = {"strongest": [], "stale": [], "rejected": [], "merge_suggestions": []}
    try:
        graph = concept_graph.get_concept_graph()
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        # Strongest: top 5 by weight.
        ranked = sorted(nodes, key=lambda n: n.get("weight", 0.0), reverse=True)
        concept_health["strongest"] = [
            {"name": n["name"], "weight": n.get("weight", 0.0), "sources": n.get("sources", [])}
            for n in ranked[:5] if n.get("weight", 0) > 0
        ]
        # Stale: concepts with weight < 0.3 that haven't been updated recently.
        concept_health["stale"] = [
            {"name": n["name"], "weight": n.get("weight", 0.0)}
            for n in nodes if 0 < n.get("weight", 0) < 0.3
        ][:5]
        # Rejected: concepts marked as rejected.
        concept_health["rejected"] = [
            {"name": n["name"]} for n in nodes if n.get("rejected")
        ][:5]
        # Merge suggestions: concepts that share many edges with each other.
        name_to_neighbors: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            if src and tgt:
                name_to_neighbors[src].add(tgt)
                name_to_neighbors[tgt].add(src)
        seen_pairs: set[tuple[str, str]] = set()
        for name_a, neighbors_a in name_to_neighbors.items():
            for name_b, neighbors_b in name_to_neighbors.items():
                if name_a >= name_b:
                    continue
                pair = (name_a, name_b)
                if pair in seen_pairs:
                    continue
                overlap = neighbors_a & neighbors_b
                if len(overlap) >= 3:
                    seen_pairs.add(pair)
                    concept_health["merge_suggestions"].append({
                        "concept_a": name_a, "concept_b": name_b,
                        "shared_neighbors": sorted(overlap)[:5],
                        "rationale": f"Share {len(overlap)} neighbor concepts — consider merging.",
                    })
        concept_health["merge_suggestions"] = concept_health["merge_suggestions"][:5]
    except Exception:
        concept_health = {"error": "Concept graph not available or unreadable."}

    # ── tutor state ────────────────────────────────────────────────────
    tutor_state: dict[str, Any] = {"mastered": [], "weak": [], "total_concepts": 0}
    try:
        progress = _load_tutor_progress()
        concepts = progress.get("concepts", {})
        tutor_state["total_concepts"] = len(concepts)
        for key, entry in concepts.items():
            asked = max(entry.get("times_asked", 0), 1)
            ratio = entry.get("times_correct", 0) / asked
            if ratio >= 0.8:
                tutor_state["mastered"].append({"concept": key, "ratio": round(ratio, 2)})
            elif asked >= 2 and ratio < 0.5:
                tutor_state["weak"].append({"concept": key, "ratio": round(ratio, 2), "asked": asked})
        tutor_state["mastered"] = sorted(tutor_state["mastered"], key=lambda c: c["ratio"], reverse=True)[:8]
        tutor_state["weak"] = sorted(tutor_state["weak"], key=lambda c: c["ratio"])[:8]
    except Exception:
        tutor_state = {"error": "Tutor progress unavailable."}

    # ── note-derived signals ───────────────────────────────────────────
    note_signals: dict[str, Any] = {"total_notes": 0, "recent_concepts": []}
    try:
        all_notes = personal_notes.list_notes(
            path=PERSONAL_NOTES_PATH
        ).get("notes", [])
        note_signals["total_notes"] = len(all_notes)
        note_concepts: Counter = Counter()
        for n in all_notes[-30:]:
            for c in n.get("concepts", []):
                note_concepts[c] += 1
        note_signals["recent_concepts"] = [
            {"concept": c, "note_count": cnt} for c, cnt in note_concepts.most_common(8)
        ]
    except Exception:
        note_signals = {"error": "Personal notes unavailable."}

    # ── interaction summary ────────────────────────────────────────────
    interaction_summary: dict[str, Any] = {"total": 0, "recent_tags": []}
    if INTERACTION_LOG_PATH.exists():
        try:
            interactions = [
                json.loads(line) for line in INTERACTION_LOG_PATH.open("r", encoding="utf-8") if line.strip()
            ]
            interaction_summary["total"] = len(interactions)
            tag_counts: Counter = Counter()
            for entry in interactions[-50:]:
                for tag in entry.get("tags", "").split(","):
                    tag = tag.strip()
                    if tag:
                        tag_counts[tag] += 1
            interaction_summary["recent_tags"] = [
                {"tag": t, "count": c} for t, c in tag_counts.most_common(8)
            ]
        except Exception:
            interaction_summary = {"error": "Interaction log unreadable."}

    # ── correction actions available ───────────────────────────────────
    correction_actions = [
        {
            "action": "confirm_signal",
            "description": "Promote a candidate signal to a durable preference, interest, or rule.",
            "example": 'self_audit_correction(action="confirm_signal", target="interest:knowledge graphs", reason="Repeated interest across 3+ sessions")',
        },
        {
            "action": "reject_signal",
            "description": "Mark a candidate signal as rejected so it stops resurfacing in audits.",
            "example": 'self_audit_correction(action="reject_signal", target="signal:verbose_explanations", reason="User explicitly said they want brevity")',
        },
        {
            "action": "downgrade_preference",
            "description": "Reduce the weight of an over-promoted preference that no longer fits.",
            "example": 'self_audit_correction(action="downgrade_preference", target="preference:long form answers", reason="User has shifted to mobile use")',
        },
        {
            "action": "suppress_concept",
            "description": "Suppress a concept in graph ranking so it stops influencing recommendations.",
            "example": 'self_audit_correction(action="suppress_concept", target="concept:outdated_method", reason="Method superseded by newer paper")',
        },
    ]

    return {
        "audit_generated_at": now,
        "confirmed": confirmed,
        "candidate_signals": {
            "count": candidate_count,
            "top_types": candidate_signals,
            "path": str(CANDIDATE_SIGNALS_PATH),
        },
        "concept_graph": concept_health,
        "tutor_state": tutor_state,
        "notes": note_signals,
        "interaction_summary": interaction_summary,
        "correction_actions_available": correction_actions,
    }


def self_audit_correction(action: str, target: str, reason: str = "") -> dict[str, Any]:
    """Apply a user-directed correction to the knowledge model.

    Supported actions:
      - confirm_signal:   Promote a candidate signal to a durable preference.
      - reject_signal:    Reject a candidate signal so it stops resurfacing.
      - downgrade_preference:  Reduce weight of an over-promoted preference.
      - suppress_concept: Suppress a concept in graph ranking.
    """
    valid_actions = {"confirm_signal", "reject_signal", "downgrade_preference", "suppress_concept"}
    if action not in valid_actions:
        return {"status": "error", "message": f"Unknown action '{action}'. Valid: {sorted(valid_actions)}"}

    profile = _load_user_profile()
    now = _now_iso()

    if action == "confirm_signal":
        # Parse target: "interest:X" or "style:X" or "rule:X"
        if ":" in target:
            category, value = target.split(":", 1)
        else:
            category, value = "interest", target

        if category == "interest":
            existing = [i for i in profile.get("interests", []) if i.get("name", "").lower() == value.lower()]
            if existing:
                existing[0]["confidence"] = min(1.0, existing[0].get("confidence", 0.5) + 0.2)
                existing[0]["evidence"] = f"{existing[0].get('evidence', '')}; confirmed via audit correction: {reason}"[:400]
            else:
                profile.setdefault("interests", []).append({
                    "name": value, "confidence": 0.85,
                    "evidence": f"Confirmed via audit correction: {reason}"[:400],
                })
        elif category in ("style", "preference"):
            profile.setdefault("style_preferences", []).append({
                "preference": value, "source": f"Audit correction: {reason}"[:400],
            })
        elif category == "rule":
            profile.setdefault("adaptation_rules", []).append({
                "rule": value, "source": f"Audit correction: {reason}"[:400],
                "confirmed_at": now,
            })

        profile["updated_at"] = now
        _save_user_profile(profile)
        return {"status": "ok", "action": "confirm_signal", "target": target, "reason": reason}

    if action == "reject_signal":
        # Record rejection so the signal type stops resurfacing.
        rejection = {
            "timestamp": now,
            "target": target,
            "reason": reason,
            "action": "rejected",
        }
        _ensure_dirs()
        with CANDIDATE_SIGNALS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rejection) + "\n")
        return {"status": "ok", "action": "reject_signal", "target": target, "reason": reason}

    if action == "downgrade_preference":
        # Lower confidence on a matching preference/interest.
        for bucket in ["interests", "style_preferences"]:
            for item in profile.get(bucket, []):
                name = item.get("name") or item.get("preference", "")
                if target.lower() in name.lower():
                    item["confidence"] = max(0.1, item.get("confidence", 0.5) - 0.3)
                    item["downgraded_at"] = now
                    item["downgrade_reason"] = reason[:300]
        profile["updated_at"] = now
        _save_user_profile(profile)
        return {"status": "ok", "action": "downgrade_preference", "target": target, "reason": reason}

    if action == "suppress_concept":
        try:
            concept_graph.reject_concept(target, reason)
        except Exception:
            pass  # best-effort — graph may not have a reject_concept method yet
        return {"status": "ok", "action": "suppress_concept", "target": target, "reason": reason}

    return {"status": "error", "message": "Unhandled action."}


def adaptive_grill(topic: str = "", source: str = "", question_count: int = 5) -> dict[str, Any]:
    """Generate personalized questions and recommendations from the user model and ingested text."""
    profile = _load_user_profile()
    records = _load_records()
    if source:
        records = [
            record
            for record in records
            if source.lower() in record["source"].lower()
            or source.lower() in record.get("metadata", {}).get("title", "").lower()
        ]

    profile_summary = _profile_signal_summary(profile)
    cards = _note_cards_for_records(records)

    # --- ADR 0026: note-guided questioning — boost with personal note concepts ---
    note_concepts: list[str] = []
    try:
        note_list = personal_notes.list_notes(path=PERSONAL_NOTES_PATH).get("notes", [])
        for n in note_list[-20:]:
            note_concepts.extend(n.get("concepts", []))
        # Deduplicate and keep top 15.
        seen: set[str] = set()
        deduped: list[str] = []
        for c in note_concepts:
            key = c.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(c)
        note_concepts = deduped[:15]
    except Exception:
        pass

    # --- concept graph: rank cards by user-interest weight ---
    try:
        user_interests = [item.get("name", "") for item in profile.get("interests", [])]
        if user_interests:
            cards = concept_graph.rank(user_interests, cards)
    except Exception:
        pass  # best-effort ranking; fall back to default card order

    questions: list[dict[str, Any]] = []
    max_questions = max(1, min(question_count, 12))

    interest = next(
        (item for item in profile.get("interests", []) if item.get("name")),
        {"name": "research agents", "evidence": "Default research-agent focus."},
    )
    style = next(
        (item for item in profile.get("style_preferences", []) if item.get("preference")),
        {"preference": "prefer concrete next steps"},
    )

    if topic:
        matches = search_evidence(topic, 4)["matches"]
        for index, match in enumerate(matches, start=1):
            questions.append(
                _adaptive_question(
                    f"Q{len(questions)+1:03d}",
                    (
                        f"When you read this passage about '{topic}', what do you want "
                        "to decide or build from it?"
                    ),
                    (
                        "Turn your answer into a saved preference if it describes a recurring "
                        "research interest or decision pattern."
                    ),
                    "The topic matched an evidence passage, and your profile favors actionable follow-through.",
                    source=match["source"],
                    citation=match["citation"],
                    profile_signal=style.get("preference", ""),
                )
            )
            if index >= 2:
                break

    for card in cards:
        if len(questions) >= max_questions:
            break
        if card["bucket"] == "limitations":
            questions.append(
                _adaptive_question(
                    f"Q{len(questions)+1:03d}",
                    f"Does this limitation change how you would trust or use {card['title']}?",
                    "If yes, ask for a comparison against another paper before adopting the idea.",
                    "Limitations are a good fit for your preference for practical, decision-oriented questions.",
                    source=card["source"],
                    citation=card["citation"],
                    profile_signal=interest.get("name", ""),
                )
            )
        elif card["bucket"] == "methods":
            questions.append(
                _adaptive_question(
                    f"Q{len(questions)+1:03d}",
                    f"What part of this method would you want your own agent to copy, reject, or test?",
                    "Extract a reusable design pattern only after tying it to a cited method passage.",
                    "Your profile emphasizes agent-building and iterative improvement.",
                    source=card["source"],
                    citation=card["citation"],
                    profile_signal=interest.get("name", ""),
                )
            )
        elif card["bucket"] == "open_questions":
            questions.append(
                _adaptive_question(
                    f"Q{len(questions)+1:03d}",
                    f"Which open question here is most worth turning into your next research task?",
                    "Promote the chosen question into a follow-up search or paper-comparison prompt.",
                    "Open questions connect the text to your recurring workflow of improving the agent.",
                    source=card["source"],
                    citation=card["citation"],
                    profile_signal=style.get("preference", ""),
                )
            )

    # --- ADR 0026: note-guided questions ---
    for concept in note_concepts:
        if len(questions) >= max_questions:
            break
        questions.append(
            _adaptive_question(
                f"Q{len(questions)+1:03d}",
                f"Your notes mention '{concept}'. Has anything in these papers changed "
                "your thinking about it?",
                "If yes, save an updated note with your new perspective.",
                f"Your personal notes connect this concept to your research interests.",
                profile_signal=concept,
            )
        )

    if len(questions) < max_questions:
        questions.append(
            _adaptive_question(
                f"Q{len(questions)+1:03d}",
                "When I ask you research questions, do you want me to challenge assumptions first or summarize evidence first?",
                "Save the answer with set_user_preference as a style preference.",
                "This resolves an adaptation choice the current user model cannot infer with high confidence.",
                profile_signal=", ".join(profile_summary["question_patterns"][:2]),
            )
        )

    if len(questions) < max_questions:
        questions.append(
            _adaptive_question(
                f"Q{len(questions)+1:03d}",
                "What topics should I keep connecting papers back to by default?",
                "Save recurring topics as interests so future paper briefs become more relevant.",
                "The user model benefits from explicit interests, not just inferred ones.",
                profile_signal=", ".join(profile_summary["interests"][:3]),
            )
        )

    session = {
        "timestamp": _now_iso(),
        "topic": topic or None,
        "source": source or None,
        "profile_summary": profile_summary,
        "questions": questions[:max_questions],
    }
    _append_grill_session(session)

    return {
        "session_log_path": str(GRILL_LOG_PATH),
        "first_question": questions[0] if questions else None,
        "queued_questions": questions[1:max_questions],
        "recommendation": (
            "Ask the first question only. After the user answers, call "
            "respond_to_adaptive_grill to update the user model and choose the next question."
        ),
        "profile_summary": profile_summary,
    }


def respond_to_adaptive_grill(question_id: str, user_answer: str, question_text: str = "") -> dict[str, Any]:
    """Learn from a user's grill answer and recommend the next adaptation."""
    candidate_signals = _infer_message_signals(user_answer)
    explicit_memory = _is_explicit_memory_request(user_answer)
    context = f"answer to adaptive grill question {question_id}: {question_text[:180]}"
    _record_candidate_signals(
        {
            "timestamp": _now_iso(),
            "question_id": question_id,
            "question_text": question_text,
            "user_answer": user_answer,
            "signals": candidate_signals,
            "explicit_memory_request": explicit_memory,
        }
    )
    record_interaction(
        user_message=user_answer,
        agent_response=f"Adaptive grill answer for {question_id}",
        outcome="captured_candidate_signal",
        tags="adaptive_grill,personalization",
    )

    # --- concept graph: link the grill question's concept to user interests ---
    if question_text:
        try:
            profile = _load_user_profile()
            for interest in profile.get("interests", []):
                interest_name = interest.get("name", "")
                if interest_name and any(
                    token in question_text.lower()
                    for token in interest_name.lower().split()
                ):
                    concept_graph.link(
                        interest_name, question_text[:120], "adaptive_grill", edge_type="engaged"
                    )
        except Exception:
            pass  # best-effort graph linking

    lower = user_answer.lower()
    durable_updates = []
    if explicit_memory and any(word in lower for word in ["short", "concise", "brief", "blunt"]):
        durable_updates.append(
            set_user_preference(
                "style",
                "Prefer short, direct grill questions and compact recommendations.",
                user_answer[:240],
                0.85,
            )
        )
    if explicit_memory and any(word in lower for word in ["challenge", "assumption", "push", "grill"]):
        durable_updates.append(
            set_user_preference(
                "adaptation_rule",
                "When reviewing papers, challenge assumptions and ask one pointed follow-up question.",
                user_answer[:240],
                0.82,
            )
        )
    if explicit_memory and any(word in lower for word in ["build", "agent", "workflow", "tool"]):
        durable_updates.append(
            set_user_preference(
                "interest",
                "turning research into agent/tool/workflow improvements",
                user_answer[:240],
                0.8,
            )
        )

    result = {
        "status": "ok",
        "candidate_signals_path": str(CANDIDATE_SIGNALS_PATH),
        "candidate_signals": candidate_signals,
        "explicit_memory_request": explicit_memory,
        "durable_updates": durable_updates,
        "next_recommendation": (
            "Treat this as provisional unless it repeats or the user explicitly asked "
            "to remember it. Ask the next queued adaptive_grill question, or call "
            "adaptive_grill again with a narrower topic if the answer revealed a new direction."
        ),
    }
    return _projection_status(result, "grill_answer", question_id, question_text)


# ---------------------------------------------------------------------------
# Tutor Mode — helpers and tools
# ---------------------------------------------------------------------------


def _load_tutor_progress() -> dict[str, Any]:
    """Load concept-level mastery summary, cached in memory."""
    cache = getattr(_load_tutor_progress, "_cache", None)
    if cache is not None:
        return cache
    _ensure_dirs()
    if not TUTOR_PROGRESS_PATH.exists():
        progress: dict[str, Any] = {"schema_version": 1, "concepts": {}}
        TUTOR_PROGRESS_PATH.write_text(json.dumps(progress, indent=2), encoding="utf-8")
        _load_tutor_progress._cache = progress  # type: ignore[attr-defined]
        return progress
    try:
        progress = json.loads(TUTOR_PROGRESS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        progress = {"schema_version": 1, "concepts": {}, "recovery_note": "file was unreadable"}
        TUTOR_PROGRESS_PATH.write_text(json.dumps(progress, indent=2), encoding="utf-8")
    if not _validate_tutor_progress(progress):
        logger.warning("Tutor progress failed validation, restoring defaults")
        progress = {"schema_version": 1, "concepts": {},
                      "recovery_note": "tutor_progress.json failed validation"}
        TUTOR_PROGRESS_PATH.write_text(json.dumps(progress, indent=2), encoding="utf-8")
    _load_tutor_progress._cache = progress  # type: ignore[attr-defined]
    return progress


def _validate_tutor_progress(progress: dict[str, Any]) -> bool:
    """Return True if tutor progress has required fields with correct types."""
    if not isinstance(progress.get("schema_version"), int):
        return False
    if not isinstance(progress.get("concepts"), dict):
        return False
    return True


def _save_tutor_progress(progress: dict[str, Any]) -> None:
    _ensure_dirs()
    progress["updated_at"] = _now_iso()
    TUTOR_PROGRESS_PATH.write_text(json.dumps(progress, indent=2), encoding="utf-8")
    _load_tutor_progress._cache = progress  # type: ignore[attr-defined]


def _next_concept(
    progress: dict[str, Any],
    user_interests: list[str],
    last_was_weak: bool,
) -> dict[str, Any]:
    """Pick the next concept to teach using alternating weak/interest strategy.

    Prerequisite hints (concept-graph dependencies) get a one-hop priority
    boost: if a candidate concept has an unmet prerequisite, that prerequisite
    is favoured instead.  The boost is advisory, never blocking.
    """
    concepts = progress.get("concepts", {})
    weak: list[dict[str, Any]] = []
    strong: list[dict[str, Any]] = []

    for key, entry in concepts.items():
        asked = max(entry.get("times_asked", 0), 1)
        ratio = entry.get("times_correct", 0) / asked
        entry["_key"] = key
        if ratio < 0.5:
            weak.append(entry)
        elif ratio < 1.0:
            strong.append(entry)

    weak.sort(key=lambda e: e.get("times_correct", 0) / max(e.get("times_asked", 1), 1))

    # --- Prerequisite priority boost (one-hop) ---
    # For every candidate concept (weak first, then strong), check whether it
    # has unmet prerequisites.  If an unmet prerequisite exists and is also
    # a known concept (in tutor progress), boost its position in the weak
    # list.  If the prerequisite has never been taught, offer it as a new
    # concept to introduce.
    try:
        for candidate_list in (weak, strong):
            for entry in candidate_list:
                concept_key = entry["_key"]
                for prereq_key in concept_graph.get_prerequisites(concept_key):
                    # Already mastered? Skip.
                    prereq_entry = concepts.get(prereq_key)
                    if prereq_entry:
                        asked_p = max(prereq_entry.get("times_asked", 0), 1)
                        ratio_p = prereq_entry.get("times_correct", 0) / asked_p
                        if ratio_p >= 0.8:
                            continue  # mastered — no boost needed
                        # Boost: move this prerequisite to the front of the weak list.
                        prereq_entry["_key"] = prereq_key
                        if prereq_entry not in weak:
                            weak.insert(0, prereq_entry)
                    else:
                        # Prerequisite concept exists in the dependency graph
                        # but hasn't been taught at all — introduce it.
                        return {
                            "concept": prereq_key,
                            "reason": "prerequisite for '{}' — never taught yet".format(concept_key),
                        }
    except Exception:
        pass  # best-effort; fall back to default ordering

    if not last_was_weak and weak:
        target = weak[0]
        return {"concept": target["_key"], "reason": "weak concept — only {}/{} correct".format(
            target.get("times_correct", 0), target.get("times_asked", 1))}

    if strong:
        target = strong[-1]
        return {"concept": target["_key"], "reason": "strong concept — reinforce before mastery"}

    if weak:
        target = weak[0]
        return {"concept": target["_key"], "reason": "weak concept — {}/{} correct".format(
            target.get("times_correct", 0), target.get("times_asked", 1))}

    if user_interests:
        return {"concept": user_interests[0], "reason": "new session — starting with your top interest"}
    return {"concept": None, "reason": "no progress and no interests — ask the user what to study"}


def _grade_answer(question: str, user_answer: str, passage_text: str) -> dict[str, Any]:
    """Grade a free-text tutor answer via LLM.  Returns CORRECT / INCORRECT + reason."""
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    prompt = (
        "You are grading a student's answer to a question about a research paper.\n\n"
        f"Question: {question}\n\n"
        f"Source passage: {passage_text[:1200]}\n\n"
        f"Student answer: {user_answer}\n\n"
        "Reply with exactly one line: CORRECT or INCORRECT, followed by a one-sentence "
        "reason. If the answer is partially correct but misses something important, say "
        "INCORRECT and explain what's missing. If the answer is mostly right but has a "
        "minor confusion, say CORRECT and note the confusion as a hint.\n\n"
        "Format: VERDICT. Reason. [HINT: optional one-sentence teaching hint]"
    )
    try:
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.0,
        )
        text = response.choices[0].message.content or "INCORRECT. Could not grade."
    except Exception:
        return {"correct": False, "verdict": "INCORRECT", "reason": "grading error", "raw": ""}

    upper = text.strip().upper()
    correct = upper.startswith("CORRECT")
    parts = text.split(". ", 1)
    reason = parts[1] if len(parts) > 1 else text
    hint = ""
    if "HINT:" in reason:
        reason, hint = reason.split("HINT:", 1)

    return {
        "correct": correct,
        "verdict": "CORRECT" if correct else "INCORRECT",
        "reason": reason.strip(),
        "mastery_hint": hint.strip() if hint else None,
        "raw": text,
    }


def record_tutor_answer(
    concept: str,
    question: str,
    user_answer: str,
    source: str = "",
    passage_text: str = "",
) -> dict[str, Any]:
    """Grade a tutor answer, record progress, update the concept graph, and suggest the next concept."""
    grade = _grade_answer(question, user_answer, passage_text) if passage_text else {"correct": True, "verdict": "CORRECT", "reason": "no passage to grade against", "mastery_hint": None}
    correct = grade["correct"]

    # Update tutor progress.
    progress = _load_tutor_progress()
    concepts = progress.setdefault("concepts", {})
    key = concept.strip().lower()
    entry = concepts.setdefault(key, {"concept": concept, "times_asked": 0, "times_correct": 0, "last_seen": None})
    entry["times_asked"] += 1
    if correct:
        entry["times_correct"] += 1
    entry["last_seen"] = _now_iso()
    if grade.get("mastery_hint"):
        entry.setdefault("mastery_hints", []).append(grade["mastery_hint"])
    _save_tutor_progress(progress)

    # Log the session event.
    _ensure_dirs()
    session_event = {
        "timestamp": _now_iso(),
        "concept": concept,
        "question": question,
        "user_answer": user_answer,
        "correct": correct,
        "verdict": grade["verdict"],
        "reason": grade["reason"],
        "mastery_hint": grade.get("mastery_hint"),
        "source": source or None,
    }
    with TUTOR_SESSIONS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(session_event) + "\n")

    # Strengthen the concept graph — tutor engagement is engagement.
    try:
        profile = _load_user_profile()
        for interest in profile.get("interests", []):
            interest_name = interest.get("name", "")
            if not interest_name:
                continue
            sim = concept_graph._similarity(interest_name, concept)
            if sim > 0:
                concept_graph.link(
                    interest_name, concept, source or "tutor_session",
                    edge_type="engaged", similarity_score=sim,
                )
    except Exception:
        pass

    # Mastery → graph feedback: mastered concepts get deprioritised in the graph.
    asked = max(entry.get("times_asked", 1), 1)
    ratio = entry.get("times_correct", 0) / asked
    try:
        graph = concept_graph.load()
        edges = graph.get("edges", {})
        if ratio >= 0.8:
            # Mastered — reduce edge weight to floor so rank() deprioritises.
            for interest_key in list(edges):
                edge = edges[interest_key].get(key)
                if edge is not None:
                    edge["weight"] = round(max(0.1, edge.get("weight", 1.0) * 0.3), 2)
                    edge["mastered"] = True
        elif ratio < 0.5:
            # Weak — boost edge weight so this concept stays visible in rankings.
            for interest_key in list(edges):
                edge = edges[interest_key].get(key)
                if edge is not None and not edge.get("mastered"):
                    edge["weight"] = round(edge.get("weight", 1.0) + 0.5, 2)
        concept_graph._save(graph)
    except Exception:
        pass
    # Invalidate concept_graph cache so next load picks up the mastery-adjusted weights.
    concept_graph._graph_cache = graph

    # Suggest the next concept.
    user_interests = [item.get("name", "") for item in _load_user_profile().get("interests", [])]
    last_was_weak = ratio < 0.5
    next_concept = _next_concept(progress, user_interests, last_was_weak)

    result = {
        "status": "ok",
        "concept": concept,
        "correct": correct,
        "verdict": grade["verdict"],
        "reason": grade["reason"],
        "mastery_hint": grade.get("mastery_hint"),
        "progress": {"times_asked": entry["times_asked"], "times_correct": entry["times_correct"]},
        "suggested_next_concept": next_concept,
        "sessions_log_path": str(TUTOR_SESSIONS_PATH),
    }
    return _projection_status(result, "tutor_progress", concept)


def get_tutor_progress() -> dict[str, Any]:
    """Inspect tutor progress — concept-level mastery summary."""
    progress = _load_tutor_progress()
    summary = []
    for key, entry in sorted(progress.get("concepts", {}).items()):
        asked = max(entry.get("times_asked", 0), 1)
        summary.append({
            "concept": entry.get("concept", key),
            "times_asked": entry.get("times_asked", 0),
            "times_correct": entry.get("times_correct", 0),
            "mastery": round(entry.get("times_correct", 0) / asked, 2),
            "last_seen": entry.get("last_seen"),
        })
    return {
        "progress_path": str(TUTOR_PROGRESS_PATH),
        "sessions_log_path": str(TUTOR_SESSIONS_PATH),
        "concept_count": len(summary),
        "concepts": summary,
    }


def _safe_tool(fn):
    """Wrap a tool function so exceptions return an error dict instead of raising.

    This prevents the ADK from sending malformed message chains to the LLM
    when a tool call fails mid-execution.  DeepSeek's API is strict about
    requiring a tool response for every tool_call_id.
    """
    from functools import wraps

    @wraps(fn)
    def _wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            return {
                "status": "error",
                "tool": fn.__name__,
                "message": str(exc)[:500],
            }

    return _wrapper


# ── Smart context header ───────────────────────────────────────────────
# ADR 0069: Inject a compact snapshot of durable state into the system
# instruction on every turn so the agent stays sharp without needing to
# remember to call profile/notes/graph tools.  Target: ≤ 500 tokens.
#
# The snapshot is cache-stabilized: it only rebuilds when the underlying
# ── ADR 0072 / Architecture Plan Phase 1 ────────────────────────────
# Dynamic context construction has been extracted to
# agent_runtime/dynamic_context.py.  Re-export the cache for test
# compatibility and keep the public _dynamic_instruction entry point.

_SNAPSHOT_CACHE = _dynamic_ctx._SNAPSHOT_CACHE  # re-export for tests


def _state_fingerprint() -> str:
    """Return a short hash of all durable state that feeds the snapshot.

    Delegates to agent_runtime.dynamic_context.state_fingerprint.
    """
    return _dynamic_ctx.state_fingerprint()


def _build_snapshot(ctx: Any | None = None) -> str:
    """Build a compact context header — legacy path, delegates to deep snapshot.

    Kept for backward compatibility; new code should use the budget-aware
    builders in agent_runtime.dynamic_context.
    """
    return _dynamic_ctx._build_deep_snapshot(ctx)


# The static instruction body (extracted from the old inline string so
# it can be combined with the dynamic snapshot header).
_STATIC_INSTRUCTION = (
    "You are a Personal Knowledge Manager: grounded, adaptive, privacy-aware, "
    "and focused on the user's current session goal. Use the active Agent Mode "
    "to choose posture; Mentor Mode is one mode among many, not the default "
    "identity of the whole agent. "
    "For factual answers, call search_evidence and cite the returned citation "
    "fields. Use paper_brief for summaries, compare_papers for cross-paper "
    "synthesis, and make_study_guide for learning workflows. "
    "Use rename_paper, delete_paper, and organize_papers to manage the papers/ "
    "directory. rename_paper atomically migrates file, knowledge-base record, "
    "and concept-graph edges. delete_paper defaults to dry-run preview; only "
    "execute when the user confirms. organize_papers accepts a mapping of "
    "{old_name: new_name} and runs each rename independently. "
    "Use save_personal_note only for explicit note capture prompts such as "
    "'note:', 'save note:', 'remember note:', or direct requests to store a "
    "personal knowledge-management note. Do not save ordinary unmarked chat "
    "as a note. Use list_personal_notes, get_personal_note, and "
    "search_personal_notes when the user asks about their notes. Treat personal "
    "notes as the user's knowledge/context, not as source-backed paper evidence. "
    "Use Relationship Management tools only for explicit relationship prompts "
    "such as 'add person:', 'relationship note:', 'log interaction', or direct "
    "requests to remember someone. Do not silently create Person records from "
    "ordinary chat. Use add_person, list_people, get_person, search_people, "
    "add_relationship_note, log_relationship_interaction, recommend_reconnections, "
    "and forget_person for relationship memory. Relationship data is sensitive: "
    "when summaries contain Sensitive Relationship Context, soften or omit it "
    "unless the user directly asks for full context. For professional, networking, "
    "or collaboration relationships you may draft outreach when asked; for "
    "personal or intimate relationships, suggest context or an angle and leave "
    "the wording to the user. Never send messages externally. "
    "Edit notes with edit_personal_note, reject incorrect cards with "
    "reject_note_card, and remove misleading concepts with reject_note_concept. "
    "Use get_note_backlinks to discover notes that share concepts — the backlinks "
    "are derived from the Concept Graph, not manual wiki-links. "
    "When answering with both papers and personal notes, separate your output "
    "into three labeled lanes: **Evidence** (cited paper passages), "
    "**Your Notes** (relevant personal notes and cards), and **Inference** "
    "(your synthesis, clearly labeled as inferential). "
    "Adapt across three separate dimensions per concept: content_selection "
    "(what to show), explanation_style (how to explain), and challenge_level "
    "(difficulty of questions). A user may want concise answers about one "
    "topic but deeper scaffolding on another — do not use one global setting. "
    "Separate source-backed "
    "claims from your own inference. Before giving a personalized recommendation "
    "from a paper, establish at least one cited source-backed claim first; label "
    "brainstorming or extrapolation as inference. Exercise research taste: when "
    "a paper seems low-yield, say whether to skim, study deeply, compare, or "
    "discard, and justify that recommendation with citations and the user model. "
    "Follow the user's known interests by default, but include at most one adjacent "
    "possibility when the text strongly suggests a nearby idea worth considering; "
    "make it easy for the user to reject that direction. "
    "Be warm but not deferential: if the user's interpretation exceeds the "
    "evidence, or their preferred direction conflicts with the paper or their "
    "stated goals, push back with citations and propose a safer framing. "
    "For every personalized recommendation, include a Recommendation Confidence "
    "label: High when directly cited and aligned with user goals, Medium when "
    "text-supported but interpretive, and Low when speculative, adjacent, or weakly "
    "supported. Explain the confidence briefly. "
    "After meaningful paper reading, grilling, synthesis, or recommendation work, "
    "offer to produce a compact session artifact such as concept cards, decision "
    "notes, open questions, agent-building ideas, a reading queue, or user-model "
    "updates. Ask before creating artifacts, but make the offer specific by naming "
    "the exact artifact shape. "
    "Support explicit modes when the user names them. Detect the mode from "
    "the first message and switch posture accordingly — do not wait for "
    "the user to repeat the mode name. "
    "Reader Mode means faithful source understanding (also called Source Mode); "
    "Grill Mode means one pointed adaptive question at a time; "
    "Builder Mode means Socratic ideation "
    "and design partnership; Taste Mode means judge skim/study/"
    "compare/discard; Artifact Mode means create confirmed durable outputs; "
    "Profile Mode means inspect or update the user model (also called Reflect Mode); "
    "Tutor Mode means "
    "teach paper concepts through an explain-then-quiz loop with adaptive "
    "curriculum. In Tutor Mode, use search_evidence to find a cited passage, "
    "explain the concept, ask one question via adaptive_grill, then call "
    "record_tutor_answer to grade the response and suggest the next concept. "
    "Alternate between drilling weak concepts and exploring high-interest ones; "
    "let the user steer at any point. "
    "Builder Mode means Socratic ideation and design partnership. Follow "
    "a three-phase flow: (1) Clarify — ask one Socratic question about the "
    "user's goal, shaped by get_user_profile, get_note_backlinks, and recent "
    "papers. (2) Generate — produce 3–5 ideas with Ideation Provenance tags "
    "on every component: [from your notes], [cited: source], or [inference]. "
    "(3) Grill — the user picks an idea; stress-test one component at a "
    "time across feasibility, trade-offs, assumptions, risks, adjacent "
    "possibilities from papers/notes, conflicts with stated preferences, and "
    "knowledge gaps from get_tutor_progress. Ask one pointed question per "
    "component. Let the user steer depth — stop when they say stop. "
    "Writing Mode means transform knowledge into prose with attention to "
    "voice, flow, expression, and audience. By default, apply moderate "
    "polish to the user's prompts and responses — fix grammar, improve "
    "clarity, and elevate word choice. Read the user's polish_preferences "
    "from the profile for per-context settings (chat, technical, creative, "
    "default). When the user says 'keep my wording,' 'too formal,' or "
    "'that's not what I meant,' record a Polish Preference correction "
    "through learn_from_user_message for that context. Polish levels: "
    "none (exact wording), light (grammar only), moderate (grammar + flow), "
    "full (significant restructuring). Start proactive and learn to match "
    "the user's expected level over time. "
    "Adapt to cognitive diversity by default. Chunk long answers into "
    "labeled sections and signal structure upfront ('Three things about X'). "
    "Lead every answer with the most personally relevant insight before "
    "providing full explanation. Vary pacing based on engagement — rapid-fire "
    "when the user is locked in, gentle check-ins when quiet. After meaningful "
    "answers, offer one to three concrete next actions. When resuming after a pause, re-anchor with 'You were "
    "exploring X. Continue or pivot?' — don't dump a recap. Check comprehension "
    "before continuing on complex topics. Default to actionable over abstract. "
    "Session metadata is written by runtime/application code, not by model tool "
    "calls; use provided session context when adapting pacing or re-anchoring. "
    "Mentor Mode means think through a mentor's cognitive framework using "
    "their ingested papers as your reasoning substrate. Simon is the default "
    "only inside Mentor Mode. In Simon mode, call search_evidence with "
    "evidence_scope='mentor:simon' before making Simon-derived framework claims, then synthesize through "
    "frameworks such as satisficing, bounded rationality, design science, and "
    "means-ends analysis. In Lanier mode, activated by 'Lanier,' 'Jaron,' or a "
    "clearly requested human-centered critique, call search_evidence with "
    "evidence_scope='mentor:lanier' before making Lanier-derived framework claims, then synthesize through "
    "human agency, phenomenological critique, data dignity, and contrarian "
    "warmth. If the relevant mentor corpus is missing or cannot be isolated "
    "from the general knowledge base, say so and offer either source ingestion "
    "or a clearly labeled inspired/inference lens. Speak as the agent applying "
    "the mentor model, not as Simon or Lanier. In both modes, adapt to the user "
    "specifically through existing privacy and provenance boundaries: use "
    "get_user_profile for style_preferences, get_tutor_progress for challenge "
    "level, and apply cognitive adaptation rules. Use relevant notes, concept "
    "graph context, and interests naturally, but do not treat Personal Notes as "
    "mentor-source evidence or pull sensitive relationship context unless it is "
    "directly relevant and requested. "
    "When the user asks for an audit of what you've learned about them, call "
    "knowledge_self_audit to produce the full inspectable view — confirmed "
    "preferences, candidate signals, concept graph health, tutor mastery, and "
    "note-derived signals. Present the audit with the correction actions listed "
    "at the bottom so the user can steer: confirm a signal, reject one, downgrade "
    "a preference, or suppress a concept. Call self_audit_correction only when "
    "the user explicitly asks to apply one of those actions. "
    "Prioritize the current session goal over the long-term user profile; use the "
    "profile to shape style and suggestions, then include adjacent possibilities "
    "only after the session goal is served. Infer the session goal by default; "
    "ask one clarifying question only when ambiguity would materially change the "
    "output. The agent may propose improvements to itself from research insights, "
    "but must not claim to modify its own code automatically; code changes require "
    "explicit user approval and a separate implementation step. "
    "Treat answers to adaptive grill questions as provisional candidate signals "
    "unless the user explicitly says to remember them; do not over-promote one "
    "exploratory answer into a durable preference. "
    "Use the Concept Graph (get_concept_graph) to rank grill questions by "
    "user-interest weight and to annotate paper briefs with interest_match "
    "labels (high/medium/low). When a paper is ingested, concept-graph edges "
    "are created automatically; grill answers and explicit saves strengthen "
    "them. "
    "Use get_user_profile when tailoring tone, "
    "format, or topic selection. Call learn_from_user_message when a user message "
    "reveals a new interest, question pattern, communication quirk, or correction. "
    "Call set_user_preference for explicit preferences. The user prefers direct, "
    "useful progress, but also wants more lengthy answers shaped around their "
    "personality for explanations, synthesis, and recommendations. Keep grill "
    "questions pointed, then give richer reasoning after answers. Do not overfit "
    "from weak signals. "
    "When the user wants questioning, grilling, or recommendations, call "
    "adaptive_grill and ask only its first_question. After the user answers, call "
    "respond_to_adaptive_grill before giving the next recommendation. "
    "If papers have not been ingested, ask the user to add files or call "
    "ingest_all_papers when they ask to read the folder. Before concluding "
    "nothing is ingested, always check first: call list_concepts or "
    "paper_brief to see what's already in the knowledge base — papers "
    "persist across sessions and do not need to be re-ingested. "
    "When the user edits or interacts with notes, the knowledge loop "
    "automatically updates graph signals and candidate patterns — you do "
    "not need to manually route these updates. Use suggest_concept_merges "
    "to find near-duplicate concepts that could be consolidated, and "
    "render_note_markdown and import_markdown_notes to sync between the "
    "canonical JSONL store and Markdown mirrors. "
    "Use search_web to look up information beyond ingested papers. "
    "For academic queries (research, papers, methods, findings), use "
    "source='scholar' which searches Semantic Scholar and returns "
    "peer-reviewed paper metadata with `[cited: paper, via Semantic Scholar]` "
    "provenance. For general or how-to queries, use source='web' which "
    "searches DuckDuckGo and returns web results tagged `[from web: domain.com]` "
    "with source_quality labels. Web-sourced claims are capped at Medium "
    "recommendation confidence — web content is not peer-reviewed. Present "
    "web results in their own lane, distinct from paper Evidence and your "
    "Personal Notes. "
    "Support these agent modes, inferred from user intent: Source (understand "
    "papers faithfully, formerly Reader), Retrieve (search papers/web/notes), "
    "Synthesis (combine across sources with provenance), Builder (Socratic "
    "ideation and design), Grill (one adaptive question at a time), Tutor "
    "(explain-then-quiz loop), Reflect (inspect/update user model, formerly "
    "Profile), Relationship (manage people and interactions), Taste (judge "
    "skim/study/compare/discard), Review (audit knowledge state), Writing "
    "(draft and revise prose), Artifact (create durable outputs), Admin "
    "(manage files and config), Mentor (guide thinking through Simon's "
    "design-science lens; invoke 'Lanier' for humanistic perspective). "
    "Use at most one primary mode plus one "
    "supporting mode; infer silently by default. "
    "Keep answers structured, grounded, adaptive, and appropriately detailed."
)


def _dynamic_instruction(ctx: Any) -> str:
    """Instruction provider: delegate to budget-aware dynamic context.

    ADR 0072 Slice 1: the agent_runtime.dynamic_context module handles
    budget inference, tier-specific snapshot construction, budget-aware
    caching, and compaction hints.

    The static instruction body is set via ``static_instruction=`` so it
    stays in the cacheable system-instruction slot.
    """
    return _dynamic_ctx.build_dynamic_instruction(ctx)


root_agent = Agent(
    model=DeepSeekLlm(),
    name="research_paper_agent",
    description="Reads research papers, extracts concepts, compares papers, and answers grounded questions.",
    static_instruction=_STATIC_INSTRUCTION,
    instruction=_dynamic_instruction,
    before_model_callback=_dynamic_ctx.build_before_model_callback(),
    tools=[
        _safe_tool(list_papers),
        _safe_tool(rename_paper),
        _safe_tool(delete_paper),
        _safe_tool(organize_papers),
        _safe_tool(ingest_paper),
        _safe_tool(ingest_all_papers),
        _safe_tool(list_concepts),
        _safe_tool(search_evidence),
        _safe_tool(paper_brief),
        _safe_tool(compare_papers),
        _safe_tool(make_study_guide),
        _safe_tool(get_user_profile),
        _safe_tool(learn_from_user_message),
        _safe_tool(record_interaction),
        _safe_tool(set_user_preference),
        _safe_tool(save_personal_note),
        _safe_tool(list_personal_notes),
        _safe_tool(get_personal_note),
        _safe_tool(search_personal_notes),
        _safe_tool(delete_personal_note),
        _safe_tool(edit_personal_note),
        _safe_tool(reject_note_card),
        _safe_tool(reject_note_concept),
        _safe_tool(get_note_backlinks),
        _safe_tool(render_note_markdown),
        _safe_tool(import_markdown_notes),
        _safe_tool(add_person),
        _safe_tool(list_people),
        _safe_tool(get_person),
        _safe_tool(search_people),
        _safe_tool(add_relationship_note),
        _safe_tool(log_relationship_interaction),
        _safe_tool(recommend_reconnections),
        _safe_tool(forget_person),
        _safe_tool(search_web),
        _safe_tool(knowledge_self_audit),
        _safe_tool(self_audit_correction),
        _safe_tool(adaptive_grill),
        _safe_tool(respond_to_adaptive_grill),
        _safe_tool(concept_graph.get_concept_graph),
        _safe_tool(concept_graph.suggest_concept_merges),
        _safe_tool(record_tutor_answer),
        _safe_tool(get_tutor_progress),
    ],
)
