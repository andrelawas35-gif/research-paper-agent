"""Dynamic context construction — Performance Budget, snapshots, and cache.

ADR 0072 Slice 1: per-turn Performance Budget inference, tier-specific
snapshot builders, budget-aware snapshot caching, and dynamic instruction
construction.

Extracted from agent.py per the Python Module Architecture Plan Phase 1.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from .paths import (
    CONCEPT_GRAPH_PATH,
    PERSONAL_NOTES_PATH,
    SESSION_META_PATH,
    TUTOR_PROGRESS_PATH,
    USER_PROFILE_PATH,
)

logger = logging.getLogger(__name__)

# ── Budget tier constants ────────────────────────────────────────────
# Plain string literals per ADR 0072; typed enums deferred until budget
# crosses module boundaries (model routing, tool exposure, metrics).

FAST: str = "fast"
BALANCED: str = "balanced"
DEEP: str = "deep"
_VALID_TIERS: frozenset[str] = frozenset({FAST, BALANCED, DEEP})

# ── Snapshot cache ───────────────────────────────────────────────────
# Keyed by (state_fingerprint, budget_tier) so balanced and deep never
# share cached text for the same durable state.  fast bypasses the cache
# entirely because it returns an empty instruction.

_SNAPSHOT_CACHE: dict[tuple[str, str], str] = {}


# ======================================================================
# Budget Inference
# ======================================================================

# ── Explicit performance wording ─────────────────────────────────────
# These patterns are checked against the latest user text.  Explicit
# wording always wins over mode-hint inference (ADR 0072).

_FAST_PATTERNS: list[str] = [
    r"\bfast\s*mode\b",
    r"\bkeep\s+it\s+(quick|fast|short|brief|terse)\b",
    r"\b(quick|quickly|just|only)\s+(tell|show|check|get|give)\b",
    r"\bno\s+explanation\b",
    r"\bdon't\s+explain\b",
    r"\bkeep\s+(this|it)\s+(short|brief)\b",
    r"\bmake\s+it\s+(quick|fast)\b",
]

_DEEP_PATTERNS: list[str] = [
    r"\bdeep\s*mode\b",
    r"\bthink\s+(deeply|hard|carefully)\b",
    r"\b(go|dive)\s+deep(er)?\b",
    r"\bthorough(ly)?\b",
    r"\bcomprehensive(ly)?\b",
    r"\bin[- ]depth\b",
    r"\btake\s+your\s+time\b",
    r"\bno\s+rush\b",
    r"\b(ingest|import)\s+(all\s+)?(papers|documents|files)\b",
    r"\b(read|scan)\s+(all\s+)?(papers|documents|files|the\s+folder|papers\s+folder|the\s+papers\s+folder)\b",
]

# ── Mode hints that suggest a budget tier ────────────────────────────
# Only used when no explicit performance wording is found.

_DEEP_MODE_HINTS: frozenset[str] = frozenset({
    "grill", "mentor", "tutor", "synthesis", "builder",
    "review", "taste",
})

_FAST_MODE_HINTS: frozenset[str] = frozenset({
    "admin", "retrieve",
})

# ── Mode taxonomy keywords for loose mode-hint extraction ────────────

_MODE_KEYWORDS: dict[str, str] = {
    "source": "source",
    "reader": "source",
    "retrieve": "retrieve",
    "search": "retrieve",
    "synthesis": "synthesis",
    "synthesize": "synthesis",
    "builder": "builder",
    "build": "builder",
    "design": "builder",
    "grill": "grill",
    "tutor": "tutor",
    "teach": "tutor",
    "learn": "tutor",
    "reflect": "reflect",
    "profile": "reflect",
    "relationship": "relationship",
    "taste": "taste",
    "judge": "taste",
    "review": "review",
    "audit": "review",
    "writing": "writing",
    "write": "writing",
    "draft": "writing",
    "polish": "writing",
    "artifact": "artifact",
    "admin": "admin",
    "manage": "admin",
    "organize": "admin",
    "mentor": "mentor",
    "simon": "mentor",
    "lanier": "mentor",
}


def _extract_latest_user_text(ctx: Any) -> str:
    """Extract the latest user message from ADK context.

    Tries known ADK attributes or fields.  Returns ``""`` when the
    context is unavailable or unrecognised — the caller falls back to
    ``balanced``.  Never raises.
    """
    if ctx is None:
        return ""
    try:
        # ADK session events — last user message is typically the
        # second-to-last event (before the model response).
        session = getattr(ctx, "session", None)
        if session is not None:
            events = getattr(session, "events", [])
            if events:
                for ev in reversed(events):
                    author = getattr(ev, "author", None)
                    if author == "user":
                        content = getattr(ev, "content", None)
                        if content and isinstance(content, str):
                            return content.strip()
                        # content may be a list of Part objects
                        parts = getattr(content, "parts", None) if hasattr(content, "parts") else None
                        if parts:
                            text_parts = [getattr(p, "text", "") for p in parts if hasattr(p, "text")]
                            joined = " ".join(text_parts).strip()
                            if joined:
                                return joined
    except Exception:
        pass
    return ""


def _extract_mode_hint(ctx: Any) -> str:
    """Extract a mode hint from ADK context or latest user text.

    Returns a mode name from the taxonomy (e.g. ``"grill"``, ``"tutor"``)
    or ``""`` when no mode can be inferred.  Never raises.
    """
    # Try ADK metadata first (agent state, session metadata).
    if ctx is not None:
        try:
            session = getattr(ctx, "session", None)
            if session is not None:
                state = getattr(session, "state", {})
                if isinstance(state, dict):
                    mode = state.get("agent_mode", "")
                    if mode and mode.lower() in _MODE_KEYWORDS:
                        return _MODE_KEYWORDS[mode.lower()]
        except Exception:
            pass

    # Fall back to scanning the latest user text for mode keywords.
    text = _extract_latest_user_text(ctx)
    if not text:
        return ""

    lower = text.lower()
    for keyword, mode_name in _MODE_KEYWORDS.items():
        if keyword in lower:
            return mode_name

    return ""


def _infer_performance_budget_from_text(text: str, mode_hint: str = "") -> str:
    """Pure inference: text → budget tier.

    Rules (ADR 0072):
    1. Explicit fast/deep wording wins over everything.
    2. Mode hint is a tiebreaker when no explicit wording found.
    3. Unknown or missing context falls back to ``balanced``.

    Args:
        text: The latest user message text.
        mode_hint: An optional mode name (e.g. ``"grill"``) from the
                   mode taxonomy.  Only used when no explicit wording.

    Returns:
        One of ``"fast"``, ``"balanced"``, or ``"deep"``.
    """
    if not text:
        return BALANCED

    lower = text.lower()

    # 1. Explicit wording wins.
    for pattern in _FAST_PATTERNS:
        if re.search(pattern, lower):
            return FAST

    for pattern in _DEEP_PATTERNS:
        if re.search(pattern, lower):
            return DEEP

    # 2. Mode hint as tiebreaker.
    hint = mode_hint.lower().strip()
    if hint in _DEEP_MODE_HINTS:
        return DEEP
    if hint in _FAST_MODE_HINTS:
        return FAST

    # 3. Default.
    return BALANCED


def _infer_performance_budget(ctx: Any) -> str:
    """Infer the performance budget tier from ADK context.

    Extracts the latest user text and mode hint, then delegates to the
    pure inference function.  Falls back to ``balanced`` on any failure.
    Never raises.
    """
    try:
        text = _extract_latest_user_text(ctx)
        mode_hint = _extract_mode_hint(ctx)
        return _infer_performance_budget_from_text(text, mode_hint)
    except Exception:
        logger.debug("Performance budget inference failed; falling back to balanced")
        return BALANCED


def _validate_tier(tier: str) -> str:
    """Validate and normalise a budget tier string."""
    tier = tier.strip().lower()
    if tier in _VALID_TIERS:
        return tier
    return BALANCED


# ======================================================================
# State Fingerprinting
# ======================================================================


def state_fingerprint() -> str:
    """Return a short hash of all durable state that feeds the snapshot.

    When this hash changes, the snapshot is rebuilt.  When it stays the
    same, the cached snapshot is reused — keeping the instruction
    identical across turns and preserving the LLM context cache.
    """
    h = hashlib.sha1()
    for path in (
        USER_PROFILE_PATH,
        CONCEPT_GRAPH_PATH,
        PERSONAL_NOTES_PATH,
        TUTOR_PROGRESS_PATH,
    ):
        try:
            h.update(path.read_bytes())
        except Exception:
            pass
    return h.hexdigest()[:16]


# ======================================================================
# Snapshot Builders
# ======================================================================


def _load_user_profile():
    """Lazy import — avoids circular dependency with agent.py."""
    from research_paper_agent.agent import _load_user_profile as _loader  # noqa: PLC0415
    return _loader()


def _build_balanced_snapshot(ctx: Any | None = None) -> str:
    """Build a compact, stable orientation snapshot for ``balanced`` budget.

    Includes only stable fields that rarely change turn-to-turn:
    - explicit interests
    - style preferences
    - polish default
    - explicit avoidances
    - quirks
    - stable top graph concepts (without volatile counts)

    Excludes: recent notes, session metadata, weak tutor concepts,
    exact counts, timestamps, and any "latest" state.
    """
    profile = _load_user_profile()

    parts: list[str] = ["[context snapshot]"]

    # ── who ─────────────────────────────────────────────────────────
    interests = [i.get("name", "") for i in profile.get("interests", [])[:5]]
    style = [s.get("preference", "") for s in profile.get("style_preferences", [])[:3]]
    polish = profile.get("polish_preferences", {})
    polish_default = polish.get("default", "moderate") if isinstance(polish, dict) else "moderate"
    avoidances = [a.get("rule", "") for a in profile.get("avoidances", [])[:2]]
    quirks = [q.get("observation", "") for q in profile.get("grammar_and_quirks", [])[:2]]

    who_lines = []
    if interests:
        who_lines.append(f"interests: {', '.join(interests)}")
    if style:
        who_lines.append(f"style: {', '.join(style)}")
    who_lines.append(f"polish: {polish_default}")
    if avoidances:
        who_lines.append(f"avoid: {', '.join(avoidances)}")
    if quirks:
        who_lines.append(f"quirks: {', '.join(quirks)}")
    parts.append("user: " + "; ".join(who_lines))

    # ── graph (stable concepts, no counts) ──────────────────────────
    try:
        from research_paper_agent import concept_graph as cg  # noqa: PLC0415

        g = cg.load()
        edges = g.get("edges", {})
        edge_count: dict[str, int] = {}
        for interest_edges in edges.values():
            if isinstance(interest_edges, dict):
                for e in interest_edges.values():
                    if isinstance(e, dict):
                        c = e.get("concept", "")
                        if c:
                            edge_count[c] = edge_count.get(c, 0) + 1
        top = sorted(edge_count.items(), key=lambda x: -x[1])[:5]
        if top:
            # Include concept names only — no volatile counts.
            parts.append("top concepts: " + ", ".join(c for c, _ in top))
    except Exception:
        pass

    return "\n".join(parts)


def _build_deep_snapshot(ctx: Any | None = None, mode_hint: str = "") -> str:
    """Build a richer, task-scoped snapshot for ``deep`` budget.

    Includes the balanced snapshot plus task-relevant extras:
    - Recent note titles/concepts for note, synthesis, builder, review,
      or resume tasks.
    - Weak tutor concepts for tutor, mentor, or learning tasks.
    - One unfinished prior session only for explicit resume or
      continuation tasks.
    - Top graph concepts without volatile counters.

    Still excludes: raw note text, full interaction logs, full graph
    dumps, changing exact counts, timestamps, and unbounded session rows.
    """
    profile = _load_user_profile()

    parts: list[str] = ["[context snapshot — deep]"]

    # ── who (same as balanced) ──────────────────────────────────────
    interests = [i.get("name", "") for i in profile.get("interests", [])[:5]]
    style = [s.get("preference", "") for s in profile.get("style_preferences", [])[:3]]
    polish = profile.get("polish_preferences", {})
    polish_default = polish.get("default", "moderate") if isinstance(polish, dict) else "moderate"
    avoidances = [a.get("rule", "") for a in profile.get("avoidances", [])[:2]]
    quirks = [q.get("observation", "") for q in profile.get("grammar_and_quirks", [])[:2]]

    who_lines = []
    if interests:
        who_lines.append(f"interests: {', '.join(interests)}")
    if style:
        who_lines.append(f"style: {', '.join(style)}")
    who_lines.append(f"polish: {polish_default}")
    if avoidances:
        who_lines.append(f"avoid: {', '.join(avoidances)}")
    if quirks:
        who_lines.append(f"quirks: {', '.join(quirks)}")
    parts.append("user: " + "; ".join(who_lines))

    # ── task-scoped notes ───────────────────────────────────────────
    hint = mode_hint.lower()
    _note_modes = frozenset({"note", "synthesis", "builder", "review", "writing"})
    if hint in _note_modes:
        try:
            from research_paper_agent import personal_notes as pn  # noqa: PLC0415

            notes = pn.load_notes()
            active = [n for n in notes if not n.get("deleted_at") and n.get("title")]
            active.sort(key=lambda n: n.get("updated_at", n.get("created_at", "")), reverse=True)
            recent = active[:5]
            if recent:
                note_lines = []
                for n in recent:
                    title = n.get("title", "")[:60]
                    concepts = [c for c in n.get("concepts", [])[:3] if isinstance(c, str)]
                    label = title
                    if concepts:
                        label += f" [{', '.join(concepts)}]"
                    note_lines.append(label)
                parts.append("recent notes: " + " | ".join(note_lines))
        except Exception:
            pass

    # ── graph (stable concepts, no counts) ──────────────────────────
    try:
        from research_paper_agent import concept_graph as cg  # noqa: PLC0415

        g = cg.load()
        edges = g.get("edges", {})
        edge_count: dict[str, int] = {}
        for interest_edges in edges.values():
            if isinstance(interest_edges, dict):
                for e in interest_edges.values():
                    if isinstance(e, dict):
                        c = e.get("concept", "")
                        if c:
                            edge_count[c] = edge_count.get(c, 0) + 1
        top = sorted(edge_count.items(), key=lambda x: -x[1])[:5]
        if top:
            parts.append("top concepts: " + ", ".join(c for c, _ in top))
    except Exception:
        pass

    # ── weak tutor concepts ─────────────────────────────────────────
    _tutor_modes = frozenset({"tutor", "mentor", "learn"})
    if hint in _tutor_modes:
        try:
            tp = json.loads(TUTOR_PROGRESS_PATH.read_text()) if TUTOR_PROGRESS_PATH.exists() else {}
            weak = [c for c, s in tp.get("concepts", {}).items()
                    if isinstance(s, dict) and s.get("times_correct", 0) < s.get("times_asked", 1) * 0.5]
            if weak:
                parts.append(f"weak concepts: {', '.join(weak[:5])}")
        except Exception:
            pass

    # ── session context (one unfinished prior session) ───────────────
    if hint in {"resume", "continue"} or "resume" in hint or "continue" in hint:
        try:
            if SESSION_META_PATH.exists():
                lines = SESSION_META_PATH.read_text().strip().splitlines()
                if lines:
                    last = json.loads(lines[-1])
                    goal = last.get("inferred_goal", "")
                    status = last.get("completion_status", "")
                    if goal and status != "ended_naturally":
                        parts.append(
                            f"prior session: {goal} (unfinished)"
                        )
        except Exception:
            pass

    return "\n".join(parts)


# ======================================================================
# Dynamic Instruction Construction
# ======================================================================

# Performance budget suffix appended to the snapshot for long sessions.
# Fixed text — the event count is NOT embedded, so the instruction stays
# cache-stable across consecutive turns.
_COMPACTION_HINT: str = (
    "\n[compaction: long session. Be concise. "
    "Lead with the most relevant insight. "
    "Skip historical recaps. "
    "Prefer actionable next steps.]"
)


def _event_count(ctx: Any) -> int:
    """Return the number of session events, or 0 on failure."""
    if ctx is None:
        return 0
    try:
        session = getattr(ctx, "session", None)
        if session is not None:
            events = getattr(session, "events", [])
            return len(events) if events else 0
    except Exception:
        pass
    return 0


def build_dynamic_instruction(ctx: Any) -> str:
    """Build the dynamic instruction header for the current turn.

    Expected flow:
    1. Infer budget tier from context.
    2. ``fast`` → return empty string (bypass snapshot + cache).
    3. Compute durable-state fingerprint.
    4. Look up cached snapshot by ``(fingerprint, budget)``.
    5. On cache miss, build the tier-specific snapshot.
    6. Append compaction hint when session is long (>80 events).

    ``fast`` returns ``""`` so the model gets only the static instruction,
    maximising context-cache alignment.

    The caller (``agent.py``) passes this as ``instruction=`` to the
    ADK ``Agent``.
    """
    global _SNAPSHOT_CACHE

    # 1. Infer budget.
    budget = _infer_performance_budget(ctx)

    # 2. Fast bypass — no snapshot, no cache.
    if budget == FAST:
        return ""

    # 3. Compute fingerprint.
    fp = state_fingerprint()

    # 4. Cache lookup.
    cache_key = (fp, budget)
    cached = _SNAPSHOT_CACHE.get(cache_key)
    if cached is not None:
        snapshot = cached
    else:
        # 5. Build tier-specific snapshot.
        mode_hint = _extract_mode_hint(ctx)
        try:
            if budget == BALANCED:
                snapshot = _build_balanced_snapshot(ctx)
            else:  # deep
                snapshot = _build_deep_snapshot(ctx, mode_hint)
        except Exception:
            logger.debug("Snapshot build failed for budget=%s; returning empty", budget)
            return ""
        _SNAPSHOT_CACHE[cache_key] = snapshot

    # 6. Compaction hint for long sessions.
    ev_count = _event_count(ctx)
    if ev_count > 80:
        snapshot += _COMPACTION_HINT
        cache_hit = "hit" if cached is not None else "miss"

    # ── ADR 0072 Slice 2: Diagnostics (never in prompt context) ──────
    logger.debug(
        "performance_budget: tier=%s snapshot_type=%s size=%d cache=%s events=%d",
        budget,
        "balanced" if budget == BALANCED else "deep",
        len(snapshot),
        "hit" if cached is not None else "miss",
        ev_count,
    )

    return snapshot


# ======================================================================
# ADR 0072 Slice 2: Write Gating
# ======================================================================


def write_allowed(action_type: str, budget: str, evidence_strength: str = "explicit") -> bool:
    """Return True if a durable write is permitted under the current budget.

    Args:
        action_type: One of ``"memory"`` (explicit commands like "remember"),
                     ``"note"`` (save/edit note), ``"profile"`` (user model),
                     ``"graph"`` (concept graph), ``"projection"`` (derived).
        budget: ``"fast"``, ``"balanced"``, or ``"deep"``.
        evidence_strength: ``"explicit"``, ``"high_confidence"``, or
                           ``"candidate"``.

    Rules (ADR 0072):
    - ``fast``: only explicit memory commands ("remember", "save note").
    - ``balanced``: explicit intent + high-confidence structured events.
    - ``deep``: candidate signals + projection updates allowed; durable
      preferences still require explicit confirmation or repeated evidence.
    """
    budget = _validate_tier(budget)

    if budget == FAST:
        # Only explicit user commands for memory/notes.
        return action_type in ("memory", "note") and evidence_strength == "explicit"

    if budget == BALANCED:
        # Explicit commands or high-confidence events.
        if evidence_strength == "explicit":
            return action_type in ("memory", "note", "profile", "graph")
        if evidence_strength == "high_confidence":
            return action_type in ("note", "graph")
        return False

    # deep: broadest allowance, but durable prefs still gated.
    if evidence_strength == "explicit":
        return True  # allow all action types
    if evidence_strength == "high_confidence":
        return action_type in ("note", "profile", "graph", "projection")
    if evidence_strength == "candidate":
        return action_type in ("projection",)
    return False


# ======================================================================
# ADR 0072 Slice 2: Tool Groups (for before_model_callback filtering)
# ======================================================================

# Tool names grouped by latency and capability scope.
# Fast: inspection / read-only — safe for any budget.
_FAST_TOOLS: frozenset[str] = frozenset({
    "list_papers", "list_concepts", "paper_brief",
    "get_user_profile", "get_tutor_progress",
    "list_personal_notes", "get_personal_note",
    "list_people", "get_person",
    "get_concept_graph", "get_note_backlinks",
    "render_note_markdown",
})

# Safe: moderate-latency — search, evidence, recommendations.
_SAFE_TOOLS: frozenset[str] = frozenset({
    "ingest_paper", "ingest_all_papers",
    "rename_paper", "organize_papers",
    "search_evidence", "search_personal_notes",
    "search_people", "search_web",
    "compare_papers", "make_study_guide",
    "recommend_reconnections", "suggest_concept_merges",
    "knowledge_self_audit",
})

# Write: durable writes — gated by budget.
_WRITE_TOOLS: frozenset[str] = frozenset({
    "save_personal_note", "edit_personal_note",
    "delete_personal_note", "reject_note_card",
    "reject_note_concept", "import_markdown_notes",
    "learn_from_user_message", "set_user_preference",
    "self_audit_correction",
    "add_person", "add_relationship_note",
    "log_relationship_interaction", "forget_person",
})

# Heavy: multi-step, synthesis, tutor, grill — deep only.
_HEAVY_TOOLS: frozenset[str] = frozenset({
    "ingest_paper", "ingest_all_papers",
    "rename_paper", "delete_paper", "organize_papers",
    "adaptive_grill", "respond_to_adaptive_grill",
    "record_tutor_answer",
})


def _allowed_tool_names(budget: str) -> frozenset[str]:
    """Return the set of tool names allowed for a given budget tier."""
    budget = _validate_tier(budget)
    if budget == FAST:
        return _FAST_TOOLS
    if budget == BALANCED:
        return _FAST_TOOLS | _SAFE_TOOLS | _WRITE_TOOLS
    # deep: everything
    return _FAST_TOOLS | _SAFE_TOOLS | _WRITE_TOOLS | _HEAVY_TOOLS


# ======================================================================
# ADR 0072 Slice 2: before_model_callback builder
# ======================================================================


def build_before_model_callback():
    """Return an async callback for ADK Agent.before_model_callback.

    The callback:
    1. Infers the budget from the session context.
    2. Filters tools_dict to only allowed tools for that budget.
    3. Adjusts generation config (max_tokens, temperature) per budget.
    4. Logs diagnostics outside prompt context.

    Usage in agent.py::

        from .agent_runtime.dynamic_context import build_before_model_callback
        root_agent = Agent(
            ...,
            before_model_callback=build_before_model_callback(),
        )
    """

    async def _callback(callback_context: Any, llm_request: Any) -> Any:
        try:
            # Budget inference: use the latest user text from the request.
            budget = BALANCED
            try:
                contents = getattr(llm_request, "contents", [])
                if contents:
                    last_content = contents[-1]
                    text = ""
                    if hasattr(last_content, "parts"):
                        text = " ".join(
                            getattr(p, "text", "") for p in last_content.parts
                            if hasattr(p, "text")
                        )
                    elif isinstance(last_content, str):
                        text = last_content
                    if text:
                        budget = _infer_performance_budget_from_text(text)
            except Exception:
                pass  # fall back to balanced

            # Tool filtering.
            allowed = _allowed_tool_names(budget)
            tools_dict = getattr(llm_request, "tools_dict", None)
            if tools_dict is not None:
                filtered = 0
                for name in list(tools_dict):
                    if name not in allowed:
                        del tools_dict[name]
                        filtered += 1
                logger.debug(
                    "budget_tool_filter: budget=%s allowed=%d filtered=%d",
                    budget, len(allowed), filtered,
                )

            # Generation controls.
            config = getattr(llm_request, "config", None)
            if config is not None:
                if budget == FAST:
                    # Shorter output, slightly faster.
                    try:
                        setattr(config, "max_output_tokens", 1024)
                    except Exception:
                        pass
                    try:
                        setattr(config, "temperature", 0.3)
                    except Exception:
                        pass
                elif budget == DEEP:
                    # Larger output, more creative.
                    try:
                        setattr(config, "max_output_tokens", 8192)
                    except Exception:
                        pass
                # balanced: use defaults (no change).

        except Exception:
            pass  # never block the model call on a callback error

        return None  # None = proceed with model call

    return _callback
