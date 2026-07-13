"""Cognitive Support policies — A4 from implementation-plan-regulation-pkm.md.

ADR 0067: Cognitive Adaptation — ADHD-Aware Instruction + Session Metadata.
ADR 0105: Tutoring Uses Bounded, Capacity-Aware Study Sessions.
ADR 0126: Context Overflow Preserves Intent, Safety, and Confirmed State.

Capacity-aware chunking, choice limits, pause recovery, question parking,
and commitment framing as user-correctable preferences — not diagnosis.
Support changes delivery, not factual conclusions or permissions.
Settings can be inspected and corrected.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import USER_MODEL_DIR, ensure_dirs, now_iso

# ── Path ─────────────────────────────────────────────────────────────

COGNITIVE_SUPPORT_PATH = USER_MODEL_DIR / "cognitive_support.json"


# ── Domain types ─────────────────────────────────────────────────────


class CapacityLevel(str, Enum):
    """Current cognitive capacity — user-assessed, not diagnosed."""
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNKNOWN = "unknown"


class ChunkSize(str, Enum):
    """Preferred chunk size for information delivery."""
    SMALL = "small"  # 1-2 points at a time
    MEDIUM = "medium"  # 3-5 points
    LARGE = "large"  # 6+ points
    ADAPTIVE = "adaptive"  # adjust based on capacity


class ChoiceLimit(str, Enum):
    """Maximum choices presented at once."""
    MINIMAL = "minimal"  # 2-3 options
    STANDARD = "standard"  # 4-6 options
    EXPANDED = "expanded"  # 7+ options


# ── Policy schema ────────────────────────────────────────────────────


@dataclass
class CognitiveSupportProfile:
    """User-correctable cognitive support preferences.

    These are preferences that affect how information is delivered,
    not factual conclusions about the user. Every field is inspectable
    and correctable by the Owner.
    """

    schema_version: int = 1
    updated_at: str = field(default_factory=now_iso)

    # ── Capacity-aware chunking ──────────────────────────────────────
    default_capacity: CapacityLevel = CapacityLevel.UNKNOWN
    preferred_chunk_size: ChunkSize = ChunkSize.ADAPTIVE
    max_points_per_chunk: int = 5
    signal_structure_upfront: bool = True  # "Three things to know about X"

    # ── Choice limits ────────────────────────────────────────────────
    choice_limit: ChoiceLimit = ChoiceLimit.STANDARD
    max_choices_shown: int = 5

    # ── Pause recovery ───────────────────────────────────────────────
    reanchor_after_minutes: int = 30  # re-anchor after this many minutes
    always_reanchor_cross_day: bool = True
    reanchor_phrasing: str = (
        "You were exploring {topic}. Want to continue or pivot?"
    )

    # ── Question parking ─────────────────────────────────────────────
    enable_question_parking: bool = True
    max_parked_questions: int = 10

    # ── Commitment framing ───────────────────────────────────────────
    offer_next_actions: bool = True
    max_next_actions: int = 3
    next_actions_phrasing: str = (
        "Here's what you can do with this:"
    )

    # ── Pacing ───────────────────────────────────────────────────────
    vary_pacing: bool = True
    ask_depth_preference: bool = True  # "Want me to go deeper or keep it brief?"

    # ── Comprehension checks ─────────────────────────────────────────
    check_comprehension: bool = False  # Off by default — user opt-in

    # ── Metadata ─────────────────────────────────────────────────────
    last_capacity_update: Optional[str] = None
    recovery_note: Optional[str] = None


# ── Parked questions ─────────────────────────────────────────────────


@dataclass
class ParkedQuestion:
    """A question the user asked but wants to return to later."""
    question_id: str
    question: str
    context: str  # what the user was exploring
    parked_at: str
    parked_until: Optional[str] = None  # optional re-surfacing time
    resolved: bool = False


# ── Profile management ───────────────────────────────────────────────


def _default_profile() -> CognitiveSupportProfile:
    """Return the default cognitive support profile."""
    return CognitiveSupportProfile()


def load_profile(
    path: Optional[Path] = None,
) -> CognitiveSupportProfile:
    """Load the cognitive support profile from disk."""
    profile_path = path or COGNITIVE_SUPPORT_PATH
    if not profile_path.exists():
        profile = _default_profile()
        save_profile(profile, path=path)
        return profile

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        return _dict_to_profile(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        profile = _default_profile()
        profile.recovery_note = (
            "cognitive_support.json was unreadable and defaults were restored."
        )
        save_profile(profile, path=path)
        return profile


def save_profile(
    profile: CognitiveSupportProfile,
    path: Optional[Path] = None,
) -> None:
    """Persist the cognitive support profile to disk."""
    ensure_dirs()
    profile_path = path or COGNITIVE_SUPPORT_PATH
    profile.updated_at = now_iso()
    profile_path.write_text(
        json.dumps(_profile_to_dict(profile), indent=2),
        encoding="utf-8",
    )


def inspect_profile(
    profile: Optional[CognitiveSupportProfile] = None,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return an inspectable view of the cognitive support profile.

    Every setting is explained in plain language. No diagnostic language.
    """
    p = profile or load_profile(path)

    return {
        "schema_version": p.schema_version,
        "updated_at": p.updated_at,
        "capacity": {
            "default_capacity": {
                "value": p.default_capacity.value,
                "description": (
                    "Your current mental bandwidth. 'Unknown' means the agent "
                    "will ask or infer from context. This is a preference, not a diagnosis."
                ),
            },
            "preferred_chunk_size": {
                "value": p.preferred_chunk_size.value,
                "description": (
                    "How many ideas to present at once. 'Adaptive' adjusts "
                    "based on your stated or inferred capacity."
                ),
            },
            "max_points_per_chunk": {
                "value": p.max_points_per_chunk,
                "description": "Maximum bullet points or ideas in one response section.",
            },
            "signal_structure_upfront": {
                "value": p.signal_structure_upfront,
                "description": (
                    "When on, the agent previews structure: 'Three things to know about X.'"
                ),
            },
        },
        "choices": {
            "choice_limit": {
                "value": p.choice_limit.value,
                "description": "Maximum options presented when offering choices.",
            },
            "max_choices_shown": {
                "value": p.max_choices_shown,
                "description": "Hard cap on options shown at once.",
            },
        },
        "pause_recovery": {
            "reanchor_after_minutes": {
                "value": p.reanchor_after_minutes,
                "description": (
                    "After this many minutes of inactivity, the agent re-anchors "
                    "you to what you were doing."
                ),
            },
            "always_reanchor_cross_day": {
                "value": p.always_reanchor_cross_day,
                "description": "Always re-anchor when resuming on a different day.",
            },
            "reanchor_phrasing": {
                "value": p.reanchor_phrasing,
                "description": "The phrase used to re-anchor. {topic} is replaced with context.",
            },
        },
        "question_parking": {
            "enable_question_parking": {
                "value": p.enable_question_parking,
                "description": (
                    "When on, you can park questions to return to later without "
                    "losing your current thread."
                ),
            },
            "max_parked_questions": {
                "value": p.max_parked_questions,
                "description": "Maximum questions that can be parked at once.",
            },
        },
        "commitment_framing": {
            "offer_next_actions": {
                "value": p.offer_next_actions,
                "description": (
                    "When on, the agent suggests concrete next actions after "
                    "explanations. You control what action to take."
                ),
            },
            "max_next_actions": {
                "value": p.max_next_actions,
                "description": "Maximum next actions suggested at once.",
            },
            "next_actions_phrasing": {
                "value": p.next_actions_phrasing,
                "description": "The phrase used to introduce next actions.",
            },
        },
        "pacing": {
            "vary_pacing": {
                "value": p.vary_pacing,
                "description": "Adjust response depth based on engagement signals.",
            },
            "ask_depth_preference": {
                "value": p.ask_depth_preference,
                "description": (
                    "When on, the agent occasionally asks whether you want "
                    "more depth or to keep it brief."
                ),
            },
        },
        "comprehension": {
            "check_comprehension": {
                "value": p.check_comprehension,
                "description": (
                    "When on, the agent checks if you understood before "
                    "continuing. Off by default — opt in if helpful."
                ),
            },
        },
    }


# ── Profile updates ──────────────────────────────────────────────────


def update_profile(
    updates: Dict[str, Any],
    profile: Optional[CognitiveSupportProfile] = None,
    path: Optional[Path] = None,
) -> CognitiveSupportProfile:
    """Update the cognitive support profile with validated changes.

    Only known fields are updated. Unknown fields are silently ignored.
    Returns the updated profile.
    """
    p = profile or load_profile(path)

    valid_fields = {
        "default_capacity", "preferred_chunk_size", "max_points_per_chunk",
        "signal_structure_upfront", "choice_limit", "max_choices_shown",
        "reanchor_after_minutes", "always_reanchor_cross_day",
        "reanchor_phrasing", "enable_question_parking",
        "max_parked_questions", "offer_next_actions", "max_next_actions",
        "next_actions_phrasing", "vary_pacing", "ask_depth_preference",
        "check_comprehension",
    }

    for key, value in updates.items():
        if key not in valid_fields:
            continue

        if key == "default_capacity":
            try:
                p.default_capacity = CapacityLevel(value)
            except ValueError:
                pass

        elif key == "preferred_chunk_size":
            try:
                p.preferred_chunk_size = ChunkSize(value)
            except ValueError:
                pass

        elif key == "choice_limit":
            try:
                p.choice_limit = ChoiceLimit(value)
            except ValueError:
                pass

        elif key == "last_capacity_update":
            p.last_capacity_update = str(value)

        elif isinstance(value, bool):
            setattr(p, key, value)

        elif isinstance(value, int) and value >= 0:
            setattr(p, key, value)

        elif isinstance(value, str):
            setattr(p, key, value)

    save_profile(p, path=path)
    return p


# ── Capacity-aware chunking ──────────────────────────────────────────


def chunk_points(
    points: List[str],
    profile: Optional[CognitiveSupportProfile] = None,
    capacity: Optional[CapacityLevel] = None,
) -> List[List[str]]:
    """Split a list of points into capacity-aware chunks.

    Uses the profile's preferred chunk size and capacity to determine
    how many points per chunk. Returns a list of chunks.
    """
    p = profile or load_profile()
    cap = capacity or p.default_capacity

    points_per_chunk = p.max_points_per_chunk

    if p.preferred_chunk_size == ChunkSize.SMALL:
        points_per_chunk = min(points_per_chunk, 2)
    elif p.preferred_chunk_size == ChunkSize.LARGE:
        points_per_chunk = min(points_per_chunk, 8)
    elif p.preferred_chunk_size == ChunkSize.ADAPTIVE:
        if cap == CapacityLevel.LOW:
            points_per_chunk = min(points_per_chunk, 2)
        elif cap == CapacityLevel.HIGH:
            points_per_chunk = min(points_per_chunk, 6)
        else:
            points_per_chunk = min(points_per_chunk, 4)

    chunks: List[List[str]] = []
    for i in range(0, len(points), points_per_chunk):
        chunks.append(points[i:i + points_per_chunk])

    return chunks


# ── Choice limiting ──────────────────────────────────────────────────


def limit_choices(
    options: List[str],
    profile: Optional[CognitiveSupportProfile] = None,
) -> List[str]:
    """Limit the number of choices presented based on profile settings.

    ADR 0105: Choice limits prevent overwhelming the user.
    """
    p = profile or load_profile()

    limit = p.max_choices_shown
    if p.choice_limit == ChoiceLimit.MINIMAL:
        limit = min(limit, 3)
    elif p.choice_limit == ChoiceLimit.EXPANDED:
        limit = min(limit, 8)

    return options[:limit]


# ── Pause recovery ───────────────────────────────────────────────────


def _parse_iso_utc(ts: str):
    """Parse an ISO timestamp to a UTC datetime. Handles Z suffix for Python < 3.11."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def should_reanchor(
    current_time: Optional[str] = None,
    last_active_at: Optional[str] = None,
    profile: Optional[CognitiveSupportProfile] = None,
) -> Dict[str, Any]:
    """Determine if the agent should re-anchor the user after a pause.

    ADR 0067: Re-anchor after 30+ minutes or cross-day resume.
    Returns a decision with the re-anchoring phrase if needed.
    """
    p = profile or load_profile()

    if current_time is None:
        current_time = now_iso()
    if last_active_at is None:
        return {"should_reanchor": False, "reason": "no previous activity"}

    try:
        cur = _parse_iso_utc(current_time)
        last = _parse_iso_utc(last_active_at)

        diff_minutes = (cur - last).total_seconds() / 60

        # Cross-day check
        if p.always_reanchor_cross_day and cur.date() != last.date():
            return {
                "should_reanchor": True,
                "reason": f"cross-day resume ({diff_minutes:.0f} min gap)",
                "phrasing": p.reanchor_phrasing,
            }

        # Time-based check
        if diff_minutes >= p.reanchor_after_minutes:
            return {
                "should_reanchor": True,
                "reason": f"{diff_minutes:.0f} min gap (threshold: {p.reanchor_after_minutes})",
                "phrasing": p.reanchor_phrasing,
            }

        return {"should_reanchor": False, "reason": f"only {diff_minutes:.0f} min gap"}

    except (ValueError, TypeError):
        return {"should_reanchor": False, "reason": "could not parse timestamps"}


# ── Question parking ─────────────────────────────────────────────────


def park_question(
    question: str,
    context: str,
    parked_questions: Optional[List[ParkedQuestion]] = None,
    profile: Optional[CognitiveSupportProfile] = None,
    until: Optional[str] = None,
) -> Dict[str, Any]:
    """Park a question for later review.

    ADR 0105: Question Parking Lot for deferring questions without
    losing the current thread.
    """
    p = profile or load_profile()
    parked = parked_questions or []

    if not p.enable_question_parking:
        return {"status": "error", "message": "Question parking is disabled"}

    if len(parked) >= p.max_parked_questions:
        return {
            "status": "error",
            "message": f"Parking lot full ({len(parked)}/{p.max_parked_questions})",
        }

    import uuid
    pq = ParkedQuestion(
        question_id=f"pq_{uuid.uuid4().hex[:8]}",
        question=question,
        context=context,
        parked_at=now_iso(),
        parked_until=until,
    )
    parked.append(pq)

    return {
        "status": "ok",
        "question_id": pq.question_id,
        "total_parked": len(parked),
        "max_parked": p.max_parked_questions,
    }


def get_parked_questions(
    parked_questions: List[ParkedQuestion],
    include_resolved: bool = False,
) -> List[ParkedQuestion]:
    """Get the current list of parked questions."""
    if include_resolved:
        return list(parked_questions)
    return [q for q in parked_questions if not q.resolved]


def resolve_parked_question(
    question_id: str,
    parked_questions: List[ParkedQuestion],
) -> Dict[str, Any]:
    """Mark a parked question as resolved."""
    for q in parked_questions:
        if q.question_id == question_id:
            q.resolved = True
            return {"status": "ok", "question_id": question_id, "resolved": True}
    return {"status": "error", "message": f"Question {question_id} not found"}


# ── Commitment framing ───────────────────────────────────────────────


def frame_next_actions(
    actions: List[str],
    profile: Optional[CognitiveSupportProfile] = None,
) -> Dict[str, Any]:
    """Frame next actions as user-controlled options — not directives.

    ADR 0105: One closing Commitment, user-correctable.
    ADR 0067: Offer concrete next actions after meaningful answers.
    """
    p = profile or load_profile()

    if not p.offer_next_actions:
        return {"offer_actions": False, "actions": []}

    limited = actions[:p.max_next_actions]
    return {
        "offer_actions": True,
        "phrasing": p.next_actions_phrasing,
        "actions": [
            {"index": i + 1, "action": action}
            for i, action in enumerate(limited)
        ],
    }


# ── Serialization ────────────────────────────────────────────────────


def _profile_to_dict(p: CognitiveSupportProfile) -> Dict[str, Any]:
    """Serialize a CognitiveSupportProfile to a plain dict."""
    return {
        "schema_version": p.schema_version,
        "updated_at": p.updated_at,
        "default_capacity": p.default_capacity.value,
        "preferred_chunk_size": p.preferred_chunk_size.value,
        "max_points_per_chunk": p.max_points_per_chunk,
        "signal_structure_upfront": p.signal_structure_upfront,
        "choice_limit": p.choice_limit.value,
        "max_choices_shown": p.max_choices_shown,
        "reanchor_after_minutes": p.reanchor_after_minutes,
        "always_reanchor_cross_day": p.always_reanchor_cross_day,
        "reanchor_phrasing": p.reanchor_phrasing,
        "enable_question_parking": p.enable_question_parking,
        "max_parked_questions": p.max_parked_questions,
        "offer_next_actions": p.offer_next_actions,
        "max_next_actions": p.max_next_actions,
        "next_actions_phrasing": p.next_actions_phrasing,
        "vary_pacing": p.vary_pacing,
        "ask_depth_preference": p.ask_depth_preference,
        "check_comprehension": p.check_comprehension,
        "last_capacity_update": p.last_capacity_update,
        "recovery_note": p.recovery_note,
    }


def _dict_to_profile(d: Dict[str, Any]) -> CognitiveSupportProfile:
    """Deserialize a dict to a CognitiveSupportProfile."""
    return CognitiveSupportProfile(
        schema_version=int(d.get("schema_version", 1)),
        updated_at=str(d.get("updated_at", "")),
        default_capacity=CapacityLevel(d.get("default_capacity", "unknown")),
        preferred_chunk_size=ChunkSize(d.get("preferred_chunk_size", "adaptive")),
        max_points_per_chunk=int(d.get("max_points_per_chunk", 5)),
        signal_structure_upfront=bool(d.get("signal_structure_upfront", True)),
        choice_limit=ChoiceLimit(d.get("choice_limit", "standard")),
        max_choices_shown=int(d.get("max_choices_shown", 5)),
        reanchor_after_minutes=int(d.get("reanchor_after_minutes", 30)),
        always_reanchor_cross_day=bool(d.get("always_reanchor_cross_day", True)),
        reanchor_phrasing=str(d.get("reanchor_phrasing", "You were exploring {topic}. Want to continue or pivot?")),
        enable_question_parking=bool(d.get("enable_question_parking", True)),
        max_parked_questions=int(d.get("max_parked_questions", 10)),
        offer_next_actions=bool(d.get("offer_next_actions", True)),
        max_next_actions=int(d.get("max_next_actions", 3)),
        next_actions_phrasing=str(d.get("next_actions_phrasing", "Here's what you can do with this:")),
        vary_pacing=bool(d.get("vary_pacing", True)),
        ask_depth_preference=bool(d.get("ask_depth_preference", True)),
        check_comprehension=bool(d.get("check_comprehension", False)),
        last_capacity_update=d.get("last_capacity_update"),
        recovery_note=d.get("recovery_note"),
    )
