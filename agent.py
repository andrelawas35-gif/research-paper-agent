from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
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
    score_passage as _score_passage,
    search_evidence as _rt_search_evidence,
)
from .agent_runtime.papers import (  # noqa: E402, F401
    _load_records,
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

# ── Architecture Plan Phase 2: durable profile + session state ────────
from .agent_runtime.user_profile import (  # noqa: E402
    CandidateSignal as _UpCandidateSignal,
    UserProfile as _UpUserProfile,
    _append_unique_signal as _up_append_unique_signal,
    _default_user_profile as _up_default_user_profile,
    _infer_message_signals as _up_infer_message_signals,
    _is_explicit_memory_request as _up_is_explicit_memory_request,
    _load_user_profile as _up_load_user_profile,
    _record_candidate_signals as _up_record_candidate_signals,
    _save_user_profile as _up_save_user_profile,
    _validate_candidate_signal as _up_validate_candidate_signal,
    _validate_profile as _up_validate_profile,
    get_user_profile as _up_get_user_profile,
    learn_from_user_message as _up_learn_from_user_message,
    set_user_preference as _up_set_user_preference,
)
from .agent_runtime.session_memory import (  # noqa: E402
    _write_session_meta as _sm_write_session_meta,
    record_interaction as _sm_record_interaction,
)

UserProfile = _UpUserProfile
CandidateSignal = _UpCandidateSignal
_append_unique_signal = _up_append_unique_signal
_default_user_profile = _up_default_user_profile
_infer_message_signals = _up_infer_message_signals
_is_explicit_memory_request = _up_is_explicit_memory_request
_load_user_profile = _up_load_user_profile
_record_candidate_signals = _up_record_candidate_signals
_save_user_profile = _up_save_user_profile
_validate_candidate_signal = _up_validate_candidate_signal
_validate_profile = _up_validate_profile
get_user_profile = _up_get_user_profile
learn_from_user_message = _up_learn_from_user_message
set_user_preference = _up_set_user_preference
record_interaction = _sm_record_interaction
_write_session_meta = _sm_write_session_meta


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


# ── ADR 0070: Record schemas ────────────────────────────────────────


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




def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Delegates to agent_runtime.paths.now_iso.
    """
    from .agent_runtime.paths import now_iso as _paths_now_iso

    return _paths_now_iso()


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





# ---------------------------------------------------------------------------
# Tutor Mode — helpers and tools
# ---------------------------------------------------------------------------


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


def _aliased_tool(fn, *aliases: str):
    """Register a tool under its own name plus alias names.

    The ADK resolves tools by exact function name.  If the LLM calls
    ``list_paper`` instead of ``list_papers``, the call fails.  This
    creates thin wrappers with the alias names so both names work.

    Usage::

        tools=[*_aliased_tool(list_papers, "list_paper", "show_papers"), ...]
    """
    from google.adk.tools import FunctionTool

    wrapped = _safe_tool(fn)
    tools = [FunctionTool(wrapped)]
    for alias in aliases:
        alias_fn = _make_alias(wrapped, alias)
        tools.append(FunctionTool(alias_fn))
    return tools


def _make_alias(fn, name: str):
    """Create a callable with a specific __name__ that delegates to fn."""
    def _alias(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)
    _alias.__name__ = name
    _alias.__qualname__ = name
    _alias.__doc__ = fn.__doc__
    _alias.__wrapped__ = fn  # type: ignore[attr-defined]
    return _alias


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
        *_aliased_tool(list_papers, "list_paper", "show_papers"),
        _safe_tool(rename_paper),
        _safe_tool(delete_paper),
        _safe_tool(organize_papers),
        *_aliased_tool(ingest_paper, "add_paper", "read_paper"),
        _safe_tool(ingest_all_papers),
        *_aliased_tool(list_concepts, "list_concept", "show_concepts"),
        *_aliased_tool(search_evidence, "search_paper", "find_evidence"),
        *_aliased_tool(paper_brief, "brief_paper", "summarize_paper"),
        _safe_tool(compare_papers),
        *_aliased_tool(make_study_guide, "study_guide", "create_study_guide"),
        *_aliased_tool(get_user_profile, "show_profile", "my_profile"),
        _safe_tool(learn_from_user_message),
        _safe_tool(record_interaction),
        _safe_tool(set_user_preference),
        *_aliased_tool(save_personal_note, "save_note", "create_note"),
        *_aliased_tool(list_personal_notes, "list_notes", "show_notes"),
        *_aliased_tool(get_personal_note, "get_note", "read_note"),
        *_aliased_tool(search_personal_notes, "search_notes", "find_notes"),
        _safe_tool(delete_personal_note),
        *_aliased_tool(edit_personal_note, "edit_note", "update_note"),
        _safe_tool(reject_note_card),
        _safe_tool(reject_note_concept),
        _safe_tool(get_note_backlinks),
        _safe_tool(render_note_markdown),
        _safe_tool(import_markdown_notes),
        _safe_tool(add_person),
        *_aliased_tool(list_people, "list_person", "show_people"),
        *_aliased_tool(get_person, "show_person", "find_person"),
        *_aliased_tool(search_people, "search_person", "find_people"),
        _safe_tool(add_relationship_note),
        _safe_tool(log_relationship_interaction),
        _safe_tool(recommend_reconnections),
        _safe_tool(forget_person),
        *_aliased_tool(search_web, "web_search", "lookup"),
        *_aliased_tool(knowledge_self_audit, "audit", "self_audit"),
        _safe_tool(self_audit_correction),
        _safe_tool(adaptive_grill),
        _safe_tool(respond_to_adaptive_grill),
        _safe_tool(concept_graph.get_concept_graph),
        _safe_tool(concept_graph.suggest_concept_merges),
        *_aliased_tool(record_tutor_answer, "grade_answer", "tutor_answer"),
        *_aliased_tool(get_tutor_progress, "tutor_progress", "show_progress"),
    ],
)
