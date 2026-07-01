"""Local personal-note storage for the research paper agent.

The first slice is intentionally small: durable JSONL records, simple lexical
search, and soft-delete support. LLM extraction, Markdown mirrors, and graph
integration come later.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
USER_MODEL_DIR = APP_DIR / "user_model"
PERSONAL_NOTES_PATH = USER_MODEL_DIR / "personal_notes.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _note_store_path(path: Path | None = None) -> Path:
    return path or PERSONAL_NOTES_PATH


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


def load_notes(path: Path | None = None, include_deleted: bool = False) -> list[dict[str, Any]]:
    """Load personal notes from JSONL, skipping unreadable lines."""
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
    note = {
        "schema_version": 1,
        "note_id": _next_note_id(notes, now),
        "title": title.strip() or _derive_title(cleaned_text),
        "text": cleaned_text,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "user_tags": _split_csv(user_tags),
        "suggested_tags": [],
        "cards": [],
        "concepts": _split_csv(concepts),
        "candidate_signals": [],
        "markdown_path": None,
        "versions": [],
    }
    notes.append(note)
    _write_notes(notes, path)
    return {
        "status": "ok",
        "note_id": note["note_id"],
        "notes_path": str(_note_store_path(path)),
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
        _write_notes(notes, path)
        return {"status": "ok", "changed": True, "note": note}
    return {"status": "error", "message": f"Note not found: {note_id}"}
