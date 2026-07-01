from __future__ import annotations

import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.adk.agents.llm_agent import Agent
from google.adk.labs.openai import OpenAILlm
from openai import AsyncOpenAI
from openai import OpenAI

from . import concept_graph


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
    PAPERS_DIR.mkdir(exist_ok=True)
    KNOWLEDGE_DIR.mkdir(exist_ok=True)
    USER_MODEL_DIR.mkdir(exist_ok=True)


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
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    }


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
        return json.loads(USER_PROFILE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        profile = _default_user_profile()
        profile["recovery_note"] = "profile.json was unreadable and defaults were restored."
        USER_PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        _load_user_profile._cache = profile  # type: ignore[attr-defined]
        return profile
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
    with CANDIDATE_SIGNALS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


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
    """List supported papers available for ingestion."""
    _ensure_dirs()
    files = sorted(
        path.name
        for path in PAPERS_DIR.iterdir()
        if path.suffix.lower() in {".txt", ".md", ".pdf"}
    )
    return {"papers_dir": str(PAPERS_DIR), "papers": files}


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


def ingest_paper(file_name: str) -> dict[str, Any]:
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
                if concept_name and concept_graph.token_overlap(interest_name, concept_name):
                    concept_graph.link(interest_name, concept_name, path.name, edge_type="ingest")
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


def search_evidence(query: str, max_passages: int = 8) -> dict[str, Any]:
    """Search ingested evidence passages with weighted lexical ranking and citations."""
    query_terms = _tokenize(query)
    if not query_terms:
        return {"query": query, "matches": []}

    records = _load_records()
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
    return {"query": query, "matches": matches[:max(1, min(max_passages, 20))]}


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


def self_improvement_audit() -> dict[str, Any]:
    """Review the user model and suggest how the agent should adapt next."""
    profile = _load_user_profile()
    interaction_count = 0
    if INTERACTION_LOG_PATH.exists():
        interaction_count = sum(1 for _ in INTERACTION_LOG_PATH.open("r", encoding="utf-8"))

    profile_gaps = []
    for bucket in ["interests", "style_preferences", "question_patterns", "grammar_and_quirks"]:
        if not profile.get(bucket):
            profile_gaps.append(f"No entries yet for {bucket}.")

    recommendations = [
        "Call get_user_profile before tailoring answers to the user.",
        "Call learn_from_user_message when the user expresses a new interest, correction, or recurring workflow.",
        "Call set_user_preference when the user gives explicit feedback about tone, format, or behavior.",
        "Use concrete commands for operational questions, but give fuller answers for research synthesis, recommendations, and personality-shaped guidance.",
    ]
    if interaction_count < 5:
        recommendations.append("Record more interactions before drawing strong conclusions about quirks.")

    return {
        "profile_path": str(USER_PROFILE_PATH),
        "interaction_log_path": str(INTERACTION_LOG_PATH),
        "interaction_count": interaction_count,
        "profile_gaps": profile_gaps,
        "recommendations": recommendations,
        "current_adaptation_rules": profile.get("adaptation_rules", []),
    }


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

    return {
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
    _load_tutor_progress._cache = progress  # type: ignore[attr-defined]
    return progress


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
            if interest_name and concept_graph.token_overlap(interest_name, concept):
                concept_graph.link(interest_name, concept, source or "tutor_session", edge_type="engaged")
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

    return {
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


root_agent = Agent(
    model=DeepSeekLlm(),
    name="research_paper_agent",
    description="Reads research papers, extracts concepts, compares papers, and answers grounded questions.",
    instruction=(
        "You are a careful research assistant for papers and a local personalized "
        "assistant for this user. Use tools before making claims about ingested papers. "
        "For factual answers, call search_evidence and cite the returned citation "
        "fields. Use paper_brief for summaries, compare_papers for cross-paper "
        "synthesis, and make_study_guide for learning workflows. Separate source-backed "
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
        "Support explicit modes when the user names them: Reader Mode means faithful "
        "source understanding; Grill Mode means one pointed adaptive question at a time; "
        "Builder Mode means turn research into agent/tool/workflow ideas; Taste Mode "
        "means judge skim/study/compare/discard; Artifact Mode means create confirmed "
        "durable outputs; Profile Mode means inspect or update the user model; "
        "Tutor Mode means teach paper concepts through an explain-then-quiz loop "
        "with adaptive curriculum. In Tutor Mode, use search_evidence to find a "
        "cited passage, explain the concept, ask one question via adaptive_grill, "
        "then call record_tutor_answer to grade the response and suggest the next "
        "concept. Alternate between drilling weak concepts and exploring high-interest "
        "ones; let the user steer at any point. "
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
        "persist across sessions and do not need to be re-ingested. Keep answers structured, "
        "grounded, adaptive, and appropriately detailed."
    ),
    tools=[
        _safe_tool(list_papers),
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
        _safe_tool(self_improvement_audit),
        _safe_tool(adaptive_grill),
        _safe_tool(respond_to_adaptive_grill),
        _safe_tool(concept_graph.get_concept_graph),
        _safe_tool(record_tutor_answer),
        _safe_tool(get_tutor_progress),
    ],
)
