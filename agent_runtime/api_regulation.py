"""Regulation API endpoints — U1 from implementation-plan-regulation-pkm.md.

ADR 0095: Web App Is Primary and Discord Is Rapid Entry.
ADR 0096: Single-Owner Private Access and Explicit Channel Linking.
ADR 0100: Model Proposes; Code Authorizes and Persists.

Provides REST endpoints for the guided PWA Regulation flow:
- Session lifecycle: create, read, list, complete, expire
- Structured capture: facts, interpretations, emotions, urges, actions, outcomes
- Safety screen: begin, complete, safety resources
- GPT-assisted coaching: model-assisted regulation
- Personal regulation rules: list, create, confirm, retire
- Offline protocol access
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from .emotional_regulation import (
    Action,
    ConfirmationState,
    Emotion,
    EmotionLabel,
    Fact,
    Interpretation,
    Outcome,
    PersonalRegulationRule,
    RegulationStateError,
    RuleStrength,
    SafetyCategory,
    SessionState,
    TriggerSession,
    Urge,
    begin_safety_screen,
    complete_safety_screen,
    complete_trigger_check_in,
    get_deterministic_protocol,
    get_non_overridable_safety_rules,
    get_safety_resources,
    is_safety_blocking,
    record_trigger_response,
    start_trigger_check_in,
)
from .model_assisted_regulation import (
    RegulationModelResponse,
    RegulationPipelineResult,
    handle_degradation,
    run_regulation_pipeline,
    validate_model_response,
)
from .model_provider import (
    ContextBudget,
    FailureClass,
    FakeProvider,
    ModelProvider,
    Workflow,
)
from .stores import RegulationStore, StoreRegistry

if TYPE_CHECKING:
    from .regulation_persistence import EncryptedRegulationPersistence

# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

# Pre-populate default safety rules (non-overridable)
DEFAULT_SAFETY_RULES = get_non_overridable_safety_rules()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ═══════════════════════════════════════════════════════════════════════
# Router factory
# ═══════════════════════════════════════════════════════════════════════


def create_regulation_router(
    *,
    store_registry: StoreRegistry,
    owner_id: str = "default",
    model_provider: Optional[ModelProvider] = None,
    system_prompt: Optional[str] = None,
    sessions_dict: Optional[Dict[str, TriggerSession]] = None,
    rules_dict: Optional[Dict[str, PersonalRegulationRule]] = None,
    persistence: Optional["EncryptedRegulationPersistence"] = None,
    auth_dependency: Any = None,
) -> APIRouter:
    """Create the Regulation API router.

    Args:
        store_registry: Store registry for persistence.
        owner_id: The owner identifier.
        model_provider: Optional ModelProvider for AI-assisted coaching.
        system_prompt: Optional custom system prompt.
        sessions_dict: Optional external sessions dict (enables sharing
            with api_privacy).
        rules_dict: Optional external rules dict (enables sharing
            with api_privacy).

    Returns:
        Configured APIRouter with all Regulation endpoints.
    """
    dependencies = [Depends(auth_dependency)] if auth_dependency is not None else []
    router = APIRouter(
        prefix="/api/regulation", tags=["regulation"], dependencies=dependencies
    )
    _provider = model_provider or FakeProvider()
    _system_prompt = system_prompt or _default_system_prompt()
    _sessions: Dict[str, TriggerSession] = sessions_dict if sessions_dict is not None else {}
    _rules: Dict[str, PersonalRegulationRule] = rules_dict if rules_dict is not None else {}

    if persistence is not None:
        durable_sessions, durable_rules = persistence.load()
        _sessions.update(durable_sessions)
        _rules.update(durable_rules)

    def _put_session(session: TriggerSession) -> None:
        _sessions[session.session_id] = session
        if persistence is not None:
            persistence.save_session(session)

    def _put_rule(rule: PersonalRegulationRule) -> None:
        _rules[rule.rule_id] = rule
        if persistence is not None:
            persistence.save_rule(rule)

    # Pre-populate default safety rules
    for rule_text in DEFAULT_SAFETY_RULES:
        existing = any(r.text == rule_text for r in _rules.values())
        if not existing:
            rule = PersonalRegulationRule(
                rule_id=str(uuid.uuid4()),
                text=rule_text,
                strength=RuleStrength.HARD_GUARDRAIL,
                confirmation=ConfirmationState.CONFIRMED,
            )
            _rules[rule.rule_id] = rule

    # ── Session lifecycle ────────────────────────────────────────────

    @router.post("/sessions")
    async def create_session(request: Request) -> Dict[str, Any]:
        """Create a new Regulation Session.

        Request body:
            trigger_event: str (required) — one-sentence description
            is_private: bool (default false) — Private Check-In if true

        Returns the session ID and initial state.
        """
        body = await request.json()
        trigger_event = body.get("trigger_event", "").strip()
        if not trigger_event:
            raise HTTPException(status_code=400, detail="trigger_event is required")

        is_private = body.get("is_private", False)

        session = start_trigger_check_in(
            owner_id=owner_id,
            trigger_event=trigger_event,
            is_private=is_private,
        )

        # Begin safety screen immediately
        session = begin_safety_screen(session)

        _put_session(session)

        return {
            "session_id": session.session_id,
            "state": session.state.value,
            "trigger_event": session.trigger_event,
            "is_private": session.is_private,
            "created_at": session.created_at,
        }

    @router.get("/sessions/{session_id}")
    async def get_session(session_id: str) -> Dict[str, Any]:
        """Get the current state of a Regulation Session."""
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return _session_to_dict(session)

    @router.get("/sessions")
    async def list_sessions(
        state: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List Regulation Sessions, optionally filtered by state."""
        sessions = list(_sessions.values())
        if state:
            sessions = [s for s in sessions if s.state.value == state]
        # Sort by created_at descending, limit
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        sessions = sessions[:limit]
        return {
            "count": len(sessions),
            "sessions": [_session_summary(s) for s in sessions],
        }

    @router.post("/sessions/{session_id}/expire")
    async def expire_session(session_id: str) -> Dict[str, Any]:
        """Expire an incomplete session."""
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state in (SessionState.COMPLETED, SessionState.EXPIRED):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot expire session in state {session.state.value}",
            )

        if session.is_private:
            del _sessions[session_id]
            return {"session_id": session_id, "state": SessionState.EXPIRED.value}

        from .emotional_regulation import _transition
        session = _transition(session, SessionState.EXPIRED)
        _put_session(session)

        return {"session_id": session_id, "state": session.state.value}

    # ── Safety screen ────────────────────────────────────────────────

    @router.post("/sessions/{session_id}/safety-screen")
    async def complete_safety(request: Request, session_id: str) -> Dict[str, Any]:
        """Complete the safety screen for a session.

        Request body:
            safety_category: str — one of self_harm, violence, abuse,
                immediate_danger, none

        Routes to ACTIVE or SAFETY_BRANCH.
        """
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        body = await request.json()
        category_str = body.get("safety_category", "none")

        try:
            category = SafetyCategory(category_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid safety_category: {category_str}. "
                       f"Must be one of: {[c.value for c in SafetyCategory]}",
            )

        try:
            session = complete_safety_screen(session, category)
        except RegulationStateError as e:
            raise HTTPException(status_code=400, detail=str(e))

        _put_session(session)

        return {
            "session_id": session_id,
            "state": session.state.value,
            "safety_category": category.value,
            "is_safety_active": session.is_safety_active(),
        }

    @router.get("/safety-resources")
    async def safety_resources(
        category: str = "none",
    ) -> Dict[str, Any]:
        """Get local safety resources and emergency instructions.

        Always available, no auth needed for this endpoint.
        Query param: category (default: "none")
        """
        try:
            cat = SafetyCategory(category)
        except ValueError:
            cat = SafetyCategory.NONE
        resources = get_safety_resources(cat)
        rules = [
            {"text": r, "strength": "hard_guardrail"}
            for r in DEFAULT_SAFETY_RULES
        ]
        return {
            "category": cat.value,
            "resources": resources,
            "non_overridable_rules": rules,
        }

    # ── Structured capture ───────────────────────────────────────────

    @router.post("/sessions/{session_id}/facts")
    async def record_facts(request: Request, session_id: str) -> Dict[str, Any]:
        """Record facts for a session.

        Request body:
            facts: list of {text, certainty, source}
        """
        session = _get_active_session(_sessions, session_id)
        body = await request.json()

        facts = []
        for item in body.get("facts", []):
            try:
                facts.append(Fact(
                    text=item["text"],
                    certainty=float(item["certainty"]),
                    source=item.get("source", "user_report"),
                ))
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=400, detail=str(e))

        try:
            session = record_trigger_response(session, facts=facts)
        except RegulationStateError as e:
            raise HTTPException(status_code=400, detail=str(e))

        _put_session(session)
        return _session_to_dict(session)

    @router.post("/sessions/{session_id}/interpretations")
    async def record_interpretations(
        request: Request, session_id: str
    ) -> Dict[str, Any]:
        """Record interpretations for a session."""
        session = _get_active_session(_sessions, session_id)
        body = await request.json()

        interpretations = []
        for item in body.get("interpretations", []):
            try:
                interpretations.append(Interpretation(
                    text=item["text"],
                    plausibility=float(item["plausibility"]),
                    evidence_for=item.get("evidence_for", []),
                    evidence_against=item.get("evidence_against", []),
                ))
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=400, detail=str(e))

        try:
            session = record_trigger_response(session, interpretations=interpretations)
        except RegulationStateError as e:
            raise HTTPException(status_code=400, detail=str(e))

        _put_session(session)
        return _session_to_dict(session)

    @router.post("/sessions/{session_id}/emotions")
    async def record_emotions(request: Request, session_id: str) -> Dict[str, Any]:
        """Record emotions for a session."""
        session = _get_active_session(_sessions, session_id)
        body = await request.json()

        emotions = []
        for item in body.get("emotions", []):
            try:
                label = EmotionLabel(item["label"].lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid emotion label: {item.get('label')}",
                )
            try:
                emotions.append(Emotion(
                    label=label,
                    intensity=int(item["intensity"]),
                    description=item.get("description", ""),
                ))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        try:
            session = record_trigger_response(session, emotions=emotions)
        except RegulationStateError as e:
            raise HTTPException(status_code=400, detail=str(e))

        _put_session(session)
        return _session_to_dict(session)

    @router.post("/sessions/{session_id}/urges")
    async def record_urges(request: Request, session_id: str) -> Dict[str, Any]:
        """Record urges for a session."""
        session = _get_active_session(_sessions, session_id)
        body = await request.json()

        urges = []
        for item in body.get("urges", []):
            try:
                urges.append(Urge(
                    text=item["text"],
                    strength=int(item["strength"]),
                ))
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=400, detail=str(e))

        try:
            session = record_trigger_response(session, urges=urges)
        except RegulationStateError as e:
            raise HTTPException(status_code=400, detail=str(e))

        _put_session(session)
        return _session_to_dict(session)

    @router.post("/sessions/{session_id}/actions")
    async def record_actions(request: Request, session_id: str) -> Dict[str, Any]:
        """Record a chosen action."""
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        body = await request.json()

        actions = []
        for item in body.get("actions", []):
            try:
                actions.append(Action(
                    text=item["text"],
                    reversible=item.get("reversible", True),
                    waiting_period_minutes=int(item.get("waiting_period_minutes", 0)),
                ))
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=400, detail=str(e))

        new_actions = list(session.actions) + actions
        from .emotional_regulation import _new_version
        session = _new_version(session, actions=new_actions)

        _put_session(session)
        return _session_to_dict(session)

    @router.post("/sessions/{session_id}/outcomes")
    async def record_outcomes(request: Request, session_id: str) -> Dict[str, Any]:
        """Record an outcome for a completed session."""
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state != SessionState.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail="Can only record outcomes for completed sessions",
            )

        body = await request.json()

        outcomes = []
        for item in body.get("outcomes", []):
            try:
                outcomes.append(Outcome(
                    text=item["text"],
                    was_helpful=item.get("was_helpful"),
                ))
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=400, detail=str(e))

        new_outcomes = list(session.outcomes) + outcomes
        from .emotional_regulation import _new_version
        session = _new_version(session, outcomes=new_outcomes)

        _put_session(session)
        return _session_to_dict(session)

    # ── Complete session ─────────────────────────────────────────────

    @router.post("/sessions/{session_id}/complete")
    async def complete_session(
        request: Request, session_id: str
    ) -> Dict[str, Any]:
        """Complete a Regulation Session.

        Optional body:
            actions: list of {text, reversible, waiting_period_minutes}
            outcomes: list of {text, was_helpful}
        """
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        body = await request.json() if await request.body() else {}

        actions = []
        for item in body.get("actions", []):
            actions.append(Action(
                text=item["text"],
                reversible=item.get("reversible", True),
                waiting_period_minutes=int(item.get("waiting_period_minutes", 0)),
            ))

        outcomes = []
        for item in body.get("outcomes", []):
            outcomes.append(Outcome(
                text=item["text"],
                was_helpful=item.get("was_helpful"),
            ))

        try:
            session = complete_trigger_check_in(
                session,
                actions=actions if actions else None,
                outcomes=outcomes if outcomes else None,
            )
        except RegulationStateError as e:
            raise HTTPException(status_code=400, detail=str(e))

        _put_session(session)

        return {"session_id": session_id, "state": session.state.value}

    # ── GPT-assisted coaching ────────────────────────────────────────

    @router.post("/sessions/{session_id}/assist")
    async def assist_session(request: Request, session_id: str) -> Dict[str, Any]:
        """Get GPT-assisted coaching for a session.

        Runs the regulation pipeline: context assembly → model call →
        validation → authorization → degradation fallback.

        Request body (optional):
            current_message: str — additional user message for this turn

        Returns the authorized model response or degradation protocol.
        """
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state not in (SessionState.ACTIVE, SessionState.SAFETY_BRANCH):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot assist session in state {session.state.value}. "
                       f"Session must be ACTIVE or SAFETY_BRANCH.",
            )

        body = await request.json() if await request.body() else {}
        current_message = body.get("current_message", session.trigger_event or "")

        try:
            result: RegulationPipelineResult = await run_regulation_pipeline(
                provider=_provider,
                session=session,
                user_message=current_message,
                system_prompt=_system_prompt,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Regulation pipeline error: {str(e)}")

        # Update in-memory session
        if result.session:
            _put_session(result.session)

        return {
            "session_id": session_id,
            "is_degraded": result.is_degraded,
            "has_authorized_response": result.has_authorized_response,
            "model_response": (
                result.authorized.model_response.dict()
                if result.authorized else None
            ),
            "authorizations": (
                {k: v.value for k, v in result.authorized.authorizations.items()}
                if result.authorized else None
            ),
            "blocked_items": result.authorized.blocked_items if result.authorized else [],
            "requires_owner_confirm": (
                result.authorized.requires_owner_confirm
                if result.authorized else []
            ),
            "degradation": (
                {
                    "reason": result.degradation.reason.value,
                    "message": result.degradation.message,
                    "protocol_steps": result.degradation.protocol_steps,
                    "safety_resources": result.degradation.safety_resources,
                }
                if result.degradation else None
            ),
        }

    # ── Deterministic offline protocol ───────────────────────────────

    @router.get("/sessions/{session_id}/offline")
    async def offline_protocol(session_id: str) -> Dict[str, Any]:
        """Get the deterministic offline protocol for a session.

        Always available, even when the model is unavailable.
        """
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        protocol = get_deterministic_protocol()
        return {
            "session_id": session_id,
            "is_safety_active": session.is_safety_active(),
            "protocol": protocol,
        }

    # ── Personal regulation rules ────────────────────────────────────

    @router.get("/rules")
    async def list_rules(
        strength: Optional[str] = None,
        confirmation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List personal regulation rules, optionally filtered."""
        rules = list(_rules.values())
        if strength:
            try:
                s = RuleStrength(strength)
                rules = [r for r in rules if r.strength == s]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid strength: {strength}",
                )
        if confirmation:
            try:
                c = ConfirmationState(confirmation)
                rules = [r for r in rules if r.confirmation == c]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid confirmation: {confirmation}",
                )

        return {
            "count": len(rules),
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "text": r.text,
                    "strength": r.strength.value,
                    "confirmation": r.confirmation.value,
                    "exceptions": r.exceptions,
                    "created_at": r.created_at,
                }
                for r in rules
            ],
        }

    @router.post("/rules")
    async def create_rule(request: Request) -> Dict[str, Any]:
        """Create a personal regulation rule.

        Request body:
            text: str (required)
            strength: str — hard_guardrail, default_principle, reflection_prompt
            exceptions: list of str (optional)

        Hard guardrails cannot be created from the API if they conflict
        with non-overridable safety rules.
        """
        body = await request.json()
        text = body.get("text", "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="text is required")

        try:
            strength = RuleStrength(body.get("strength", "reflection_prompt"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid strength: {body.get('strength')}",
            )

        # Hard guardrails must not conflict with non-overridable safety rules
        if strength == RuleStrength.HARD_GUARDRAIL:
            safety_rules = get_non_overridable_safety_rules()
            for sr in safety_rules:
                if sr.lower() in text.lower():
                    raise HTTPException(
                        status_code=400,
                        detail="Hard guardrail conflicts with a non-overridable "
                               "safety rule. Use a weaker strength.",
                    )

        exceptions = body.get("exceptions", [])

        rule = PersonalRegulationRule(
            rule_id=str(uuid.uuid4()),
            text=text,
            strength=strength,
            confirmation=ConfirmationState.CONFIRMED,
            exceptions=exceptions,
        )

        _put_rule(rule)

        return {
            "rule_id": rule.rule_id,
            "text": rule.text,
            "strength": rule.strength.value,
            "confirmation": rule.confirmation.value,
            "exceptions": rule.exceptions,
            "created_at": rule.created_at,
        }

    @router.put("/rules/{rule_id}/confirm")
    async def confirm_rule(rule_id: str) -> Dict[str, Any]:
        """Confirm an unconfirmed rule."""
        rule = _rules.get(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        from .emotional_regulation import _now_iso as _reg_now
        new_rule = PersonalRegulationRule(
            rule_id=rule.rule_id,
            text=rule.text,
            strength=rule.strength,
            confirmation=ConfirmationState.CONFIRMED,
            exceptions=rule.exceptions,
            created_at=rule.created_at,
            updated_at=_reg_now(),
        )
        _put_rule(new_rule)

        return {
            "rule_id": new_rule.rule_id,
            "text": new_rule.text,
            "strength": new_rule.strength.value,
            "confirmation": new_rule.confirmation.value,
        }

    @router.put("/rules/{rule_id}/retire")
    async def retire_rule(rule_id: str) -> Dict[str, Any]:
        """Retire a rule."""
        rule = _rules.get(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        # Non-overridable safety rules cannot be retired
        safety_rules = get_non_overridable_safety_rules()
        for sr in safety_rules:
            if sr.lower() in rule.text.lower() and rule.strength == RuleStrength.HARD_GUARDRAIL:
                raise HTTPException(
                    status_code=400,
                    detail="This rule matches a non-overridable safety rule "
                           "and cannot be retired.",
                )

        from .emotional_regulation import _now_iso as _reg_now
        new_rule = PersonalRegulationRule(
            rule_id=rule.rule_id,
            text=rule.text,
            strength=rule.strength,
            confirmation=ConfirmationState.RETIRED,
            exceptions=rule.exceptions,
            created_at=rule.created_at,
            updated_at=_reg_now(),
        )
        _put_rule(new_rule)

        return {"rule_id": rule_id, "confirmation": "retired"}

    return router


# ═══════════════════════════════════════════════════════════════════════
# Helpers (used by endpoint functions as closures — defined here for
# reuse, but they close over _sessions/_rules from the factory)
# ═══════════════════════════════════════════════════════════════════════


def _default_system_prompt() -> str:
    """Default system prompt for model-assisted Regulation."""
    return (
        "You are a regulation coach helping the user navigate emotional "
        "activation. Your role is to help them separate facts from "
        "interpretations, identify their emotions and urges, and choose "
        "actions consistent with their values and long-term wellbeing.\n\n"
        "Guidelines:\n"
        "- Never make truth verdicts about another person's motives.\n"
        "- Always present at least one interpretation that does not "
        "assume bad intent.\n"
        "- Acknowledge uncertainty explicitly.\n"
        "- Never suggest surveillance, retaliation, coercion, or "
        "repeated interrogation.\n"
        "- Do not diagnose or label people.\n"
        "- Focus on what the user can control: their own choices.\n"
        "- Flag safety concerns when appropriate.\n"
        "- Request confirmation for sensitive or identity-shaping items."
    )


def _get_active_session(sessions: Dict[str, TriggerSession], session_id: str) -> TriggerSession:
    """Get a session and verify it's in ACTIVE state."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.state != SessionState.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not ACTIVE (current state: {session.state.value})",
        )
    return session


def _session_to_dict(session: TriggerSession) -> Dict[str, Any]:
    """Serialize a session to a JSON-safe dict."""
    return {
        "session_id": session.session_id,
        "owner_id": session.owner_id,
        "state": session.state.value,
        "is_private": session.is_private,
        "trigger_event": session.trigger_event,
        "facts": [
            {
                "text": f.text,
                "certainty": f.certainty,
                "source": f.source,
                "captured_at": f.captured_at,
            }
            for f in session.facts
        ],
        "interpretations": [
            {
                "text": i.text,
                "plausibility": i.plausibility,
                "evidence_for": i.evidence_for,
                "evidence_against": i.evidence_against,
            }
            for i in session.interpretations
        ],
        "emotions": [
            {
                "label": e.label.value,
                "intensity": e.intensity,
                "description": e.description,
            }
            for e in session.emotions
        ],
        "urges": [
            {"text": u.text, "strength": u.strength}
            for u in session.urges
        ],
        "actions": [
            {
                "text": a.text,
                "reversible": a.reversible,
                "waiting_period_minutes": a.waiting_period_minutes,
            }
            for a in session.actions
        ],
        "outcomes": [
            {
                "text": o.text,
                "was_helpful": o.was_helpful,
            }
            for o in session.outcomes
        ],
        "safety_state": {
            "category": session.safety_state.category.value,
            "is_active": session.safety_state.is_active,
        },
        "sensitivity": session.sensitivity.value,
        "retention_days": session.retention_days,
        "created_at": session.created_at,
        "completed_at": session.completed_at,
        "version": session.version,
    }


def _session_summary(session: TriggerSession) -> Dict[str, Any]:
    """A compact summary of a session (no content details)."""
    return {
        "session_id": session.session_id,
        "state": session.state.value,
        "trigger_event": session.trigger_event,
        "is_private": session.is_private,
        "created_at": session.created_at,
        "completed_at": session.completed_at,
        "safety_active": session.is_safety_active(),
        "emotion_count": len(session.emotions),
        "fact_count": len(session.facts),
        "action_count": len(session.actions),
    }
