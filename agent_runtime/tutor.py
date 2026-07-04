"""Tutor mode — progress tracking, grading, next-concept selection.

Extracted from agent.py per Python Module Architecture Plan Phase 4.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .paths import TUTOR_PROGRESS_PATH, TUTOR_SESSIONS_PATH

logger = logging.getLogger(__name__)


def _load_tutor_progress() -> dict[str, Any]:
    """Load concept-level mastery summary, cached in memory."""
    cache = getattr(_load_tutor_progress, "_cache", None)
    if cache is not None:
        return cache
    TUTOR_PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
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
    """Persist tutor progress to disk and invalidate cache."""
    from .paths import now_iso  # noqa: PLC0415

    TUTOR_PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    progress["updated_at"] = now_iso()
    TUTOR_PROGRESS_PATH.write_text(json.dumps(progress, indent=2), encoding="utf-8")
    _load_tutor_progress._cache = progress  # type: ignore[attr-defined]


def _next_concept(
    progress: dict[str, Any],
    user_interests: list[str],
    last_was_weak: bool,
) -> dict[str, Any]:
    """Pick the next concept to teach using alternating weak/interest strategy."""
    from research_paper_agent import concept_graph  # noqa: PLC0415

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

    # Prerequisite priority boost (one-hop).
    try:
        for candidate_list in (weak, strong):
            for entry in candidate_list:
                concept_key = entry["_key"]
                for prereq_key in concept_graph.get_prerequisites(concept_key):
                    prereq_entry = concepts.get(prereq_key)
                    if prereq_entry:
                        asked_p = max(prereq_entry.get("times_asked", 0), 1)
                        ratio_p = prereq_entry.get("times_correct", 0) / asked_p
                        if ratio_p >= 0.8:
                            continue
                        prereq_entry["_key"] = prereq_key
                        if prereq_entry not in weak:
                            weak.insert(0, prereq_entry)
                    else:
                        return {
                            "concept": prereq_key,
                            "reason": f"prerequisite for '{concept_key}' — never taught yet",
                        }
    except Exception:
        pass

    if not last_was_weak and weak:
        target = weak[0]
        return {"concept": target["_key"], "reason": f"weak concept — {target.get('times_correct', 0)}/{target.get('times_asked', 1)} correct"}

    if strong:
        target = strong[-1]
        return {"concept": target["_key"], "reason": "strong concept — reinforce before mastery"}

    if weak:
        target = weak[0]
        return {"concept": target["_key"], "reason": f"weak concept — {target.get('times_correct', 0)}/{target.get('times_asked', 1)} correct"}

    if user_interests:
        return {"concept": user_interests[0], "reason": "new session — starting with your top interest"}
    return {"concept": None, "reason": "no progress and no interests — ask the user what to study"}


def _grade_answer(question: str, user_answer: str, passage_text: str) -> dict[str, Any]:
    """Grade a free-text tutor answer via LLM."""
    from openai import OpenAI  # noqa: PLC0415

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
        "correct": correct, "verdict": "CORRECT" if correct else "INCORRECT",
        "reason": reason.strip(), "mastery_hint": hint.strip() if hint else None,
        "raw": text,
    }
