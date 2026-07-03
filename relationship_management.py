"""Local relationship-management storage for the research paper agent.

This module owns append-only relationship events, derived person summaries,
simple lexical search, soft-delete support, and reconnection recommendations.
The first slice deliberately avoids external messaging and model extraction.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
USER_MODEL_DIR = APP_DIR / "user_model"
PEOPLE_PATH = USER_MODEL_DIR / "people.jsonl"

PROFESSIONAL_TYPES = {
    "collaborator",
    "mentor",
    "networking",
    "professional",
    "prospect",
}

SENSITIVE_PATTERN = re.compile(
    r"\b(health|sick|ill|trauma|grief|family|dating|breakup|conflict|"
    r"legal|lawsuit|money|finance|debt|workplace|burned out|burnout|"
    r"anxious|depressed|stress|stressed)\b",
    re.IGNORECASE,
)

STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "ask",
    "but",
    "for",
    "from",
    "has",
    "have",
    "her",
    "him",
    "his",
    "into",
    "last",
    "next",
    "note",
    "person",
    "relationship",
    "she",
    "that",
    "the",
    "their",
    "them",
    "this",
    "with",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _people_store_path(path: Path | None = None) -> Path:
    return path or PEOPLE_PATH


def _split_csv(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else value.split(",")
    seen: set[str] = set()
    items: list[str] = []
    for item in raw_items:
        normalized = re.sub(r"\s+", " ", str(item)).strip()
        key = normalized.lower()
        if normalized and key not in seen:
            items.append(normalized)
            seen.add(key)
    return items


def _append_unique(items: list[str], value: str) -> None:
    normalized = re.sub(r"\s+", " ", str(value)).strip(" .,:;").strip()
    if not normalized:
        return
    if normalized.lower() in {item.lower() for item in items}:
        return
    items.append(normalized)


def _normalize_relationship_type(value: str) -> str:
    normalized = re.sub(r"\s+", "_", str(value or "unknown").strip().lower())
    allowed = {
        "friend",
        "family",
        "collaborator",
        "mentor",
        "prospect",
        "community",
        "professional",
        "networking",
        "unknown",
    }
    return normalized if normalized in allowed else "unknown"


def _tokens(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text.lower())
        if word not in STOPWORDS
    ]


def _event_store(path: Path | None = None) -> Path:
    return _people_store_path(path)


def load_events(path: Path | None = None) -> list[dict[str, Any]]:
    store = _event_store(path)
    if not store.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in store.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def _write_events(events: list[dict[str, Any]], path: Path | None = None) -> None:
    store = _event_store(path)
    store.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(event, ensure_ascii=False) for event in events)
    store.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


def _next_id(events: list[dict[str, Any]], prefix: str, now: str, field: str) -> str:
    date_part = now[:10].replace("-", "")
    id_prefix = f"{prefix}_{date_part}_"
    max_seen = 0
    for event in events:
        candidates = [str(event.get(field, "")), str(event.get("person_id", ""))]
        for candidate in candidates:
            if not candidate.startswith(id_prefix):
                continue
            suffix = candidate.removeprefix(id_prefix)
            if suffix.isdigit():
                max_seen = max(max_seen, int(suffix))
    return f"{id_prefix}{max_seen + 1:03d}"


def _append_event(event_type: str, person_id: str, payload: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    events = load_events(path)
    now = _now_iso()
    event = {
        "schema_version": 1,
        "event_id": _next_id(events, "rel_event", now, "event_id"),
        "event_type": event_type,
        "person_id": person_id,
        "created_at": now,
        "payload": payload,
    }
    events.append(event)
    _write_events(events, path)
    return event


def _empty_person(person_id: str, now: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "person_id": person_id,
        "display_name": "",
        "aliases": [],
        "relationship_type": "unknown",
        "context_notes": [],
        "interaction_log": [],
        "open_loops": [],
        "important_dates": [],
        "tags": [],
        "concepts": [],
        "linked_note_ids": [],
        "cadence_days": None,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }


def _apply_event(people: dict[str, dict[str, Any]], event: dict[str, Any]) -> None:
    person_id = str(event.get("person_id", ""))
    if not person_id:
        return
    payload = event.get("payload", {})
    event_type = event.get("event_type")
    created_at = str(event.get("created_at", _now_iso()))

    if event_type == "person_created":
        person = _empty_person(person_id, created_at)
        person["display_name"] = str(payload.get("display_name", "")).strip()
        person["aliases"] = _split_csv(payload.get("aliases", []))
        person["relationship_type"] = _normalize_relationship_type(payload.get("relationship_type", "unknown"))
        person["tags"] = _split_csv(payload.get("tags", []))
        person["concepts"] = _split_csv(payload.get("concepts", []))
        person["cadence_days"] = payload.get("cadence_days")
        people[person_id] = person
    elif person_id not in people:
        return

    person = people.get(person_id)
    if not person:
        return

    if event_type == "context_note_added":
        note = {
            "note_id": payload.get("note_id"),
            "text": payload.get("text", ""),
            "sensitive": bool(payload.get("sensitive", False)),
            "linked_note_ids": _split_csv(payload.get("linked_note_ids", [])),
            "created_at": created_at,
        }
        person["context_notes"].append(note)
        for concept in _split_csv(payload.get("concepts", [])):
            _append_unique(person["concepts"], concept)
        for tag in _split_csv(payload.get("tags", [])):
            _append_unique(person["tags"], tag)
        for note_id in note["linked_note_ids"]:
            _append_unique(person["linked_note_ids"], note_id)
        open_loop = str(payload.get("open_loop", "")).strip()
        if open_loop:
            person["open_loops"].append({
                "loop_id": payload.get("open_loop_id"),
                "text": open_loop,
                "status": "open",
                "created_at": created_at,
            })
    elif event_type == "interaction_logged":
        interaction = {
            "interaction_id": payload.get("interaction_id"),
            "summary": payload.get("summary", ""),
            "happened_at": payload.get("happened_at") or created_at,
            "channel": payload.get("channel", ""),
            "created_at": created_at,
        }
        person["interaction_log"].append(interaction)
        person["last_interaction_at"] = interaction["happened_at"]
        for concept in _split_csv(payload.get("concepts", [])):
            _append_unique(person["concepts"], concept)
        open_loop = str(payload.get("open_loop", "")).strip()
        if open_loop:
            person["open_loops"].append({
                "loop_id": payload.get("open_loop_id"),
                "text": open_loop,
                "status": "open",
                "created_at": created_at,
            })
    elif event_type == "person_forgotten":
        person["deleted_at"] = created_at

    person["updated_at"] = created_at


def load_people(path: Path | None = None, include_deleted: bool = False) -> list[dict[str, Any]]:
    people: dict[str, dict[str, Any]] = {}
    for event in load_events(path):
        _apply_event(people, event)
    results = list(people.values())
    if not include_deleted:
        results = [person for person in results if not person.get("deleted_at")]
    return sorted(results, key=lambda person: str(person.get("updated_at", "")), reverse=True)


def _find_person(people: list[dict[str, Any]], person_id_or_name: str) -> list[dict[str, Any]]:
    query = person_id_or_name.strip().lower()
    matches = []
    for person in people:
        names = [str(person.get("person_id", "")), str(person.get("display_name", ""))]
        names.extend(str(alias) for alias in person.get("aliases", []))
        if any(query == name.lower() for name in names):
            matches.append(person)
    return matches


def _resolve_one_person(person_id_or_name: str, path: Path | None = None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    matches = _find_person(load_people(path), person_id_or_name)
    if not matches:
        return None, {
            "status": "error",
            "message": f"No person found for {person_id_or_name!r}.",
        }
    if len(matches) > 1:
        return None, {
            "status": "ambiguous",
            "message": f"Multiple people match {person_id_or_name!r}.",
            "matches": [
                {
                    "person_id": person["person_id"],
                    "display_name": person["display_name"],
                    "relationship_type": person["relationship_type"],
                    "context": _brief_context(person),
                }
                for person in matches
            ],
        }
    return matches[0], None


def _brief_context(person: dict[str, Any]) -> str:
    concepts = ", ".join(person.get("concepts", [])[:3])
    tags = ", ".join(person.get("tags", [])[:3])
    if concepts:
        return f"concepts: {concepts}"
    if tags:
        return f"tags: {tags}"
    return f"type: {person.get('relationship_type', 'unknown')}"


def add_person(
    display_name: str,
    relationship_type: str = "unknown",
    aliases: str | list[str] | None = None,
    context_note: str = "",
    tags: str | list[str] | None = None,
    concepts: str | list[str] | None = None,
    cadence_days: int | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Create a Person Record through an append-only person_created event."""
    name = re.sub(r"\s+", " ", display_name).strip()
    if not name:
        return {"status": "error", "message": "display_name is required."}

    events = load_events(path)
    now = _now_iso()
    person_id = _next_id(events, "person", now, "person_id")
    payload = {
        "display_name": name,
        "relationship_type": _normalize_relationship_type(relationship_type),
        "aliases": _split_csv(aliases),
        "tags": _split_csv(tags),
        "concepts": _split_csv(concepts),
        "cadence_days": cadence_days if cadence_days and cadence_days > 0 else None,
    }
    event = _append_event("person_created", person_id, payload, path)
    if context_note.strip():
        add_relationship_note(
            person_id,
            context_note,
            concepts=payload["concepts"],
            path=path,
        )
    person = get_person(person_id, path=path).get("person")
    return {
        "status": "ok",
        "person_id": person_id,
        "event": event,
        "person": person,
        "people_path": str(_people_store_path(path)),
    }


def list_people(path: Path | None = None) -> dict[str, Any]:
    people = load_people(path)
    return {
        "status": "ok",
        "count": len(people),
        "people": [
            {
                "person_id": person["person_id"],
                "display_name": person["display_name"],
                "relationship_type": person["relationship_type"],
                "aliases": person.get("aliases", []),
                "tags": person.get("tags", []),
                "concepts": person.get("concepts", []),
                "updated_at": person.get("updated_at"),
            }
            for person in people
        ],
    }


def get_person(person_id_or_name: str, path: Path | None = None, include_deleted: bool = False) -> dict[str, Any]:
    people = load_people(path, include_deleted=include_deleted)
    matches = _find_person(people, person_id_or_name)
    if not matches:
        return {"status": "error", "message": f"No person found for {person_id_or_name!r}."}
    if len(matches) > 1:
        return {
            "status": "ambiguous",
            "matches": [
                {
                    "person_id": person["person_id"],
                    "display_name": person["display_name"],
                    "relationship_type": person["relationship_type"],
                    "context": _brief_context(person),
                }
                for person in matches
            ],
        }
    return {"status": "ok", "person": matches[0]}


def search_people(query: str, max_people: int = 10, path: Path | None = None) -> dict[str, Any]:
    query_tokens = set(_tokens(query))
    query_lower = query.lower().strip()
    matches: list[tuple[int, dict[str, Any]]] = []
    for person in load_people(path):
        haystack_parts = [
            person.get("display_name", ""),
            person.get("relationship_type", ""),
            " ".join(person.get("aliases", [])),
            " ".join(person.get("tags", [])),
            " ".join(person.get("concepts", [])),
            " ".join(note.get("text", "") for note in person.get("context_notes", [])),
            " ".join(item.get("summary", "") for item in person.get("interaction_log", [])),
            " ".join(loop.get("text", "") for loop in person.get("open_loops", [])),
        ]
        haystack = " ".join(str(part) for part in haystack_parts).lower()
        score = sum(3 for token in query_tokens if token in haystack)
        if query_lower and query_lower in haystack:
            score += 5
        if score:
            matches.append((score, person))

    ranked = sorted(matches, key=lambda item: (-item[0], item[1]["display_name"].lower()))
    return {
        "status": "ok",
        "query": query,
        "count": len(ranked[:max_people]),
        "matches": [
            {
                "person_id": person["person_id"],
                "display_name": person["display_name"],
                "relationship_type": person["relationship_type"],
                "score": score,
                "state_labels": _state_labels(person),
                "context": _brief_context(person),
            }
            for score, person in ranked[:max_people]
        ],
    }


def add_relationship_note(
    person_id_or_name: str,
    text: str,
    concepts: str | list[str] | None = None,
    tags: str | list[str] | None = None,
    linked_note_ids: str | list[str] | None = None,
    open_loop: str = "",
    sensitive: bool | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    person, error = _resolve_one_person(person_id_or_name, path)
    if error:
        return error
    assert person is not None
    note_text = text.strip()
    if not note_text:
        return {"status": "error", "message": "text is required."}
    now = _now_iso()
    payload = {
        "note_id": _next_id(load_events(path), "rel_note", now, "event_id"),
        "text": note_text,
        "concepts": _split_csv(concepts),
        "tags": _split_csv(tags),
        "linked_note_ids": _split_csv(linked_note_ids),
        "open_loop": open_loop.strip(),
        "open_loop_id": _next_id(load_events(path), "open_loop", now, "event_id") if open_loop.strip() else None,
        "sensitive": bool(SENSITIVE_PATTERN.search(note_text)) if sensitive is None else bool(sensitive),
    }
    event = _append_event("context_note_added", person["person_id"], payload, path)
    return {
        "status": "ok",
        "person_id": person["person_id"],
        "event": event,
        "person": get_person(person["person_id"], path=path).get("person"),
        "people_path": str(_people_store_path(path)),
    }


def log_relationship_interaction(
    person_id_or_name: str,
    summary: str,
    happened_at: str = "",
    channel: str = "",
    concepts: str | list[str] | None = None,
    open_loop: str = "",
    path: Path | None = None,
) -> dict[str, Any]:
    person, error = _resolve_one_person(person_id_or_name, path)
    if error:
        return error
    assert person is not None
    interaction_summary = summary.strip()
    if not interaction_summary:
        return {"status": "error", "message": "summary is required."}
    now = _now_iso()
    payload = {
        "interaction_id": _next_id(load_events(path), "interaction", now, "event_id"),
        "summary": interaction_summary,
        "happened_at": happened_at.strip() or now,
        "channel": channel.strip(),
        "concepts": _split_csv(concepts),
        "open_loop": open_loop.strip(),
        "open_loop_id": _next_id(load_events(path), "open_loop", now, "event_id") if open_loop.strip() else None,
    }
    event = _append_event("interaction_logged", person["person_id"], payload, path)
    return {
        "status": "ok",
        "person_id": person["person_id"],
        "event": event,
        "person": get_person(person["person_id"], path=path).get("person"),
        "people_path": str(_people_store_path(path)),
    }


def forget_person(person_id_or_name: str, path: Path | None = None) -> dict[str, Any]:
    person, error = _resolve_one_person(person_id_or_name, path)
    if error:
        return error
    assert person is not None
    event = _append_event("person_forgotten", person["person_id"], {"reason": "user_requested"}, path)
    return {
        "status": "ok",
        "changed": True,
        "person_id": person["person_id"],
        "event": event,
        "people_path": str(_people_store_path(path)),
    }


def _state_labels(person: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    if any(loop.get("status") == "open" for loop in person.get("open_loops", [])):
        labels.extend(["needs_follow_up", "has_open_loop"])
    if person.get("cadence_days") and person.get("last_interaction_at"):
        labels.append("cadence_tracked")
    elif not person.get("interaction_log"):
        labels.append("dormant")
    else:
        labels.append("recently_connected")
    if any(note.get("sensitive") for note in person.get("context_notes", [])):
        labels.append("sensitive_context")
    return labels


def _draft_allowed(person: dict[str, Any]) -> bool:
    return person.get("relationship_type") in PROFESSIONAL_TYPES


def _recommendation_for(person: dict[str, Any]) -> tuple[int, list[str], str, str]:
    score = 0
    reasons: list[str] = []
    open_loops = [
        loop for loop in person.get("open_loops", [])
        if loop.get("status") == "open"
    ]
    if open_loops:
        score += 40
        reasons.append(f"{len(open_loops)} open loop(s) need follow-up.")
    if not person.get("interaction_log"):
        score += 15
        reasons.append("No interaction has been logged yet.")
    if person.get("cadence_days"):
        score += 10
        reasons.append(f"Soft cadence is set to every {person['cadence_days']} days.")
    if person.get("concepts"):
        score += min(10, len(person["concepts"]) * 2)
        reasons.append("Shared concepts: " + ", ".join(person["concepts"][:3]) + ".")
    if any(note.get("sensitive") for note in person.get("context_notes", [])):
        reasons.append("Sensitive context is present; be tactful.")

    if score >= 45:
        confidence = "high"
    elif score >= 20:
        confidence = "medium"
    else:
        confidence = "low"

    if open_loops:
        recommendation = f"Reconnect with {person['display_name']} about: {open_loops[0]['text']}"
    elif person.get("concepts"):
        recommendation = f"Reconnect with {person['display_name']} around {person['concepts'][0]}."
    else:
        recommendation = f"Consider a light check-in with {person['display_name']}."
    suggested_angle = "Use a concrete professional update." if _draft_allowed(person) else "Keep it personal and write it in your own voice."
    return score, reasons, recommendation, suggested_angle if reasons else ""


def recommend_reconnections(max_people: int = 5, path: Path | None = None) -> dict[str, Any]:
    recommendations = []
    for person in load_people(path):
        score, reasons, recommendation, suggested_angle = _recommendation_for(person)
        if not reasons:
            continue
        recommendations.append((score, person, reasons, recommendation, suggested_angle))

    ranked = sorted(recommendations, key=lambda item: (-item[0], item[1]["display_name"].lower()))
    return {
        "status": "ok",
        "count": len(ranked[:max_people]),
        "recommendations": [
            {
                "person_id": person["person_id"],
                "display_name": person["display_name"],
                "relationship_type": person["relationship_type"],
                "recommendation": recommendation,
                "reasons": reasons,
                "state_labels": _state_labels(person),
                "confidence": "high" if score >= 45 else "medium" if score >= 20 else "low",
                "draft_allowed": _draft_allowed(person),
                "suggested_angle": suggested_angle,
            }
            for score, person, reasons, recommendation, suggested_angle in ranked[:max_people]
        ],
    }
