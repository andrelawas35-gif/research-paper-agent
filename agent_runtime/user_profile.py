"""Durable user profile — interests, style, preferences, candidate signals.

Extracted from agent.py per Python Module Architecture Plan Phase 2.
Owns everything that represents the user's durable, cross-session state:
the profile itself, message-signal inference, and the candidate-signal
log used before a signal is promoted into the profile.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypedDict

from .paths import CANDIDATE_SIGNALS_PATH, USER_PROFILE_PATH, ensure_dirs, now_iso

logger = logging.getLogger(__name__)


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


STOPWORDS = {
    "about", "abstract", "after", "again", "against", "and", "are",
    "also", "among", "because", "before", "between", "can", "could",
    "figure", "first", "for", "from", "have", "into", "more", "most",
    "other", "paper", "results", "section", "show", "shows", "such",
    "table", "than", "that", "the", "their", "these", "this",
    "through", "using", "were", "when", "where", "which", "while",
    "with", "would",
}


def _tokenize(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
        if word not in STOPWORDS
    ]


def _default_user_profile() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": now_iso(),
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
    ensure_dirs()
    if not USER_PROFILE_PATH.exists():
        profile = _default_user_profile()
        USER_PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        _load_user_profile._cache = profile  # type: ignore[attr-defined]
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
    ensure_dirs()
    profile["updated_at"] = now_iso()
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


def _validate_candidate_signal(record: dict[str, Any]) -> bool:
    """Return True if a candidate signal record has required fields."""
    if not isinstance(record.get("timestamp"), str):
        return False
    if not isinstance(record.get("signals"), list):
        return False
    return True


def _record_candidate_signals(event: dict[str, Any]) -> None:
    ensure_dirs()
    if not _validate_candidate_signal(event):
        logger.warning("Rejecting malformed candidate signal: %s", event.get("timestamp", "unknown"))
        return
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
