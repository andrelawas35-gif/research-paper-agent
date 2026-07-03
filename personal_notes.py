"""Local personal-note storage for the research paper agent.

This module owns durable JSONL records, Markdown mirrors, simple lexical
search, soft-delete support, and conservative on-save extraction. Graph
integration comes later.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


# ── ADR 0056: Record schemas ─────────────────────────────────────────


class NoteCard(TypedDict, total=False):
    card_id: str
    text: str
    concepts: list[str]
    rejected: bool
    confidence: float


class PersonalNote(TypedDict, total=False):
    schema_version: int
    note_id: str
    title: str
    text: str
    created_at: str
    updated_at: str
    deleted_at: str | None
    user_tags: list[str]
    suggested_tags: list[str]
    cards: list[NoteCard]
    concepts: list[str]
    candidate_signals: list[dict[str, Any]]
    markdown_path: str | None
    versions: list[dict[str, Any]]


APP_DIR = Path(__file__).resolve().parent
USER_MODEL_DIR = APP_DIR / "user_model"
PERSONAL_NOTES_PATH = USER_MODEL_DIR / "personal_notes.jsonl"
MARKDOWN_NOTES_DIR_NAME = "notes"

STOPWORDS = {
    "about",
    "after",
    "again",
    "agent",
    "also",
    "and",
    "are",
    "because",
    "before",
    "but",
    "can",
    "could",
    "does",
    "for",
    "from",
    "general",
    "have",
    "into",
    "its",
    "like",
    "make",
    "more",
    "must",
    "need",
    "needs",
    "note",
    "notes",
    "only",
    "personal",
    "prompt",
    "prompts",
    "random",
    "should",
    "that",
    "the",
    "their",
    "this",
    "through",
    "user",
    "users",
    "using",
    "when",
    "where",
    "with",
    "would",
}

CARD_SIGNAL_PATTERN = re.compile(
    r"\b(should|need|needs|must|prefer|means|because|separate|treat|use|keep|"
    r"avoid|turn|connect|capture|store|remember|learn|rank|derive|confirm)\b",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _note_store_path(path: Path | None = None) -> Path:
    return path or PERSONAL_NOTES_PATH


def _markdown_notes_dir(path: Path | None = None) -> Path:
    return _note_store_path(path).parent / MARKDOWN_NOTES_DIR_NAME


def _split_csv(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = value.split(",")
    seen: set[str] = set()
    items = []
    for item in raw_items:
        normalized = str(item).strip()
        key = normalized.lower()
        if normalized and key not in seen:
            items.append(normalized)
            seen.add(key)
    return items


def _append_unique(items: list[str], value: str) -> None:
    normalized = re.sub(r"\s+", " ", value).strip(" .,:;").strip()
    if not normalized:
        return
    if normalized.lower() in {item.lower() for item in items}:
        return
    items.append(normalized)


def _derive_title(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not first_line:
        return "Untitled note"
    return first_line[:80]


def _next_note_id(notes: list[dict[str, Any]], now: str) -> str:
    date_part = now[:10].replace("-", "")
    prefix = f"note_{date_part}_"
    max_seen = 0
    for note in notes:
        note_id = str(note.get("note_id", ""))
        if not note_id.startswith(prefix):
            continue
        suffix = note_id.removeprefix(prefix)
        if suffix.isdigit():
            max_seen = max(max_seen, int(suffix))
    return f"{prefix}{max_seen + 1:03d}"


def _slugify(value: str, fallback: str = "note") -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        slug = fallback
    return slug[:64].strip("-") or fallback


def _markdown_path_for_note(note: dict[str, Any], path: Path | None = None) -> tuple[str, Path]:
    slug = _slugify(str(note.get("title", "")), fallback=str(note.get("note_id", "note")))
    file_name = f"{note['note_id']}-{slug}.md"
    relative_path = f"{MARKDOWN_NOTES_DIR_NAME}/{file_name}"
    return relative_path, _markdown_notes_dir(path) / file_name


def _yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "\n" + "\n".join(f"  - {json.dumps(value)}" for value in values)


def _frontmatter_value(value: Any) -> str:
    if value is None:
        return "null"
    return json.dumps(value)


def _format_markdown_mirror(note: dict[str, Any]) -> str:
    cards = [
        card for card in note.get("cards", [])
        if not card.get("rejected")
    ]
    lines = [
        "---",
        f"schema_version: {note.get('schema_version', 1)}",
        f"note_id: {_frontmatter_value(note.get('note_id'))}",
        f"title: {_frontmatter_value(note.get('title'))}",
        f"created_at: {_frontmatter_value(note.get('created_at'))}",
        f"updated_at: {_frontmatter_value(note.get('updated_at'))}",
        f"deleted_at: {_frontmatter_value(note.get('deleted_at'))}",
        f"user_tags: {_yaml_list(note.get('user_tags', []))}",
        f"suggested_tags: {_yaml_list(note.get('suggested_tags', []))}",
        f"concepts: {_yaml_list(note.get('concepts', []))}",
        "---",
        "",
        f"# {note.get('title', 'Untitled note')}",
        "",
        "## Original Note",
        "",
        str(note.get("text", "")).strip(),
        "",
        "## Note Cards",
        "",
    ]

    if cards:
        for card in cards:
            lines.append(f"- [{card.get('card_id')}] {card.get('text', '')}")
            concepts = card.get("concepts", [])
            if concepts:
                lines.append(f"  - Concepts: {', '.join(concepts)}")
    else:
        lines.append("_No reusable cards extracted._")

    lines.extend(["", "## Concepts", ""])
    concepts = note.get("concepts", [])
    if concepts:
        lines.extend(f"- {concept}" for concept in concepts)
    else:
        lines.append("_No concepts extracted._")

    lines.extend(["", "## Related Links", "", "_Graph-derived links will appear in a later slice._", ""])
    return "\n".join(lines)


def _write_markdown_mirror(note: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    relative_path, markdown_path = _markdown_path_for_note(note, path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_format_markdown_mirror(note), encoding="utf-8")
    note["markdown_path"] = relative_path
    return {
        "markdown_path": relative_path,
        "markdown_full_path": str(markdown_path),
    }


def _sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", compact)
        if sentence.strip()
    ]


def _tokens(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text.lower())
        if word not in STOPWORDS and not word.isdigit()
    ]


def _suggest_tags(text: str, user_tags: list[str], limit: int = 6) -> list[str]:
    user_tag_keys = {tag.lower() for tag in user_tags}
    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for index, token in enumerate(_tokens(text)):
        if token in user_tag_keys or len(token) > 28:
            continue
        counts[token] = counts.get(token, 0) + 1
        first_seen.setdefault(token, index)

    ranked = sorted(counts.items(), key=lambda item: (-item[1], first_seen[item[0]], item[0]))
    return [token for token, count in ranked[:limit] if count >= 1]


def _phrase_candidates(text: str) -> list[str]:
    tokens = _tokens(text)
    candidates: list[str] = []
    for size in (3, 2):
        for index in range(0, max(0, len(tokens) - size + 1)):
            phrase_tokens = tokens[index:index + size]
            if len(set(phrase_tokens)) != len(phrase_tokens):
                continue
            phrase = " ".join(phrase_tokens)
            if len(phrase) < 8 or len(phrase) > 60:
                continue
            _append_unique(candidates, phrase)
    return candidates


def _extract_concepts(text: str, explicit_concepts: list[str], limit: int = 10) -> list[str]:
    concepts: list[str] = []
    for concept in explicit_concepts:
        _append_unique(concepts, concept)

    for phrase in _phrase_candidates(text):
        if len(concepts) >= limit:
            break
        _append_unique(concepts, phrase)

    if len(concepts) < limit:
        for token in _tokens(text):
            if len(concepts) >= limit:
                break
            _append_unique(concepts, token)

    return concepts[:limit]


def _concepts_for_sentence(sentence: str, concepts: list[str], limit: int = 4) -> list[str]:
    sentence_lower = sentence.lower()
    matched = [
        concept
        for concept in concepts
        if concept.lower() in sentence_lower
    ]
    if matched:
        return matched[:limit]

    sentence_tokens = set(_tokens(sentence))
    fallback = [
        concept
        for concept in concepts
        if sentence_tokens & set(_tokens(concept))
    ]
    return fallback[:limit]


def _extract_cards(text: str, concepts: list[str], limit: int = 5) -> list[dict[str, Any]]:
    """Extract 1–5 high-confidence reusable Note Cards from note text.

    Uses the DeepSeek API for extraction (ADR 0033) with a fallback to
    keyword-based extraction when the API is unavailable or returns no cards.
    """
    if not text.strip():
        return []

    # ── LLM-mediated extraction (primary) ──────────────────────────
    try:
        import os
        from openai import OpenAI

        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        prompt = (
            "Extract 1–5 reusable note cards from this text. Each card should be "
            "a self-contained insight, rule, question, or decision the user can "
            "revisit later. Return ONLY valid JSON with this format:\n\n"
            '{"cards": [{"text": "...", "confidence": 0.0-1.0}]}\n\n'
            f"Concepts mentioned in the note: {', '.join(concepts[:8])}\n\n"
            f"Text:\n{text[:1500]}"
        )
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.2,
        )
        raw = response.choices[0].message.content or "{}"
        # Extract JSON from the response.
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            llm_cards = data.get("cards", [])
            if llm_cards:
                cards = []
                for idx, c in enumerate(llm_cards[:limit]):
                    card_text = str(c.get("text", "")).strip()
                    if not card_text or len(card_text) < 15:
                        continue
                    confidence = float(c.get("confidence", 0.7))
                    if confidence < 0.4:
                        continue
                    cards.append({
                        "card_id": f"card_{idx + 1:03d}",
                        "text": card_text[:400],
                        "concepts": _concepts_for_sentence(card_text, concepts),
                        "rejected": False,
                        "confidence": round(confidence, 2),
                    })
                if cards:
                    return cards
    except Exception:
        pass  # Fall through to keyword-based extraction.

    # ── Keyword-based extraction (fallback) ─────────────────────────
    cards = []
    seen: set[str] = set()
    candidates = []
    for sentence in _sentences(text):
        if not (30 <= len(sentence) <= 320):
            continue
        if not CARD_SIGNAL_PATTERN.search(sentence):
            continue
        candidates.append(sentence)

    for sentence in candidates:
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        cards.append(
            {
                "card_id": f"card_{len(cards) + 1:03d}",
                "text": sentence,
                "concepts": _concepts_for_sentence(sentence, concepts),
                "rejected": False,
            }
        )
        if len(cards) >= limit:
            break
    return cards


def _validate_note(record: dict[str, Any]) -> bool:
    """Return True if the record has all required PersonalNote fields with correct types."""
    required_str = ["note_id", "title", "text", "created_at", "updated_at"]
    for key in required_str:
        if not isinstance(record.get(key), str):
            logger.warning("PersonalNote missing or invalid field: %s", key)
            return False
    if not isinstance(record.get("user_tags"), list):
        return False
    if not isinstance(record.get("concepts"), list):
        return False
    if not isinstance(record.get("cards"), list):
        return False
    return True


def load_notes(path: Path | None = None, include_deleted: bool = False) -> list[dict[str, Any]]:
    """Load personal notes from JSONL, skipping unreadable or invalid lines."""
    notes_path = _note_store_path(path)
    if not notes_path.exists():
        return []

    notes = []
    with notes_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                note = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping unparseable line in %s", notes_path)
                continue
            if not _validate_note(note):
                logger.warning("Skipping invalid note record: %s", note.get("note_id", "unknown"))
                continue
            if include_deleted or not note.get("deleted_at"):
                notes.append(note)
    return notes


def _write_notes(notes: list[dict[str, Any]], path: Path | None = None) -> None:
    notes_path = _note_store_path(path)
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    with notes_path.open("w", encoding="utf-8") as handle:
        for note in notes:
            handle.write(json.dumps(note, ensure_ascii=False) + "\n")


def save_note(
    text: str,
    title: str = "",
    user_tags: str | list[str] | None = None,
    concepts: str | list[str] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Create a personal note record in the local JSONL store."""
    cleaned_text = text.strip()
    if not cleaned_text:
        return {"status": "error", "message": "note text is required"}

    notes = load_notes(path, include_deleted=True)
    now = _now_iso()
    parsed_user_tags = _split_csv(user_tags)
    parsed_concepts = _split_csv(concepts)
    extracted_concepts = _extract_concepts(cleaned_text, parsed_concepts)
    note = {
        "schema_version": 1,
        "note_id": _next_note_id(notes, now),
        "title": title.strip() or _derive_title(cleaned_text),
        "text": cleaned_text,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "user_tags": parsed_user_tags,
        "suggested_tags": _suggest_tags(cleaned_text, parsed_user_tags),
        "cards": _extract_cards(cleaned_text, extracted_concepts),
        "concepts": extracted_concepts,
        "candidate_signals": [],
        "markdown_path": None,
        "versions": [],
    }
    mirror = _write_markdown_mirror(note, path)
    notes.append(note)
    _write_notes(notes, path)
    return {
        "status": "ok",
        "note_id": note["note_id"],
        "notes_path": str(_note_store_path(path)),
        **mirror,
        "note": note,
    }


def list_notes(path: Path | None = None) -> dict[str, Any]:
    """List non-deleted notes with summary fields."""
    notes = load_notes(path)
    return {
        "notes_path": str(_note_store_path(path)),
        "count": len(notes),
        "notes": [
            {
                "note_id": note.get("note_id"),
                "title": note.get("title"),
                "user_tags": note.get("user_tags", []),
                "suggested_tags": note.get("suggested_tags", []),
                "concepts": note.get("concepts", []),
                "created_at": note.get("created_at"),
                "updated_at": note.get("updated_at"),
            }
            for note in notes
        ],
    }


def get_note(note_id: str, path: Path | None = None, include_deleted: bool = False) -> dict[str, Any]:
    """Return one full personal note record by id."""
    for note in load_notes(path, include_deleted=include_deleted):
        if note.get("note_id") == note_id:
            return {"status": "ok", "notes_path": str(_note_store_path(path)), "note": note}
    return {"status": "error", "message": f"Note not found: {note_id}"}


def _search_blob(note: dict[str, Any]) -> str:
    card_text = " ".join(str(card.get("text", "")) for card in note.get("cards", []))
    parts = [
        note.get("title", ""),
        note.get("text", ""),
        " ".join(note.get("user_tags", [])),
        " ".join(note.get("suggested_tags", [])),
        " ".join(note.get("concepts", [])),
        card_text,
    ]
    return "\n".join(str(part) for part in parts).lower()


def _query_terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-]{1,}", query.lower())]


def search_notes(query: str, path: Path | None = None, max_notes: int = 10) -> dict[str, Any]:
    """Search personal notes with simple lexical scoring."""
    terms = _query_terms(query)
    if not terms:
        return {"query": query, "matches": []}

    matches = []
    for note in load_notes(path):
        blob = _search_blob(note)
        score = sum(blob.count(term) for term in terms)
        phrase_bonus = 3 if query.strip().lower() in blob else 0
        score += phrase_bonus
        if score <= 0:
            continue
        matches.append(
            {
                "note_id": note.get("note_id"),
                "title": note.get("title"),
                "score": score,
                "user_tags": note.get("user_tags", []),
                "concepts": note.get("concepts", []),
                "updated_at": note.get("updated_at"),
                "text_preview": note.get("text", "")[:280],
            }
        )

    matches.sort(key=lambda item: (item["score"], item.get("updated_at") or ""), reverse=True)
    limit = max(1, min(max_notes, 25))
    return {"query": query, "matches": matches[:limit]}


def soft_delete_note(note_id: str, path: Path | None = None) -> dict[str, Any]:
    """Mark a note deleted without purging it from disk."""
    notes = load_notes(path, include_deleted=True)
    now = _now_iso()
    for note in notes:
        if note.get("note_id") != note_id:
            continue
        if note.get("deleted_at"):
            return {"status": "ok", "changed": False, "note": note}
        note["deleted_at"] = now
        note["updated_at"] = now
        mirror = _write_markdown_mirror(note, path)
        _write_notes(notes, path)
        return {"status": "ok", "changed": True, **mirror, "note": note}
    return {"status": "error", "message": f"Note not found: {note_id}"}


# ---------------------------------------------------------------------------
# ADR 0028 + 0035: Note editing, versioning, and corrections
# ---------------------------------------------------------------------------


def edit_personal_note(
    note_id: str,
    text: str = "",
    title: str = "",
    user_tags: str | list[str] | None = None,
    concepts: str | list[str] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Edit a personal note, preserving the previous state as a version entry.

    Only provided fields are updated; omitted fields keep their current
    values.  Each edit appends a ``versions`` entry with the previous
    title, text, tags, and concepts so backlinks and cards remain traceable.
    """
    notes = load_notes(path, include_deleted=True)
    now = _now_iso()

    for note in notes:
        if note.get("note_id") != note_id:
            continue

        # Snapshot current state before mutation.
        version_entry = {
            "versioned_at": now,
            "previous_title": note.get("title"),
            "previous_text": note.get("text"),
            "previous_user_tags": list(note.get("user_tags", [])),
            "previous_concepts": list(note.get("concepts", [])),
        }
        note.setdefault("versions", []).append(version_entry)

        # Apply updates.
        if text.strip():
            note["text"] = text.strip()
        if title.strip():
            note["title"] = title.strip()
        if user_tags is not None:
            note["user_tags"] = _split_csv(user_tags)
        if concepts is not None:
            parsed = _split_csv(concepts)
            note["concepts"] = _extract_concepts(note.get("text", ""), parsed)

        note["updated_at"] = now
        note["suggested_tags"] = _suggest_tags(
            note.get("text", ""), note.get("user_tags", [])
        )
        # Re-extract cards from updated text.
        note["cards"] = _extract_cards(
            note.get("text", ""), note.get("concepts", [])
        )

        mirror = _write_markdown_mirror(note, path)
        _write_notes(notes, path)
        return {
            "status": "ok",
            "note_id": note_id,
            "version_count": len(note["versions"]),
            **mirror,
            "note": note,
        }

    return {"status": "error", "message": f"Note not found: {note_id}"}


def reject_note_card(
    note_id: str,
    card_index: int,
    path: Path | None = None,
) -> dict[str, Any]:
    """Reject an extracted Note Card by index (0-based).

    The card is marked ``rejected: true`` and excluded from future
    search indexing and Markdown mirror rendering.  The underlying
    note text is unchanged.
    """
    notes = load_notes(path, include_deleted=True)
    for note in notes:
        if note.get("note_id") != note_id:
            continue
        cards = note.get("cards", [])
        if card_index < 0 or card_index >= len(cards):
            return {
                "status": "error",
                "message": f"Card index {card_index} out of range (0–{len(cards) - 1})",
            }
        cards[card_index]["rejected"] = True
        note["updated_at"] = _now_iso()
        _write_markdown_mirror(note, path)
        _write_notes(notes, path)
        return {
            "status": "ok",
            "note_id": note_id,
            "rejected_card_index": card_index,
            "card_text": cards[card_index].get("text", "")[:200],
        }
    return {"status": "error", "message": f"Note not found: {note_id}"}


def reject_note_concept(
    note_id: str,
    concept_name: str,
    path: Path | None = None,
) -> dict[str, Any]:
    """Reject a linked Concept from a personal note.

    The concept is removed from the note's ``concepts`` list and from
    any cards that reference it.  The concept-graph edge is *not*
    modified — use ``concept_graph.reject_concept`` separately to
    suppress graph-level ranking.
    """
    notes = load_notes(path, include_deleted=True)
    for note in notes:
        if note.get("note_id") != note_id:
            continue
        concept_key = concept_name.strip().lower()
        before = len(note.get("concepts", []))
        note["concepts"] = [
            c for c in note.get("concepts", [])
            if c.lower() != concept_key
        ]
        # Also scrub the concept from any cards.
        for card in note.get("cards", []):
            card["concepts"] = [
                c for c in card.get("concepts", [])
                if c.lower() != concept_key
            ]
        removed = before - len(note["concepts"])
        note["updated_at"] = _now_iso()
        _write_markdown_mirror(note, path)
        _write_notes(notes, path)
        return {
            "status": "ok",
            "note_id": note_id,
            "removed_concept": concept_name,
            "concepts_removed": removed,
        }
    return {"status": "error", "message": f"Note not found: {note_id}"}


# ---------------------------------------------------------------------------
# ADR 0031 + 0032: Markdown mirror public API + import
# ---------------------------------------------------------------------------


def render_note_markdown(note_id: str, path: Path | None = None) -> dict[str, Any]:
    """Return the full Markdown mirror for a note as a string.

    Regenerates the mirror from the canonical JSONL record, ensuring
    it reflects the latest edits, card rejections, and concept changes.
    """
    result = get_note(note_id, path=path, include_deleted=True)
    if result.get("status") != "ok":
        return result
    note = result["note"]
    markdown_text = _format_markdown_mirror(note)
    return {
        "status": "ok",
        "note_id": note_id,
        "markdown": markdown_text,
        "title": note.get("title"),
    }


def import_markdown_notes(path: Path | None = None) -> dict[str, Any]:
    """Sync Markdown mirrors back into the canonical JSONL store.

    Reads every ``.md`` file in the ``notes/`` directory, extracts
    frontmatter fields, and updates the corresponding JSONL record.
    This is an explicit, user-invoked action — it never runs
    automatically during unrelated operations (ADR 0032).
    """
    markdown_dir = _markdown_notes_dir(path)
    if not markdown_dir.exists():
        return {"status": "ok", "imported": 0, "message": "No notes/ directory found."}

    notes = load_notes(path, include_deleted=True)
    note_index: dict[str, int] = {}
    for idx, note in enumerate(notes):
        note_index[note.get("note_id", "")] = idx

    imported = 0
    for md_file in sorted(markdown_dir.glob("*.md")):
        raw = md_file.read_text(encoding="utf-8", errors="ignore")
        # Extract YAML frontmatter between --- markers.
        fm_match = re.match(r"^---\s*\n(.*?)\n---", raw, re.DOTALL)
        if not fm_match:
            continue
        note_id = ""
        title = ""
        for line in fm_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("note_id:"):
                note_id = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip("\"'")

        if not note_id or note_id not in note_index:
            continue

        idx = note_index[note_id]
        note = notes[idx]

        # Extract body text after frontmatter and strip section headers.
        body = raw[fm_match.end():]
        # Remove markdown headers and metadata sections — keep only prose.
        body_clean = re.sub(r"^#.*$", "", body, flags=re.MULTILINE)
        body_clean = re.sub(r"^##.*$", "", body_clean, flags=re.MULTILINE)
        body_clean = body_clean.strip()

        if body_clean and body_clean != note.get("text", "").strip():
            # Version the current state before importing.
            version_entry = {
                "versioned_at": _now_iso(),
                "previous_title": note.get("title"),
                "previous_text": note.get("text"),
                "previous_user_tags": list(note.get("user_tags", [])),
                "previous_concepts": list(note.get("concepts", [])),
                "source": f"markdown_import:{md_file.name}",
            }
            note.setdefault("versions", []).append(version_entry)
            note["text"] = body_clean
            if title.strip():
                note["title"] = title.strip()
            note["updated_at"] = _now_iso()
            note["suggested_tags"] = _suggest_tags(body_clean, note.get("user_tags", []))
            imported += 1

    if imported:
        _write_notes(notes, path)

    return {"status": "ok", "imported": imported, "notes_path": str(_note_store_path(path))}


# ---------------------------------------------------------------------------
# ADR 0027: Concept-derived backlinks
# ---------------------------------------------------------------------------


def get_backlinks(note_id: str, path: Path | None = None) -> dict[str, Any]:
    """Return notes, concepts, and interests that share concepts with this note.

    Backlinks are derived from the Concept Graph — two notes are linked
    when they share at least one Concept.  This is an agent-native graph
    view, not a manual wiki-link system (ADR 0027).
    """
    result = get_note(note_id, path=path)
    if result.get("status") != "ok":
        return result
    source_concepts = {c.lower() for c in result["note"].get("concepts", [])}
    if not source_concepts:
        return {"status": "ok", "note_id": note_id, "backlinks": [], "concepts": []}

    all_notes = load_notes(path)
    backlinks: list[dict[str, Any]] = []
    for note in all_notes:
        if note.get("note_id") == note_id:
            continue
        target_concepts = {c.lower() for c in note.get("concepts", [])}
        shared = source_concepts & target_concepts
        if shared:
            backlinks.append({
                "note_id": note.get("note_id"),
                "title": note.get("title"),
                "shared_concepts": sorted(shared),
                "overlap_count": len(shared),
            })

    backlinks.sort(key=lambda b: b["overlap_count"], reverse=True)
    return {
        "status": "ok",
        "note_id": note_id,
        "concepts": sorted(source_concepts),
        "backlinks": backlinks[:20],
    }
