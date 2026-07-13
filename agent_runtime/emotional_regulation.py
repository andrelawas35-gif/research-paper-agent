"""Emotional Regulation module — R1-R5 from implementation-plan-regulation-pkm.md.

ADR 0073: Regulation Mode Optimizes for User-Aligned Action.
ADR 0074: Regulation Data Requires an Explicit Session.
ADR 0075: Isolate Regulation History from the General User Model.
ADR 0083: Emergency Regulation Is an Explicit State Machine.
ADR 0084: Safety Branch Overrides Coaching and Minimizes Retention.
ADR 0086: Personal Rules Have Explicit Strength and Exceptions.
ADR 0090: Separate Regulation, Values, Cognitive Support, and Orientation Modules.
ADR 0121: Regulation Has a Deterministic Offline Protocol.

This module owns trigger sessions, internal sequences, outcomes, personal
regulation rules, the safety branch, and the deterministic offline protocol.
It remains separate from relationship_management.py: relationship records
describe people and interactions; Regulation records describe the Owner's
internal sequence.

The companion's objective is not to decide whether a feared action is true.
It helps the Owner choose the best user-aligned next action, even when
truth remains uncertain:

    trigger → facts → interpretation → emotion → urge → action → outcome
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .event_envelope import Domain, EventEnvelope, Sensitivity
from .stores import RegulationStore, StoreBoundaryError

# ═══════════════════════════════════════════════════════════════════════
# R1 — Regulation Records
# ═══════════════════════════════════════════════════════════════════════


# ── Enums ─────────────────────────────────────────────────────────────


class SessionState(str, Enum):
    """States of a Regulation Session (ADR 0083)."""
    CREATED = "created"               # session opened, safety screen pending
    SAFETY_SCREEN = "safety_screen"   # safety check in progress
    ACTIVE = "active"                 # regulation coaching active
    SAFETY_BRANCH = "safety_branch"   # safety override active (ADR 0084)
    COMPLETED = "completed"           # session finished normally
    EXPIRED = "expired"               # session timed out without completion


class RuleStrength(str, Enum):
    """Strength of a Personal Regulation Rule (ADR 0086)."""
    HARD_GUARDRAIL = "hard_guardrail"        # non-overridable (except by Owner outside activated state)
    DEFAULT_PRINCIPLE = "default_principle"  # strong default, contextual exceptions allowed
    REFLECTION_PROMPT = "reflection_prompt"  # suggestion, gently surfaced


class ConfirmationState(str, Enum):
    """Whether a rule, value, or orientation item has been explicitly confirmed."""
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    UNDER_REVIEW = "under_review"
    RETIRED = "retired"


class SafetyCategory(str, Enum):
    """Categories for safety branch routing (ADR 0084)."""
    SELF_HARM = "self_harm"
    VIOLENCE = "violence"
    ABUSE = "abuse"
    IMMEDIATE_DANGER = "immediate_danger"
    NONE = "none"  # no safety concern detected


class EmotionLabel(str, Enum):
    """Standard emotion labels for structured capture."""
    ANGER = "anger"
    FEAR = "fear"
    SADNESS = "sadness"
    JEALOUSY = "jealousy"
    SHAME = "shame"
    GUILT = "guilt"
    ANXIETY = "anxiety"
    FRUSTRATION = "frustration"
    HURT = "hurt"
    DISAPPOINTMENT = "disappointment"
    LONELINESS = "loneliness"
    OVERWHELMED = "overwhelmed"
    CONFUSION = "confusion"
    NUMB = "numb"
    RELIEF = "relief"
    HOPE = "hope"
    GRATITUDE = "gratitude"
    OTHER = "other"


# ── Regulation Record Dataclasses ─────────────────────────────────────


@dataclass(frozen=True)
class Fact:
    """A reported observable event or circumstance, separate from interpretation.

    Facts are what a camera would record — not what the event means.
    """
    text: str
    certainty: float  # 0.0–1.0, user's confidence this happened as described
    source: str  # "user_report", "message_log", "other_observation"
    captured_at: str = field(default_factory=lambda: _now_iso())

    def __post_init__(self) -> None:
        if not 0.0 <= self.certainty <= 1.0:
            raise ValueError(f"certainty must be 0.0–1.0, got {self.certainty}")
        if not self.text.strip():
            raise ValueError("Fact text cannot be empty")


@dataclass(frozen=True)
class Interpretation:
    """A user-considered meaning of the facts — not a truth verdict.

    Multiple competing interpretations are allowed. The system never
    declares one as the truth.
    """
    text: str
    plausibility: float  # 0.0–1.0, user's estimate of how likely this is
    evidence_for: List[str] = field(default_factory=list)
    evidence_against: List[str] = field(default_factory=list)
    captured_at: str = field(default_factory=lambda: _now_iso())

    def __post_init__(self) -> None:
        if not 0.0 <= self.plausibility <= 1.0:
            raise ValueError(f"plausibility must be 0.0–1.0, got {self.plausibility}")
        if not self.text.strip():
            raise ValueError("Interpretation text cannot be empty")


@dataclass(frozen=True)
class Emotion:
    """A labeled emotional experience during the trigger session."""
    label: EmotionLabel
    intensity: int  # 1–10
    description: str = ""
    captured_at: str = field(default_factory=lambda: _now_iso())

    def __post_init__(self) -> None:
        if not 1 <= self.intensity <= 10:
            raise ValueError(f"intensity must be 1–10, got {self.intensity}")


@dataclass(frozen=True)
class Urge:
    """An impulse the user feels — recorded before action, not judged."""
    text: str
    strength: int  # 1–10
    captured_at: str = field(default_factory=lambda: _now_iso())

    def __post_init__(self) -> None:
        if not 1 <= self.strength <= 10:
            raise ValueError(f"strength must be 1–10, got {self.strength}")
        if not self.text.strip():
            raise ValueError("Urge text cannot be empty")


@dataclass(frozen=True)
class Action:
    """A chosen action — user-aligned, not system-prescribed."""
    text: str
    reversible: bool = True
    waiting_period_minutes: int = 0  # recommended pause before acting
    captured_at: str = field(default_factory=lambda: _now_iso())


@dataclass(frozen=True)
class Outcome:
    """What happened after the action — captured later."""
    text: str
    was_helpful: Optional[bool] = None
    captured_at: str = field(default_factory=lambda: _now_iso())


@dataclass(frozen=True)
class SafetyState:
    """Safety assessment for a regulation session (ADR 0084).

    If category is not NONE, the safety branch overrides coaching.
    """
    category: SafetyCategory = SafetyCategory.NONE
    is_active: bool = False
    resources_provided: bool = False
    escalation_instructions_given: bool = False
    captured_at: str = field(default_factory=lambda: _now_iso())


@dataclass(frozen=True)
class PersonalRegulationRule:
    """An explicitly confirmed instruction for Regulation Mode (ADR 0086).

    Examples: "pause before sending another message", "separate facts from
    interpretations before deciding".
    """
    rule_id: str
    text: str
    strength: RuleStrength
    confirmation: ConfirmationState = ConfirmationState.UNCONFIRMED
    exceptions: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now_iso())
    updated_at: str = field(default_factory=lambda: _now_iso())
    review_after_outcomes: int = 5  # review after this many poor-outcome uses

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Rule text cannot be empty")

    def is_authoritative(self) -> bool:
        """Unconfirmed rules cannot authorize behavior."""
        return self.confirmation == ConfirmationState.CONFIRMED


# ── Trigger Session — the container ───────────────────────────────────


@dataclass(frozen=True)
class TriggerSession:
    """An explicitly started Regulation Session (ADR 0074, 0083).

    Ordinary conversation does not silently create one of these.
    A Private Check-In variant exists where data is ephemeral.
    """
    session_id: str
    owner_id: str
    state: SessionState = SessionState.CREATED
    is_private: bool = False  # True = Private Check-In, ephemeral

    # Sequence data (populated as session progresses)
    trigger_event: Optional[str] = None  # one-sentence description of what happened
    facts: List[Fact] = field(default_factory=list)
    interpretations: List[Interpretation] = field(default_factory=list)
    emotions: List[Emotion] = field(default_factory=list)
    urges: List[Urge] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    outcomes: List[Outcome] = field(default_factory=list)

    # Safety
    safety_state: SafetyState = field(default_factory=SafetyState)

    # Metadata
    sensitivity: Sensitivity = Sensitivity.RESTRICTED
    retention_days: int = 365  # default retention
    created_at: str = field(default_factory=lambda: _now_iso())
    completed_at: Optional[str] = None
    correlation_id: Optional[str] = None

    # Version for optimistic concurrency
    version: int = 1

    # Present only after raw session content has been compacted. This keeps
    # aggregate reflection signals available without reconstructing fake
    # actions, outcomes, or narrative content.
    compact_record: Optional["RegulationRecord"] = None

    def is_durable(self) -> bool:
        """Private check-ins are not added to durable regulation history."""
        return not self.is_private

    def is_safety_active(self) -> bool:
        """Returns True if the safety branch is currently overriding coaching."""
        return self.safety_state.is_active and self.safety_state.category != SafetyCategory.NONE


@dataclass(frozen=True)
class RegulationRecord:
    """Compact durable outcome of a completed Regulation Session.

    It deliberately excludes trigger narrative, facts, interpretations, urge
    text, action text, outcome text, names, and relationship specifics.
    """

    session_id: str
    owner_id: str
    emotion_labels: Tuple[EmotionLabel, ...]
    peak_emotion_intensity: int
    action_count: int
    reversible_action_count: int
    longest_wait_minutes: int
    helpful_outcome_count: int
    unhelpful_outcome_count: int
    safety_category: SafetyCategory
    safety_resources_provided: bool
    created_at: str
    completed_at: str
    retention_days: int
    source_session_version: int


def compact_regulation_record(session: TriggerSession) -> RegulationRecord:
    """Discard raw narrative and retain only approved reflection signals."""
    if session.is_private:
        raise ValueError("Private Check-Ins cannot become durable records")
    if session.state != SessionState.COMPLETED or session.completed_at is None:
        raise ValueError("Only completed Regulation Sessions can be compacted")

    previous = session.compact_record
    previous_labels = previous.emotion_labels if previous is not None else ()
    emotion_labels = tuple(dict.fromkeys(
        (*previous_labels, *(item.label for item in session.emotions))
    ))
    return RegulationRecord(
        session_id=session.session_id,
        owner_id=session.owner_id,
        emotion_labels=emotion_labels,
        peak_emotion_intensity=max(
            previous.peak_emotion_intensity if previous else 0,
            max((item.intensity for item in session.emotions), default=0),
        ),
        action_count=(previous.action_count if previous else 0) + len(session.actions),
        reversible_action_count=(
            (previous.reversible_action_count if previous else 0)
            + sum(item.reversible for item in session.actions)
        ),
        longest_wait_minutes=max(
            previous.longest_wait_minutes if previous else 0,
            max((item.waiting_period_minutes for item in session.actions), default=0),
        ),
        helpful_outcome_count=(previous.helpful_outcome_count if previous else 0) + sum(
            item.was_helpful is True for item in session.outcomes
        ),
        unhelpful_outcome_count=(previous.unhelpful_outcome_count if previous else 0) + sum(
            item.was_helpful is False for item in session.outcomes
        ),
        safety_category=(previous.safety_category if previous else session.safety_state.category),
        safety_resources_provided=(
            previous.safety_resources_provided
            if previous else session.safety_state.resources_provided
        ),
        created_at=previous.created_at if previous else session.created_at,
        completed_at=session.completed_at,
        retention_days=session.retention_days,
        source_session_version=session.version,
    )


# ═══════════════════════════════════════════════════════════════════════
# R2 — State Machine
# ═══════════════════════════════════════════════════════════════════════


# Valid transitions (ADR 0083)
_VALID_TRANSITIONS: Dict[SessionState, Set[SessionState]] = {
    SessionState.CREATED: {SessionState.SAFETY_SCREEN, SessionState.EXPIRED},
    SessionState.SAFETY_SCREEN: {SessionState.ACTIVE, SessionState.SAFETY_BRANCH, SessionState.EXPIRED},
    SessionState.ACTIVE: {SessionState.COMPLETED, SessionState.EXPIRED},
    SessionState.SAFETY_BRANCH: {SessionState.COMPLETED, SessionState.EXPIRED},
    SessionState.COMPLETED: set(),   # terminal
    SessionState.EXPIRED: set(),     # terminal
}


class RegulationStateError(ValueError):
    """Raised when an invalid state transition is attempted."""


def _transition(session: TriggerSession, target: SessionState) -> TriggerSession:
    """Validate and apply a state transition. Returns a new (immutable) session."""
    allowed = _VALID_TRANSITIONS.get(session.state, set())
    if target not in allowed:
        raise RegulationStateError(
            f"Invalid transition: {session.state.value} → {target.value}. "
            f"Allowed: {[s.value for s in allowed]}"
        )
    return _new_version(
        session,
        state=target,
        completed_at=_now_iso() if target in (SessionState.COMPLETED, SessionState.EXPIRED) else session.completed_at,
    )


def _new_version(session: TriggerSession, **overrides: Any) -> TriggerSession:
    """Create a new version of a session with incremented version."""
    kwargs: Dict[str, Any] = {
        "session_id": session.session_id,
        "owner_id": session.owner_id,
        "state": session.state,
        "is_private": session.is_private,
        "trigger_event": session.trigger_event,
        "facts": session.facts,
        "interpretations": session.interpretations,
        "emotions": session.emotions,
        "urges": session.urges,
        "actions": session.actions,
        "outcomes": session.outcomes,
        "safety_state": session.safety_state,
        "sensitivity": session.sensitivity,
        "retention_days": session.retention_days,
        "created_at": session.created_at,
        "completed_at": session.completed_at,
        "correlation_id": session.correlation_id,
        "version": session.version + 1,
        "compact_record": session.compact_record,
    }
    kwargs.update(overrides)
    return TriggerSession(**kwargs)


# ── Public state machine API ──────────────────────────────────────────


def start_trigger_check_in(
    owner_id: str,
    trigger_event: str,
    is_private: bool = False,
    session_id: Optional[str] = None,
) -> TriggerSession:
    """Create a new Regulation Session (ADR 0074).

    Args:
        owner_id: The user who owns this session.
        trigger_event: One-sentence description of what triggered this check-in.
        is_private: If True, session is a Private Check-In (ephemeral).
        session_id: Optional pre-generated ID (for idempotency).

    Returns:
        A new TriggerSession in CREATED state.

    Raises:
        ValueError: If trigger_event is empty.
    """
    if not trigger_event.strip():
        raise ValueError("trigger_event cannot be empty")

    sid = session_id or _new_session_id()
    return TriggerSession(
        session_id=sid,
        owner_id=owner_id,
        trigger_event=trigger_event.strip(),
        is_private=is_private,
        state=SessionState.CREATED,
    )


def record_trigger_response(
    session: TriggerSession,
    *,
    facts: Optional[List[Fact]] = None,
    interpretations: Optional[List[Interpretation]] = None,
    emotions: Optional[List[Emotion]] = None,
    urges: Optional[List[Urge]] = None,
) -> TriggerSession:
    """Record the user's structured response to a trigger.

    Only valid in ACTIVE state. Adds facts, interpretations, emotions,
    and urges to the session. Duplicate content is appended (idempotency
    is the caller's responsibility via correlation_id).

    Returns a new version of the session.
    """
    if session.state != SessionState.ACTIVE:
        raise RegulationStateError(
            f"Cannot record trigger response in state {session.state.value}. "
            f"Session must be ACTIVE."
        )

    new_facts = list(session.facts) + (facts or [])
    new_interpretations = list(session.interpretations) + (interpretations or [])
    new_emotions = list(session.emotions) + (emotions or [])
    new_urges = list(session.urges) + (urges or [])

    return _new_version(
        session,
        facts=new_facts,
        interpretations=new_interpretations,
        emotions=new_emotions,
        urges=new_urges,
    )


def complete_trigger_check_in(
    session: TriggerSession,
    *,
    actions: Optional[List[Action]] = None,
    outcomes: Optional[List[Outcome]] = None,
) -> TriggerSession:
    """Complete a Regulation Session.

    Transitions from ACTIVE or SAFETY_BRANCH to COMPLETED.
    Records chosen actions and/or outcomes.

    Returns a new version of the session.
    """
    if session.state not in (SessionState.ACTIVE, SessionState.SAFETY_BRANCH):
        raise RegulationStateError(
            f"Cannot complete session in state {session.state.value}"
        )

    new_actions = list(session.actions) + (actions or [])
    new_outcomes = list(session.outcomes) + (outcomes or [])

    session = _new_version(session, actions=new_actions, outcomes=new_outcomes)
    return _transition(session, SessionState.COMPLETED)


def begin_safety_screen(session: TriggerSession) -> TriggerSession:
    """Begin the safety screen for a newly created session.

    Transitions from CREATED to SAFETY_SCREEN.
    Call complete_safety_screen() after the safety assessment.
    """
    if session.state != SessionState.CREATED:
        raise RegulationStateError(
            f"Cannot begin safety screen in state {session.state.value}. "
            f"Session must be CREATED."
        )
    return _transition(session, SessionState.SAFETY_SCREEN)


def complete_safety_screen(
    session: TriggerSession,
    safety_category: SafetyCategory,
) -> TriggerSession:
    """Complete the safety screen and route to ACTIVE or SAFETY_BRANCH.

    Must be called from SAFETY_SCREEN state.
    """
    if session.state != SessionState.SAFETY_SCREEN:
        raise RegulationStateError(
            f"Cannot complete safety screen in state {session.state.value}"
        )

    safety = SafetyState(
        category=safety_category,
        is_active=(safety_category != SafetyCategory.NONE),
        captured_at=_now_iso(),
    )

    target = SessionState.SAFETY_BRANCH if safety_category != SafetyCategory.NONE else SessionState.ACTIVE
    session = _new_version(session, safety_state=safety)
    return _transition(session, target)


def expire_session(session: TriggerSession) -> TriggerSession:
    """Expire an incomplete session."""
    if session.state in (SessionState.COMPLETED, SessionState.EXPIRED):
        raise RegulationStateError(
            f"Cannot expire session in terminal state {session.state.value}"
        )
    return _transition(session, SessionState.EXPIRED)


# ═══════════════════════════════════════════════════════════════════════
# R3 — Deterministic Emergency Protocol (ADR 0121)
# ═══════════════════════════════════════════════════════════════════════


# Built-in non-overridable safety constraints (ADR 0086)
_NON_OVERRIDABLE_SAFETY_RULES: List[str] = [
    "Never suggest or encourage surveillance of another person.",
    "Never suggest or encourage retaliation.",
    "Never suggest or encourage coercion.",
    "Never suggest or encourage repeated interrogation.",
    "Never make a definitive truth verdict about another person's motives.",
    "Never diagnose or label another person.",
]

# Local emergency resources (language: firm, non-reassuring)
_DETERMINISTIC_FLOW_SCRIPT: List[Dict[str, str]] = [
    {
        "step": "trigger",
        "prompt": "Describe what happened in one sentence. Just the observable event — "
                  "what would a camera record?",
    },
    {
        "step": "known_facts",
        "prompt": "List the facts you know for certain right now. Separate what you "
                  "observed from what you're assuming.",
    },
    {
        "step": "interpretation",
        "prompt": "What are you afraid this means? Write down the feared meaning. "
                  "Then list at least one alternative interpretation that doesn't "
                  "assume bad intent.",
    },
    {
        "step": "emotion_urge",
        "prompt": "Name the strongest emotion you're feeling right now. What is the "
                  "urge — what do you want to do immediately?",
    },
    {
        "step": "reversible_action",
        "prompt": "What is one reversible action you can take in the next 30 minutes "
                  "that supports your long-term well-being? Choose something you can "
                  "undo if you change your mind.",
    },
    {
        "step": "waiting_interval",
        "prompt": "Wait at least 30 minutes before taking any irreversible action. "
                  "The feeling is real; the feared outcome may not be. You don't have "
                  "to decide the truth right now to choose what protects you.",
    },
]


def get_deterministic_protocol() -> List[Dict[str, str]]:
    """Return the deterministic offline regulation flow (ADR 0121).

    This protocol is used when:
    - The external model is unavailable, timed out, or rate-limited.
    - The model output fails structured validation.
    - Spend limits are reached.

    It never:
    - Makes a truth verdict about another person's motives.
    - Suggests surveillance, retaliation, coercion, or repeated interrogation.
    - Diagnoses or labels another person.

    Returns:
        List of step dicts with 'step' and 'prompt' keys.
    """
    return list(_DETERMINISTIC_FLOW_SCRIPT)


def get_non_overridable_safety_rules() -> List[str]:
    """Return the built-in safety rules that cannot be edited or disabled."""
    return list(_NON_OVERRIDABLE_SAFETY_RULES)


# ═══════════════════════════════════════════════════════════════════════
# R4 — Safety Branch (ADR 0084)
# ═══════════════════════════════════════════════════════════════════════


# Safety branch resources — location-agnostic, authoritative
_SAFETY_RESOURCES: Dict[SafetyCategory, Dict[str, str]] = {
    SafetyCategory.SELF_HARM: {
        "message": (
            "If you're thinking about hurting yourself, please reach out now. "
            "You don't have to go through this alone."
        ),
        "international": "Find a crisis line at https://findahelpline.com",
        "us": "Call or text 988 (Suicide & Crisis Lifeline)",
        "ph": "Call 1553 (National Center for Mental Health Crisis Hotline)",
    },
    SafetyCategory.VIOLENCE: {
        "message": (
            "If you or someone else is in immediate danger, contact emergency "
            "services now. Your safety is the priority."
        ),
        "international": "Local emergency number varies by country.",
        "us": "Call 911",
        "ph": "Call 911 or 117",
    },
    SafetyCategory.ABUSE: {
        "message": (
            "If you're experiencing abuse, you deserve support. You are not alone "
            "and it is not your fault."
        ),
        "international": "Find resources at https://www.hotpeachpages.net",
        "us": "National Domestic Violence Hotline: 1-800-799-7233",
        "ph": "PNP Women and Children Protection Center: 177 (Aleng Pulis hotline)",
    },
    SafetyCategory.IMMEDIATE_DANGER: {
        "message": (
            "Your immediate safety is the only priority right now. Contact emergency "
            "services or go to a safe location."
        ),
        "international": "Contact local emergency services.",
        "us": "Call 911",
        "ph": "Call 911 or 117",
    },
    SafetyCategory.NONE: {
        "message": "",
        "international": "",
        "us": "",
        "ph": "",
    },
}

# Categories that block all coaching and identity learning
_SAFETY_BLOCK_CATEGORIES: Set[SafetyCategory] = {
    SafetyCategory.SELF_HARM,
    SafetyCategory.VIOLENCE,
    SafetyCategory.ABUSE,
    SafetyCategory.IMMEDIATE_DANGER,
}


def get_safety_resources(category: SafetyCategory) -> Dict[str, str]:
    """Return safety resources for a given category.

    Returns empty dict for SafetyCategory.NONE.
    """
    return dict(_SAFETY_RESOURCES.get(category, _SAFETY_RESOURCES[SafetyCategory.NONE]))


def is_safety_blocking(category: SafetyCategory) -> bool:
    """Returns True if this category blocks coaching and identity learning."""
    return category in _SAFETY_BLOCK_CATEGORIES


def create_safety_branch_response(category: SafetyCategory) -> Dict[str, Any]:
    """Build the safety branch response for a given category.

    This is the code-owned response that overrides all coaching when
    the safety screen detects a safety concern (ADR 0084).

    Returns:
        Dict with 'safety_active', 'category', 'message', 'resources',
        and 'next_steps'.
    """
    resources = get_safety_resources(category)
    return {
        "safety_active": True,
        "category": category.value,
        "message": resources.get("message", ""),
        "resources": {
            "international": resources.get("international", ""),
            "us": resources.get("us", ""),
            "ph": resources.get("ph", ""),
        },
        "next_steps": (
            "Regulation coaching is suspended while safety concerns are active. "
            "This session will not generate identity-level insights or pattern "
            "records. Only minimal safety metadata is retained."
        ),
        "retention_notice": (
            "Minimal safety metadata is retained for continuity of care. "
            "Crisis content is not used to generate Candidate Values, "
            "Regulation Patterns, or Cognitive Support conclusions."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════
# R5 — Personal Regulation Rules & Confirmed Orientation
# ═══════════════════════════════════════════════════════════════════════


# ── Rules management ──────────────────────────────────────────────────


def create_personal_rule(
    text: str,
    strength: RuleStrength = RuleStrength.DEFAULT_PRINCIPLE,
) -> PersonalRegulationRule:
    """Create a new personal regulation rule (unconfirmed).

    Rules start as UNCONFIRMED. Only CONFIRMED rules authorize behavior.
    """
    if not text.strip():
        raise ValueError("Rule text cannot be empty")
    return PersonalRegulationRule(
        rule_id=_new_rule_id(),
        text=text.strip(),
        strength=strength,
        confirmation=ConfirmationState.UNCONFIRMED,
    )


def confirm_rule(rule: PersonalRegulationRule) -> PersonalRegulationRule:
    """Confirm a personal regulation rule. Only confirmed rules are authoritative."""
    return PersonalRegulationRule(
        rule_id=rule.rule_id,
        text=rule.text,
        strength=rule.strength,
        confirmation=ConfirmationState.CONFIRMED,
        exceptions=rule.exceptions,
        created_at=rule.created_at,
        updated_at=_now_iso(),
        review_after_outcomes=rule.review_after_outcomes,
    )


def retire_rule(rule: PersonalRegulationRule) -> PersonalRegulationRule:
    """Retire a rule — it no longer guides behavior but remains in history."""
    return PersonalRegulationRule(
        rule_id=rule.rule_id,
        text=rule.text,
        strength=rule.strength,
        confirmation=ConfirmationState.RETIRED,
        exceptions=rule.exceptions,
        created_at=rule.created_at,
        updated_at=_now_iso(),
        review_after_outcomes=rule.review_after_outcomes,
    )


def update_rule_strength(
    rule: PersonalRegulationRule,
    strength: RuleStrength,
) -> PersonalRegulationRule:
    """Change a rule's strength level."""
    return PersonalRegulationRule(
        rule_id=rule.rule_id,
        text=rule.text,
        strength=strength,
        confirmation=rule.confirmation,
        exceptions=rule.exceptions,
        created_at=rule.created_at,
        updated_at=_now_iso(),
        review_after_outcomes=rule.review_after_outcomes,
    )


def add_rule_exception(
    rule: PersonalRegulationRule,
    exception: str,
) -> PersonalRegulationRule:
    """Add a contextual exception to a Default Principle."""
    if rule.strength == RuleStrength.HARD_GUARDRAIL:
        raise ValueError(
            "Hard guardrails cannot have exceptions added in an activated state. "
            "Review the guardrail outside a regulation session."
        )
    new_exceptions = list(rule.exceptions) + [exception.strip()]
    return PersonalRegulationRule(
        rule_id=rule.rule_id,
        text=rule.text,
        strength=rule.strength,
        confirmation=rule.confirmation,
        exceptions=new_exceptions,
        created_at=rule.created_at,
        updated_at=_now_iso(),
        review_after_outcomes=rule.review_after_outcomes,
    )


# ── Personal Orientation Snapshot (minimal, ADR 0081) ─────────────────


@dataclass(frozen=True)
class PersonalOrientationSnapshot:
    """Minimal task-scoped orientation for grounding responses (ADR 0081).

    Used to ground model responses in what the user has confirmed about
    themselves. Excludes intimate regulation history and unconfirmed
    candidates.
    """
    confirmed_values: List[str] = field(default_factory=list)
    confirmed_rules: List[PersonalRegulationRule] = field(default_factory=list)
    active_commitments: List[str] = field(default_factory=list)
    current_purpose: Optional[str] = None
    generated_at: str = field(default_factory=lambda: _now_iso())

    def get_authoritative_rules(
        self,
        min_strength: RuleStrength = RuleStrength.DEFAULT_PRINCIPLE,
    ) -> List[PersonalRegulationRule]:
        """Return rules that are confirmed and meet the minimum strength threshold.

        Order: Hard Guardrails first, then Default Principles, then Reflection Prompts.
        """
        strength_order = {
            RuleStrength.HARD_GUARDRAIL: 0,
            RuleStrength.DEFAULT_PRINCIPLE: 1,
            RuleStrength.REFLECTION_PROMPT: 2,
        }
        threshold = strength_order[min_strength]
        eligible = [
            r for r in self.confirmed_rules
            if r.is_authoritative() and strength_order[r.strength] <= threshold
        ]
        eligible.sort(key=lambda r: strength_order[r.strength])
        return eligible


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_session_id() -> str:
    return f"reg_{uuid.uuid4().hex[:16]}"


def _new_rule_id() -> str:
    return f"rule_{uuid.uuid4().hex[:12]}"
