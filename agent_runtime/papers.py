"""Paper ingestion, record management, and paper tools.

Extracted from agent.py per Python Module Architecture Plan Phase 3.
Owns everything related to paper files: ingestion, metadata extraction,
passage generation, evidence scope filtering, record caching, briefs,
comparisons, study guides, and file management (rename/delete/organise).

Uses lazy imports from ``agent_runtime.retrieval`` for text utilities
to avoid a circular dependency (retrieval imports papers for records).
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .paths import KNOWLEDGE_DIR, PAPERS_DIR

logger = logging.getLogger(__name__)


# ── Paper ingestion: PDF / text readers ──────────────────────────────


def _read_pdf_pages(path: Path) -> list[dict[str, Any]]:
    """Extract text pages from a PDF, with OCR fallback for scanned docs."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF support requires pypdf. Install project dependencies."
        ) from exc

    reader = PdfReader(str(path))
    pages: list[dict[str, Any]] = []
    ocr_attempted = False
    _ocr_available = False

    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        if not text.strip():
            if not ocr_attempted:
                try:
                    import fitz
                    import pytesseract
                    from PIL import Image  # noqa: F401

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
                    page_obj = doc.load_page(index - 1)
                    pix = page_obj.get_pixmap(dpi=300)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    text = pytesseract.image_to_string(img)
                    doc.close()
                except Exception:
                    pass

            if not text.strip():
                continue

        pages.append({"page": index, "text": text})

    return pages


def _read_paper_pages(path: Path) -> list[dict[str, Any]]:
    """Read a paper file (txt, md, or pdf) into pages."""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return [{"page": None, "text": text}]
    if suffix == ".pdf":
        return _read_pdf_pages(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


# ── Metadata + passage extraction ────────────────────────────────────


def _extract_metadata(source: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract title, year, DOI, arXiv ID from paper text."""
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
    """Split paper text into overlapping passages for retrieval."""
    from .retrieval import citation, keywords, sentences  # noqa: PLC0415

    passages: list[dict[str, Any]] = []
    counter = 1
    for page in pages:
        sentence_buffer: list[str] = []
        for sentence in sentences(page["text"]):
            sentence_buffer.append(sentence)
            joined = " ".join(sentence_buffer)
            if len(joined) >= 450 or len(sentence_buffer) >= 3:
                passage_id = f"P{counter:04d}"
                passages.append({
                    "id": passage_id, "source": source, "page": page["page"],
                    "citation": citation(source, page["page"], passage_id),
                    "text": joined[:1400], "keywords": keywords(joined, 12),
                })
                sentence_buffer = []
                counter += 1
        if sentence_buffer:
            passage_id = f"P{counter:04d}"
            passages.append({
                "id": passage_id, "source": source, "page": page["page"],
                "citation": citation(source, page["page"], passage_id),
                "text": " ".join(sentence_buffer)[:1400],
                "keywords": keywords(" ".join(sentence_buffer), 12),
            })
            counter += 1
    return passages[:240]


def _extract_candidate_notes(
    text: str, passages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bucket passages into sections and extract top concepts."""
    from .retrieval import SECTION_PATTERNS, keywords  # noqa: PLC0415

    buckets: dict[str, list[dict[str, str]]] = {
        "abstract": [], "methods": [], "findings": [],
        "limitations": [], "open_questions": [],
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
    for kw in keywords(text, 40):
        supporting = next(
            (p for p in passages if kw in p["keywords"] or kw in p["text"].lower()),
            None,
        )
        concepts.append({
            "name": kw,
            "citation": supporting["citation"] if supporting else None,
        })

    return {
        "concepts": concepts[:30],
        "methods": buckets["methods"],
        "findings": buckets["findings"],
        "limitations": buckets["limitations"],
        "open_questions": buckets["open_questions"],
    }


# ── Paper record paths + evidence scoping ────────────────────────────


def _paper_record_path(paper_path: Path) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", paper_path.stem)
    return KNOWLEDGE_DIR / f"{safe_name}.json"


def _normalize_evidence_scopes(
    value: str | list[str] | tuple[str, ...] | None = None,
) -> list[str]:
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
    return [r for r in records if scopes.intersection(_record_evidence_scopes(r))]


# ── Record loading + caching ─────────────────────────────────────────


def _load_records() -> list[dict[str, Any]]:
    """Load ingested paper records, cached in memory after first read."""
    cache = getattr(_load_records, "_cache", None)
    if cache is not None:
        return cache
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    _load_records._cache = records  # type: ignore[attr-defined]
    return records


def _all_passages(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [p for r in records for p in r.get("passages", [])]


# ── Dependency inference ─────────────────────────────────────────────


def _infer_dependencies(
    concepts: list[dict[str, Any]], source_paper: str,
) -> int:
    """Ask the LLM to infer prerequisite hints among extracted concepts."""
    from openai import OpenAI  # noqa: PLC0415

    concept_names = [c.get("name", "") for c in concepts if c.get("name")]
    if len(concept_names) < 2:
        return 0

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
        return 0

    from research_paper_agent import concept_graph  # noqa: PLC0415

    created = 0
    for line in text.strip().splitlines():
        line = line.strip()
        if "←" not in line and "<-" not in line:
            continue
        parts = line.replace("<-", "←").split("←")
        if len(parts) != 2:
            continue
        concept = parts[0].strip().lower()
        prerequisite = parts[1].strip().lower()
        if not concept or not prerequisite or concept == prerequisite:
            continue
        known = {c.get("name", "").strip().lower() for c in concepts}
        if concept not in known or prerequisite not in known:
            continue
        try:
            concept_graph.link_prerequisite(concept, prerequisite, source_paper)
            created += 1
        except Exception:
            continue
    return created


def _try_annotate_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Best-effort concept-graph annotation; returns brief unchanged on failure."""
    try:
        from research_paper_agent import concept_graph  # noqa: PLC0415
        from research_paper_agent.agent import _load_user_profile  # noqa: PLC0415

        profile = _load_user_profile()
        user_interests = [item.get("name", "") for item in profile.get("interests", [])]
        return concept_graph.annotate(brief, user_interests)
    except Exception:
        return brief


# ======================================================================
# Public paper tools
# ======================================================================


def list_papers() -> dict[str, Any]:
    """List supported papers available for ingestion, scanning subdirectories recursively."""
    PAPERS_DIR.mkdir(exist_ok=True)
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
    """Rename a paper file and update all dependent records atomically."""
    from research_paper_agent import concept_graph  # noqa: PLC0415

    old_path = (PAPERS_DIR / old_name).resolve()
    if PAPERS_DIR.resolve() not in old_path.parents or not old_path.is_file():
        return {"status": "error", "message": f"Source file not found in papers/: {old_name}"}

    new_path = (PAPERS_DIR / new_name).resolve()
    if PAPERS_DIR.resolve() not in new_path.parents:
        return {"status": "error", "message": f"Target path must stay within papers/: {new_name}"}

    if not new_path.parent.exists():
        new_path.parent.mkdir(parents=True, exist_ok=True)
    if new_path.exists():
        return {"status": "error", "message": f"Target file already exists: {new_name}"}

    try:
        old_path.rename(new_path)
    except OSError as exc:
        return {"status": "error", "message": f"File rename failed: {exc}"}

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
            try:
                new_path.rename(old_path)
            except OSError:
                pass
            return {
                "status": "error",
                "message": f"KB record migration failed (file rename rolled back): {exc}",
            }

    graph_result = {"edge_updates": 0, "dependency_updates": 0}
    try:
        graph_result = concept_graph.rename_source_paper(old_name, new_name)
    except Exception as exc:
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

    _load_records._cache = None  # type: ignore[attr-defined]
    return {
        "status": "ok", "old_name": old_name, "new_name": new_name,
        "kb_record_migrated": kb_renamed,
        "concept_graph_edges_updated": graph_result["edge_updates"],
        "concept_graph_dependencies_updated": graph_result["dependency_updates"],
    }


def delete_paper(file_name: str, dry_run: bool = True) -> dict[str, Any]:
    """Delete a paper file and its knowledge-base record."""
    from research_paper_agent import concept_graph  # noqa: PLC0415

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
        "dry_run": dry_run, "file": file_name, "file_size": file_size_str,
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

    errors: list[str] = []
    try:
        path.unlink()
    except OSError as exc:
        errors.append(f"file delete: {exc}")
    if kb_exists:
        try:
            kb_path.unlink()
        except OSError as exc:
            errors.append(f"KB record delete: {exc}")

    graph_result = {"edge_removals": 0, "dependency_removals": 0}
    try:
        graph_result = concept_graph.remove_source_paper(file_name)
    except Exception as exc:
        errors.append(f"concept graph cleanup: {exc}")

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
        "file_deleted": True, "kb_record_deleted": kb_exists,
        "graph_edge_removals": graph_result["edge_removals"],
        "graph_dependency_removals": graph_result["dependency_removals"],
    }


def organize_papers(mapping: dict[str, str]) -> dict[str, Any]:
    """Rename and/or move multiple papers according to a mapping."""
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
        "total": len(mapping), "succeeded": succeeded, "failed": failed,
        "results": results,
    }


def ingest_paper(file_name: str, evidence_scope: str = "") -> dict[str, Any]:
    """Read one paper from papers/ and save metadata, concepts, notes, and cited passages."""
    from .retrieval import keywords  # noqa: PLC0415

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
    record: dict[str, Any] = {
        "schema_version": 2,
        "metadata": _extract_metadata(path.name, pages),
        "source": path.name,
        "characters": len(text),
        "page_count": len(pages),
        "keywords": keywords(text),
        "notes": notes,
        "passages": passages,
    }
    if scopes:
        record["evidence_scope"] = scopes
    output_path = _paper_record_path(path)
    output_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    _load_records._cache = None  # type: ignore[attr-defined]

    # Concept graph linking (best-effort).
    try:
        from research_paper_agent import concept_graph  # noqa: PLC0415
        from research_paper_agent.agent import _load_user_profile  # noqa: PLC0415

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
        pass

    prereq_count = 0
    try:
        prereq_count = _infer_dependencies(notes["concepts"], path.name)
    except Exception:
        pass

    return {
        "status": "ok", "source": path.name,
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
    """List extracted concepts grouped by source paper."""
    records = _load_records()
    return {
        "sources": [
            {
                "source": r["source"],
                "title": r.get("metadata", {}).get("title", r["source"]),
                "concepts": r.get("notes", {}).get("concepts", []),
                "keywords": r.get("keywords", []),
            }
            for r in records
        ]
    }


def paper_brief(source: str = "") -> dict[str, Any]:
    """Return a compact source-grounded brief for one paper or all papers."""
    records = _load_records()
    if source:
        records = [
            r for r in records
            if source.lower() in r["source"].lower()
            or source.lower() in r.get("metadata", {}).get("title", "").lower()
        ]
    return {
        "briefs": [
            _try_annotate_brief({
                "source": r["source"],
                "metadata": r.get("metadata", {}),
                "top_concepts": r.get("notes", {}).get("concepts", [])[:12],
                "methods": r.get("notes", {}).get("methods", [])[:4],
                "findings": r.get("notes", {}).get("findings", [])[:4],
                "limitations": r.get("notes", {}).get("limitations", [])[:4],
                "open_questions": r.get("notes", {}).get("open_questions", [])[:4],
            })
            for r in records
        ]
    }


def compare_papers(topic: str = "") -> dict[str, Any]:
    """Compare ingested papers by concepts, methods, findings, limitations."""
    from .retrieval import search_evidence  # noqa: PLC0415

    records = _load_records()
    concept_sources: dict[str, set[str]] = defaultdict(set)
    for r in records:
        for concept in r.get("notes", {}).get("concepts", []):
            concept_sources[concept["name"]].add(r["source"])

    shared_concepts = [
        {"concept": c, "sources": sorted(s)}
        for c, s in concept_sources.items() if len(s) > 1
    ][:20]

    comparison = []
    for r in records:
        notes = r.get("notes", {})
        entry: dict[str, Any] = {
            "source": r["source"],
            "title": r.get("metadata", {}).get("title", r["source"]),
            "concepts": notes.get("concepts", [])[:10],
            "methods": notes.get("methods", [])[:3],
            "findings": notes.get("findings", [])[:3],
            "limitations": notes.get("limitations", [])[:3],
        }
        if topic:
            topic_matches = search_evidence(f"{topic} {r['source']}", 5)["matches"]
            entry["topic_evidence"] = [
                m for m in topic_matches if m["source"] == r["source"]
            ][:3]
        comparison.append(entry)

    return {"topic": topic or None, "shared_concepts": shared_concepts, "papers": comparison}


def make_study_guide(source: str = "", question_count: int = 8) -> dict[str, Any]:
    """Create a citation-backed study guide with concepts and recall questions."""
    briefs = paper_brief(source)["briefs"]
    questions: list[dict[str, Any]] = []
    for brief in briefs:
        title = brief["metadata"].get("title", brief["source"])
        for concept in brief["top_concepts"][:max(1, question_count // max(1, len(briefs)))]:
            questions.append({
                "question": f"Explain how '{concept['name']}' matters in {title}.",
                "citation": concept.get("citation"),
                "source": brief["source"],
            })
        for limitation in brief["limitations"][:2]:
            questions.append({
                "question": f"What limitation or caveat does {title} raise?",
                "citation": limitation.get("citation"),
                "source": brief["source"],
            })

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for q in questions:
        key = q["question"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)
        if len(deduped) >= max(1, min(question_count, 20)):
            break

    return {"study_guides": briefs, "recall_questions": deduped}
