"""Adaptive grill — personalized question generation and response handling.

Extracted from agent.py per Python Module Architecture Plan Phase 4.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .paths import GRILL_LOG_PATH, now_iso

logger = logging.getLogger(__name__)


# ── Grill-specific helpers ───────────────────────────────────────────


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
    cards: list[dict[str, Any]] = []
    for record in records:
        title = record.get("metadata", {}).get("title", record["source"])
        notes = record.get("notes", {})
        for bucket in ["methods", "findings", "limitations", "open_questions"]:
            for item in notes.get(bucket, [])[:4]:
                cards.append({
                    "source": record["source"], "title": title, "bucket": bucket,
                    "citation": item.get("citation"), "text": item.get("text", ""),
                })
        for concept in notes.get("concepts", [])[:8]:
            cards.append({
                "source": record["source"], "title": title, "bucket": "concept",
                "citation": concept.get("citation"), "text": concept.get("name", ""),
            })
    return cards


def _adaptive_question(
    question_id: str, question: str, recommendation: str, reason: str,
    source: str = "", citation: str | None = None, profile_signal: str = "",
) -> dict[str, Any]:
    return {
        "id": question_id, "question": question,
        "recommendation": recommendation, "why_this_question": reason,
        "source": source or None, "citation": citation,
        "profile_signal": profile_signal or None,
    }


def _append_grill_session(session: dict[str, Any]) -> None:
    GRILL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with GRILL_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(session) + "\n")


# ── Public grill tools ───────────────────────────────────────────────


def adaptive_grill(topic: str = "", source: str = "", question_count: int = 5) -> dict[str, Any]:
    """Generate personalized questions from the user model and ingested text."""
    from research_paper_agent import concept_graph, personal_notes  # noqa: PLC0415
    from research_paper_agent.agent import (  # noqa: PLC0415
        PERSONAL_NOTES_PATH, _load_records, _load_user_profile, search_evidence,
    )

    profile = _load_user_profile()
    records = _load_records()
    if source:
        records = [
            r for r in records
            if source.lower() in r["source"].lower()
            or source.lower() in r.get("metadata", {}).get("title", "").lower()
        ]

    profile_summary = _profile_signal_summary(profile)
    cards = _note_cards_for_records(records)

    # Note-guided questioning.
    note_concepts: list[str] = []
    try:
        note_list = personal_notes.list_notes(path=PERSONAL_NOTES_PATH).get("notes", [])
        for n in note_list[-20:]:
            note_concepts.extend(n.get("concepts", []))
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

    # Concept-graph ranking.
    try:
        user_interests = [item.get("name", "") for item in profile.get("interests", [])]
        if user_interests:
            cards = concept_graph.rank(user_interests, cards)
    except Exception:
        pass

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
            questions.append(_adaptive_question(
                f"Q{len(questions) + 1:03d}",
                f"When you read this passage about '{topic}', what do you want to decide or build from it?",
                "Turn your answer into a saved preference if it describes a recurring interest.",
                "The topic matched an evidence passage.",
                source=match["source"], citation=match["citation"],
                profile_signal=str(style.get("preference", "")),
            ))
            if index >= 2:
                break

    for card in cards:
        if len(questions) >= max_questions:
            break
        if card["bucket"] == "limitations":
            questions.append(_adaptive_question(
                f"Q{len(questions) + 1:03d}",
                f"Does this limitation change how you would trust or use {card['title']}?",
                "If yes, ask for a comparison against another paper.",
                "Limitations fit your preference for practical, decision-oriented questions.",
                source=card["source"], citation=card["citation"],
                profile_signal=str(interest.get("name", "")),
            ))
        elif card["bucket"] == "methods":
            questions.append(_adaptive_question(
                f"Q{len(questions) + 1:03d}",
                f"What part of this method would you want your own agent to copy, reject, or test?",
                "Extract a reusable design pattern tied to a cited method passage.",
                "Your profile emphasizes agent-building and iterative improvement.",
                source=card["source"], citation=card["citation"],
                profile_signal=str(interest.get("name", "")),
            ))
        elif card["bucket"] == "open_questions":
            questions.append(_adaptive_question(
                f"Q{len(questions) + 1:03d}",
                f"Which open question here is most worth turning into your next research task?",
                "Promote the chosen question into a follow-up search prompt.",
                "Open questions connect to your workflow.",
                source=card["source"], citation=card["citation"],
                profile_signal=str(style.get("preference", "")),
            ))

    for concept in note_concepts:
        if len(questions) >= max_questions:
            break
        questions.append(_adaptive_question(
            f"Q{len(questions) + 1:03d}",
            f"Your notes mention '{concept}'. Has anything in these papers changed your thinking?",
            "If yes, save an updated note with your new perspective.",
            "Your personal notes connect this concept to your research interests.",
            profile_signal=concept,
        ))

    if len(questions) < max_questions:
        questions.append(_adaptive_question(
            f"Q{len(questions) + 1:03d}",
            "When I ask research questions, do you want me to challenge assumptions first or summarize evidence first?",
            "Save the answer with set_user_preference as a style preference.",
            "Resolves an adaptation choice the current user model cannot infer.",
            profile_signal=", ".join(profile_summary["question_patterns"][:2]),
        ))
    if len(questions) < max_questions:
        questions.append(_adaptive_question(
            f"Q{len(questions) + 1:03d}",
            "What topics should I keep connecting papers back to by default?",
            "Save recurring topics as interests.",
            "The user model benefits from explicit interests.",
            profile_signal=", ".join(profile_summary["interests"][:3]),
        ))

    session = {
        "timestamp": now_iso(), "topic": topic or None, "source": source or None,
        "profile_summary": profile_summary, "questions": questions[:max_questions],
    }
    _append_grill_session(session)

    return {
        "session_log_path": str(GRILL_LOG_PATH),
        "first_question": questions[0] if questions else None,
        "queued_questions": questions[1:max_questions],
        "recommendation": (
            "Ask the first question only. After the user answers, call "
            "respond_to_adaptive_grill to update the user model."
        ),
        "profile_summary": profile_summary,
    }


def respond_to_adaptive_grill(question_id: str, user_answer: str, question_text: str = "") -> dict[str, Any]:
    """Learn from a user's grill answer and recommend the next adaptation."""
    from research_paper_agent import concept_graph  # noqa: PLC0415
    from research_paper_agent.agent import (  # noqa: PLC0415
        CANDIDATE_SIGNALS_PATH, _infer_message_signals,
        _is_explicit_memory_request, _load_user_profile,
        _projection_status, _record_candidate_signals,
        record_interaction, set_user_preference,
    )
    from .paths import now_iso  # noqa: PLC0415

    candidate_signals = _infer_message_signals(user_answer)
    explicit_memory = _is_explicit_memory_request(user_answer)
    context = f"answer to adaptive grill question {question_id}: {question_text[:180]}"
    _record_candidate_signals({
        "timestamp": now_iso(), "question_id": question_id,
        "question_text": question_text, "user_answer": user_answer,
        "signals": candidate_signals, "explicit_memory_request": explicit_memory,
    })
    record_interaction(
        user_message=user_answer,
        agent_response=f"Adaptive grill answer for {question_id}",
        outcome="captured_candidate_signal", tags="adaptive_grill,personalization",
    )

    if question_text:
        try:
            profile = _load_user_profile()
            for interest in profile.get("interests", []):
                interest_name = interest.get("name", "")
                if interest_name and any(
                    token in question_text.lower() for token in interest_name.lower().split()
                ):
                    concept_graph.link(interest_name, question_text[:120], "adaptive_grill", edge_type="engaged")
        except Exception:
            pass

    lower = user_answer.lower()
    durable_updates = []
    if explicit_memory and any(w in lower for w in ["short", "concise", "brief", "blunt"]):
        durable_updates.append(set_user_preference("style", "Prefer short, direct grill questions.", user_answer[:240], 0.85))
    if explicit_memory and any(w in lower for w in ["challenge", "assumption", "push", "grill"]):
        durable_updates.append(set_user_preference("adaptation_rule", "When reviewing papers, challenge assumptions.", user_answer[:240], 0.82))
    if explicit_memory and any(w in lower for w in ["build", "agent", "workflow", "tool"]):
        durable_updates.append(set_user_preference("interest", "turning research into agent improvements", user_answer[:240], 0.8))

    result = {
        "status": "ok",
        "candidate_signals_path": str(CANDIDATE_SIGNALS_PATH),
        "candidate_signals": candidate_signals,
        "explicit_memory_request": explicit_memory,
        "durable_updates": durable_updates,
        "next_recommendation": "Treat as provisional unless it repeats or user explicitly asked to remember.",
    }
    return _projection_status(result, "grill_answer", question_id, question_text)
