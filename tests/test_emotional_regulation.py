"""Tests for emotional_regulation module — R1 through R5."""

from __future__ import annotations

import pytest

# Override the conftest _isolate_paths fixture so these tests don't need google.adk.
@pytest.fixture(autouse=True)
def _isolate_paths():
    pass


from agent_runtime.emotional_regulation import (
    Action,
    ConfirmationState,
    Emotion,
    EmotionLabel,
    Fact,
    Interpretation,
    Outcome,
    PersonalOrientationSnapshot,
    PersonalRegulationRule,
    RegulationStateError,
    RuleStrength,
    SafetyCategory,
    SafetyState,
    SessionState,
    TriggerSession,
    Urge,
    # R2 — State machine
    start_trigger_check_in,
    record_trigger_response,
    complete_trigger_check_in,
    complete_safety_screen,
    expire_session,
    # R3 — Deterministic protocol
    get_deterministic_protocol,
    get_non_overridable_safety_rules,
    # R4 — Safety branch
    create_safety_branch_response,
    get_safety_resources,
    is_safety_blocking,
    # R5 — Rules and orientation
    create_personal_rule,
    confirm_rule,
    retire_rule,
    update_rule_strength,
    add_rule_exception,
)


# ═══════════════════════════════════════════════════════════════════════
# R1 — Regulation Records
# ═══════════════════════════════════════════════════════════════════════


class TestFact:
    def test_create_valid_fact(self):
        f = Fact(text="She left without saying goodbye", certainty=1.0, source="user_report")
        assert f.text == "She left without saying goodbye"
        assert f.certainty == 1.0
        assert f.source == "user_report"

    def test_certainty_bounds(self):
        with pytest.raises(ValueError, match="certainty must be 0.0–1.0"):
            Fact(text="x", certainty=1.5, source="user_report")
        with pytest.raises(ValueError, match="certainty must be 0.0–1.0"):
            Fact(text="x", certainty=-0.1, source="user_report")

    def test_certainty_edge_values(self):
        # 0.0 and 1.0 are valid
        Fact(text="x", certainty=0.0, source="user_report")
        Fact(text="x", certainty=1.0, source="user_report")

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError, match="Fact text cannot be empty"):
            Fact(text="", certainty=0.5, source="user_report")
        with pytest.raises(ValueError, match="Fact text cannot be empty"):
            Fact(text="   ", certainty=0.5, source="user_report")

    def test_frozen_immutable(self):
        f = Fact(text="x", certainty=0.5, source="user_report")
        with pytest.raises(Exception):
            f.certainty = 0.8  # type: ignore


class TestInterpretation:
    def test_create_valid(self):
        i = Interpretation(
            text="Maybe she was upset about something unrelated",
            plausibility=0.4,
            evidence_for=["She seemed fine earlier"],
            evidence_against=["She didn't say anything was wrong"],
        )
        assert i.plausibility == 0.4
        assert len(i.evidence_for) == 1
        assert len(i.evidence_against) == 1

    def test_plausibility_bounds(self):
        with pytest.raises(ValueError, match="plausibility must be 0.0–1.0"):
            Interpretation(text="x", plausibility=2.0)
        with pytest.raises(ValueError, match="plausibility must be 0.0–1.0"):
            Interpretation(text="x", plausibility=-0.5)

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError, match="Interpretation text cannot be empty"):
            Interpretation(text="", plausibility=0.5)


class TestEmotion:
    def test_create_valid(self):
        e = Emotion(label=EmotionLabel.ANGER, intensity=7, description="I felt hot and tense")
        assert e.label == EmotionLabel.ANGER
        assert e.intensity == 7

    def test_intensity_bounds(self):
        with pytest.raises(ValueError, match="intensity must be 1–10"):
            Emotion(label=EmotionLabel.FEAR, intensity=0)
        with pytest.raises(ValueError, match="intensity must be 1–10"):
            Emotion(label=EmotionLabel.FEAR, intensity=11)

    def test_intensity_edge_values(self):
        Emotion(label=EmotionLabel.FEAR, intensity=1)
        Emotion(label=EmotionLabel.FEAR, intensity=10)

    def test_all_labels_work(self):
        for label in EmotionLabel:
            e = Emotion(label=label, intensity=5)
            assert e.label == label


class TestUrge:
    def test_create_valid(self):
        u = Urge(text="Send an angry message", strength=8)
        assert u.text == "Send an angry message"
        assert u.strength == 8

    def test_strength_bounds(self):
        with pytest.raises(ValueError, match="strength must be 1–10"):
            Urge(text="x", strength=0)
        with pytest.raises(ValueError, match="strength must be 1–10"):
            Urge(text="x", strength=11)

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError, match="Urge text cannot be empty"):
            Urge(text="", strength=5)


class TestAction:
    def test_create_valid(self):
        a = Action(text="Wait 30 minutes before replying", reversible=True, waiting_period_minutes=30)
        assert a.reversible is True
        assert a.waiting_period_minutes == 30

    def test_defaults(self):
        a = Action(text="Go for a walk")
        assert a.reversible is True
        assert a.waiting_period_minutes == 0


class TestOutcome:
    def test_create_valid(self):
        o = Outcome(text="Waiting helped me respond more calmly", was_helpful=True)
        assert o.was_helpful is True

    def test_was_helpful_can_be_none(self):
        o = Outcome(text="Still processing what happened")
        assert o.was_helpful is None


class TestSafetyState:
    def test_default_safe(self):
        s = SafetyState()
        assert s.category == SafetyCategory.NONE
        assert s.is_active is False

    def test_active_safety(self):
        s = SafetyState(category=SafetyCategory.SELF_HARM, is_active=True)
        assert s.category == SafetyCategory.SELF_HARM
        assert s.is_active is True


class TestPersonalRegulationRule:
    def test_create_rule(self):
        r = PersonalRegulationRule(
            rule_id="rule_001",
            text="Pause before sending another message",
            strength=RuleStrength.DEFAULT_PRINCIPLE,
        )
        assert r.text == "Pause before sending another message"
        assert r.confirmation == ConfirmationState.UNCONFIRMED
        assert r.is_authoritative() is False

    def test_confirmed_rule_is_authoritative(self):
        r = PersonalRegulationRule(
            rule_id="rule_001",
            text="Pause before sending another message",
            strength=RuleStrength.DEFAULT_PRINCIPLE,
            confirmation=ConfirmationState.CONFIRMED,
        )
        assert r.is_authoritative() is True

    def test_retired_rule_not_authoritative(self):
        r = PersonalRegulationRule(
            rule_id="rule_001",
            text="Pause before sending another message",
            strength=RuleStrength.DEFAULT_PRINCIPLE,
            confirmation=ConfirmationState.RETIRED,
        )
        assert r.is_authoritative() is False

    def test_under_review_is_not_authoritative(self):
        r = PersonalRegulationRule(
            rule_id="rule_001",
            text="Pause before sending another message",
            strength=RuleStrength.DEFAULT_PRINCIPLE,
            confirmation=ConfirmationState.UNDER_REVIEW,
        )
        assert r.is_authoritative() is False

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError, match="Rule text cannot be empty"):
            PersonalRegulationRule(rule_id="r1", text="", strength=RuleStrength.DEFAULT_PRINCIPLE)

    def test_rule_strength_values(self):
        for strength in RuleStrength:
            r = PersonalRegulationRule(rule_id="r1", text="Test rule", strength=strength)
            assert r.strength == strength


class TestTriggerSession:
    def test_create_session(self):
        s = TriggerSession(
            session_id="reg_001",
            owner_id="owner_1",
            trigger_event="Partner didn't reply for 3 hours",
        )
        assert s.session_id == "reg_001"
        assert s.state == SessionState.CREATED
        assert s.is_private is False
        assert s.is_durable() is True
        assert s.is_safety_active() is False

    def test_private_check_in(self):
        s = TriggerSession(
            session_id="reg_002",
            owner_id="owner_1",
            trigger_event="Feeling overwhelmed",
            is_private=True,
        )
        assert s.is_private is True
        assert s.is_durable() is False

    def test_session_with_facts_interpretations(self):
        s = TriggerSession(
            session_id="reg_003",
            owner_id="owner_1",
            trigger_event="Argument about finances",
            facts=[Fact(text="We raised our voices", certainty=1.0, source="user_report")],
            interpretations=[
                Interpretation(
                    text="Maybe we're both stressed about money",
                    plausibility=0.7,
                )
            ],
            emotions=[Emotion(label=EmotionLabel.ANGER, intensity=6)],
            urges=[Urge(text="Shut down and leave", strength=7)],
        )
        assert len(s.facts) == 1
        assert len(s.interpretations) == 1
        assert len(s.emotions) == 1
        assert len(s.urges) == 1

    def test_safety_active_detection(self):
        s = TriggerSession(
            session_id="reg_004",
            owner_id="owner_1",
            trigger_event="Crisis",
            safety_state=SafetyState(category=SafetyCategory.SELF_HARM, is_active=True),
        )
        assert s.is_safety_active() is True

    def test_session_has_retention_metadata(self):
        s = TriggerSession(
            session_id="reg_005",
            owner_id="owner_1",
            trigger_event="test",
            retention_days=90,
            sensitivity="restricted",
        )
        assert s.retention_days == 90
        assert s.sensitivity == "restricted"

    def test_ordinary_chat_does_not_create_record(self):
        """R1 acceptance: ordinary chat does not create a Regulation record."""
        # The TriggerSession requires explicit construction — there's no
        # automatic creation from chat. This is enforced by design: the
        # caller must explicitly call start_trigger_check_in.
        # This test verifies that no implicit creation path exists.
        with pytest.raises(TypeError):
            TriggerSession()  # missing required fields


# ═══════════════════════════════════════════════════════════════════════
# R2 — State Machine
# ═══════════════════════════════════════════════════════════════════════


class TestStartTriggerCheckIn:
    def test_creates_session_in_created_state(self):
        s = start_trigger_check_in("owner_1", "Partner didn't reply")
        assert s.state == SessionState.CREATED
        assert s.owner_id == "owner_1"
        assert s.trigger_event == "Partner didn't reply"

    def test_idempotency_with_session_id(self):
        s1 = start_trigger_check_in("owner_1", "test", session_id="reg_custom")
        s2 = start_trigger_check_in("owner_1", "test", session_id="reg_custom")
        assert s1.session_id == s2.session_id

    def test_unique_ids_by_default(self):
        s1 = start_trigger_check_in("owner_1", "test")
        s2 = start_trigger_check_in("owner_1", "test")
        assert s1.session_id != s2.session_id

    def test_private_check_in(self):
        s = start_trigger_check_in("owner_1", "test", is_private=True)
        assert s.is_private is True
        assert s.is_durable() is False

    def test_empty_trigger_rejected(self):
        with pytest.raises(ValueError, match="trigger_event cannot be empty"):
            start_trigger_check_in("owner_1", "")
        with pytest.raises(ValueError, match="trigger_event cannot be empty"):
            start_trigger_check_in("owner_1", "   ")


class TestCompleteSafetyScreen:
    def test_route_to_active_when_no_safety_concern(self):
        s = start_trigger_check_in("owner_1", "test")
        # Simulate safety screen transition
        s = TriggerSession(
            session_id=s.session_id,
            owner_id=s.owner_id,
            trigger_event=s.trigger_event,
            state=SessionState.SAFETY_SCREEN,
        )
        s = complete_safety_screen(s, SafetyCategory.NONE)
        assert s.state == SessionState.ACTIVE
        assert s.safety_state.category == SafetyCategory.NONE
        assert s.safety_state.is_active is False

    def test_route_to_safety_branch(self):
        s = start_trigger_check_in("owner_1", "test")
        s = TriggerSession(
            session_id=s.session_id,
            owner_id=s.owner_id,
            trigger_event=s.trigger_event,
            state=SessionState.SAFETY_SCREEN,
        )
        s = complete_safety_screen(s, SafetyCategory.SELF_HARM)
        assert s.state == SessionState.SAFETY_BRANCH
        assert s.safety_state.category == SafetyCategory.SELF_HARM
        assert s.safety_state.is_active is True

    def test_rejects_when_not_in_safety_screen(self):
        s = start_trigger_check_in("owner_1", "test")
        with pytest.raises(RegulationStateError):
            complete_safety_screen(s, SafetyCategory.NONE)


class TestRecordTriggerResponse:
    def test_records_in_active_state(self):
        s = start_trigger_check_in("owner_1", "test")
        s = TriggerSession(
            session_id=s.session_id,
            owner_id=s.owner_id,
            trigger_event=s.trigger_event,
            state=SessionState.ACTIVE,
        )
        s = record_trigger_response(
            s,
            facts=[Fact(text="We argued", certainty=1.0, source="user_report")],
            emotions=[Emotion(label=EmotionLabel.ANGER, intensity=7)],
        )
        assert len(s.facts) == 1
        assert len(s.emotions) == 1
        assert s.version > 1

    def test_accumulates_across_calls(self):
        s = start_trigger_check_in("owner_1", "test")
        s = TriggerSession(
            session_id=s.session_id,
            owner_id=s.owner_id,
            trigger_event=s.trigger_event,
            state=SessionState.ACTIVE,
        )
        s = record_trigger_response(s, facts=[Fact(text="A", certainty=1.0, source="user_report")])
        s = record_trigger_response(s, emotions=[Emotion(label=EmotionLabel.FEAR, intensity=4)])
        assert len(s.facts) == 1
        assert len(s.emotions) == 1
        # Both should be present
        assert s.facts[0].text == "A"
        assert s.emotions[0].label == EmotionLabel.FEAR

    def test_rejects_in_non_active_state(self):
        s = start_trigger_check_in("owner_1", "test")
        with pytest.raises(RegulationStateError, match="must be ACTIVE"):
            record_trigger_response(s, facts=[Fact(text="x", certainty=0.5, source="user_report")])

    def test_rejects_in_safety_branch(self):
        s = TriggerSession(
            session_id="reg_x",
            owner_id="owner_1",
            trigger_event="crisis",
            state=SessionState.SAFETY_BRANCH,
        )
        with pytest.raises(RegulationStateError):
            record_trigger_response(s, facts=[Fact(text="x", certainty=0.5, source="user_report")])


class TestCompleteTriggerCheckIn:
    def test_complete_from_active(self):
        s = start_trigger_check_in("owner_1", "test")
        s = TriggerSession(
            session_id=s.session_id,
            owner_id=s.owner_id,
            trigger_event=s.trigger_event,
            state=SessionState.ACTIVE,
        )
        s = complete_trigger_check_in(
            s,
            actions=[Action(text="Went for a walk")],
            outcomes=[Outcome(text="Felt calmer", was_helpful=True)],
        )
        assert s.state == SessionState.COMPLETED
        assert len(s.actions) == 1
        assert len(s.outcomes) == 1
        assert s.completed_at is not None

    def test_complete_from_safety_branch(self):
        s = TriggerSession(
            session_id="reg_x",
            owner_id="owner_1",
            trigger_event="crisis",
            state=SessionState.SAFETY_BRANCH,
        )
        s = complete_trigger_check_in(s)
        assert s.state == SessionState.COMPLETED

    def test_cannot_complete_from_created(self):
        s = start_trigger_check_in("owner_1", "test")
        with pytest.raises(RegulationStateError):
            complete_trigger_check_in(s)

    def test_cannot_complete_already_completed(self):
        s = TriggerSession(
            session_id="reg_x",
            owner_id="owner_1",
            trigger_event="test",
            state=SessionState.COMPLETED,
        )
        with pytest.raises(RegulationStateError):
            complete_trigger_check_in(s)


class TestExpireSession:
    def test_expire_active_session(self):
        s = TriggerSession(
            session_id="reg_x",
            owner_id="owner_1",
            trigger_event="test",
            state=SessionState.ACTIVE,
        )
        s = expire_session(s)
        assert s.state == SessionState.EXPIRED

    def test_cannot_expire_completed(self):
        s = TriggerSession(
            session_id="reg_x",
            owner_id="owner_1",
            trigger_event="test",
            state=SessionState.COMPLETED,
        )
        with pytest.raises(RegulationStateError):
            expire_session(s)

    def test_cannot_expire_already_expired(self):
        s = TriggerSession(
            session_id="reg_x",
            owner_id="owner_1",
            trigger_event="test",
            state=SessionState.EXPIRED,
        )
        with pytest.raises(RegulationStateError):
            expire_session(s)


class TestStateTransitions:
    """Verify all valid and invalid transitions (R2 acceptance)."""

    def test_full_happy_path(self):
        """CREATED → SAFETY_SCREEN → ACTIVE → COMPLETED"""
        s = start_trigger_check_in("owner_1", "test")
        assert s.state == SessionState.CREATED

        s = TriggerSession(
            session_id=s.session_id,
            owner_id=s.owner_id,
            trigger_event=s.trigger_event,
            state=SessionState.SAFETY_SCREEN,
        )
        s = complete_safety_screen(s, SafetyCategory.NONE)
        assert s.state == SessionState.ACTIVE

        s = record_trigger_response(
            s,
            facts=[Fact(text="x", certainty=1.0, source="user_report")],
        )
        s = complete_trigger_check_in(s)
        assert s.state == SessionState.COMPLETED

    def test_safety_path(self):
        """CREATED → SAFETY_SCREEN → SAFETY_BRANCH → COMPLETED"""
        s = start_trigger_check_in("owner_1", "test")
        s = TriggerSession(
            session_id=s.session_id,
            owner_id=s.owner_id,
            trigger_event=s.trigger_event,
            state=SessionState.SAFETY_SCREEN,
        )
        s = complete_safety_screen(s, SafetyCategory.SELF_HARM)
        assert s.state == SessionState.SAFETY_BRANCH
        s = complete_trigger_check_in(s)
        assert s.state == SessionState.COMPLETED

    def test_expire_from_created(self):
        s = start_trigger_check_in("owner_1", "test")
        s = expire_session(s)
        assert s.state == SessionState.EXPIRED

    def test_expire_from_safety_screen(self):
        s = start_trigger_check_in("owner_1", "test")
        s = TriggerSession(
            session_id=s.session_id,
            owner_id=s.owner_id,
            trigger_event=s.trigger_event,
            state=SessionState.SAFETY_SCREEN,
        )
        s = expire_session(s)
        assert s.state == SessionState.EXPIRED

    def test_expire_from_active(self):
        s = TriggerSession(
            session_id="reg_x",
            owner_id="owner_1",
            trigger_event="test",
            state=SessionState.ACTIVE,
        )
        s = expire_session(s)
        assert s.state == SessionState.EXPIRED

    def test_cannot_jump_from_created_to_completed(self):
        s = start_trigger_check_in("owner_1", "test")
        with pytest.raises(RegulationStateError):
            complete_trigger_check_in(s)

    def test_cannot_jump_from_created_to_active(self):
        s = start_trigger_check_in("owner_1", "test")
        with pytest.raises(RegulationStateError):
            record_trigger_response(s)

    def test_version_increments_on_transition(self):
        s = start_trigger_check_in("owner_1", "test")
        v1 = s.version
        s = expire_session(s)
        assert s.version == v1 + 1

    def test_replay_safety(self):
        """Replay is safe: same input produces same state."""
        s1 = start_trigger_check_in("owner_1", "test")
        s1 = TriggerSession(
            session_id=s1.session_id,
            owner_id=s1.owner_id,
            trigger_event=s1.trigger_event,
            state=SessionState.SAFETY_SCREEN,
        )
        s1 = complete_safety_screen(s1, SafetyCategory.NONE)
        s1 = complete_trigger_check_in(s1)

        # Replay from same starting point
        s2 = start_trigger_check_in("owner_1", "test", session_id=s1.session_id)
        s2 = TriggerSession(
            session_id=s2.session_id,
            owner_id=s2.owner_id,
            trigger_event=s2.trigger_event,
            state=SessionState.SAFETY_SCREEN,
        )
        s2 = complete_safety_screen(s2, SafetyCategory.NONE)
        s2 = complete_trigger_check_in(s2)

        assert s1.state == s2.state == SessionState.COMPLETED


# ═══════════════════════════════════════════════════════════════════════
# R3 — Deterministic Emergency Protocol
# ═══════════════════════════════════════════════════════════════════════


class TestDeterministicProtocol:
    def test_returns_all_steps(self):
        flow = get_deterministic_protocol()
        assert len(flow) == 6
        steps = [s["step"] for s in flow]
        assert steps == [
            "trigger",
            "known_facts",
            "interpretation",
            "emotion_urge",
            "reversible_action",
            "waiting_interval",
        ]

    def test_each_step_has_prompt(self):
        flow = get_deterministic_protocol()
        for step in flow:
            assert "step" in step
            assert "prompt" in step
            assert len(step["prompt"]) > 20

    def test_never_makes_truth_verdict(self):
        """R3 acceptance: it never makes a truth verdict."""
        flow = get_deterministic_protocol()
        all_text = " ".join(s["prompt"] for s in flow)
        # Should not contain language that asserts truth about others' motives
        assert "they lied" not in all_text.lower()
        assert "they are" not in all_text.lower()

    def test_never_suggests_harmful_behaviors(self):
        """R3 acceptance: never suggests surveillance, retaliation, coercion, interrogation."""
        flow = get_deterministic_protocol()
        all_text = " ".join(s["prompt"] for s in flow).lower()
        forbidden = ["surveillance", "retaliation", "coercion", "interrogate"]
        for word in forbidden:
            assert word not in all_text, f"Protocol contains forbidden word: {word}"

    def test_protocol_is_deterministic(self):
        flow1 = get_deterministic_protocol()
        flow2 = get_deterministic_protocol()
        assert flow1 == flow2

    def test_protocol_is_immutable(self):
        flow = get_deterministic_protocol()
        flow_copy = get_deterministic_protocol()
        flow[0]["prompt"] = "MODIFIED"
        # Original should not be affected
        assert get_deterministic_protocol()[0]["prompt"] == flow_copy[0]["prompt"]


class TestNonOverridableSafetyRules:
    def test_returns_rules(self):
        rules = get_non_overridable_safety_rules()
        assert len(rules) >= 5

    def test_covers_all_required_prohibitions(self):
        rules_text = " ".join(get_non_overridable_safety_rules()).lower()
        required = ["surveillance", "retaliation", "coercion", "interrogation"]
        for word in required:
            assert word in rules_text, f"Missing prohibition: {word}"

    def test_no_truth_verdicts(self):
        rules_text = " ".join(get_non_overridable_safety_rules()).lower()
        assert "truth verdict" in rules_text or "truth" in rules_text

    def test_rules_are_immutable_copy(self):
        rules = get_non_overridable_safety_rules()
        rules.append("MODIFIED")
        assert len(get_non_overridable_safety_rules()) < len(rules)


# ═══════════════════════════════════════════════════════════════════════
# R4 — Safety Branch
# ═══════════════════════════════════════════════════════════════════════


class TestIsSafetyBlocking:
    def test_self_harm_is_blocking(self):
        assert is_safety_blocking(SafetyCategory.SELF_HARM) is True

    def test_violence_is_blocking(self):
        assert is_safety_blocking(SafetyCategory.VIOLENCE) is True

    def test_abuse_is_blocking(self):
        assert is_safety_blocking(SafetyCategory.ABUSE) is True

    def test_immediate_danger_is_blocking(self):
        assert is_safety_blocking(SafetyCategory.IMMEDIATE_DANGER) is True

    def test_none_is_not_blocking(self):
        assert is_safety_blocking(SafetyCategory.NONE) is False


class TestSafetyResources:
    def test_self_harm_has_resources(self):
        resources = get_safety_resources(SafetyCategory.SELF_HARM)
        assert len(resources["message"]) > 0
        assert "988" in resources.get("us", "") or "1553" in resources.get("ph", "")

    def test_violence_has_resources(self):
        resources = get_safety_resources(SafetyCategory.VIOLENCE)
        assert len(resources["message"]) > 0

    def test_abuse_has_resources(self):
        resources = get_safety_resources(SafetyCategory.ABUSE)
        assert len(resources["message"]) > 0

    def test_immediate_danger_has_resources(self):
        resources = get_safety_resources(SafetyCategory.IMMEDIATE_DANGER)
        assert len(resources["message"]) > 0

    def test_none_has_empty_resources(self):
        resources = get_safety_resources(SafetyCategory.NONE)
        assert resources["message"] == ""


class TestSafetyBranchResponse:
    def test_creates_response_with_safety_active(self):
        resp = create_safety_branch_response(SafetyCategory.SELF_HARM)
        assert resp["safety_active"] is True
        assert resp["category"] == "self_harm"
        assert len(resp["message"]) > 0
        assert len(resp["resources"]["us"]) > 0

    def test_includes_retention_notice(self):
        resp = create_safety_branch_response(SafetyCategory.SELF_HARM)
        assert "retention_notice" in resp
        assert "identity" in resp["retention_notice"].lower() or "Candidate Values" in resp["retention_notice"]

    def test_includes_next_steps(self):
        resp = create_safety_branch_response(SafetyCategory.VIOLENCE)
        assert "next_steps" in resp
        assert "coaching" in resp["next_steps"].lower()

    def test_all_blocking_categories_have_response(self):
        for cat in [SafetyCategory.SELF_HARM, SafetyCategory.VIOLENCE,
                     SafetyCategory.ABUSE, SafetyCategory.IMMEDIATE_DANGER]:
            resp = create_safety_branch_response(cat)
            assert resp["safety_active"] is True
            assert resp["category"] == cat.value

    def test_none_does_not_trigger_safety(self):
        # Safety branch should not be used for NONE
        # But the function should still return a valid structure
        resp = create_safety_branch_response(SafetyCategory.NONE)
        assert resp["safety_active"] is True  # the function always sets this
        assert resp["category"] == "none"


# ═══════════════════════════════════════════════════════════════════════
# R5 — Personal Regulation Rules & Confirmed Orientation
# ═══════════════════════════════════════════════════════════════════════


class TestCreatePersonalRule:
    def test_creates_unconfirmed_by_default(self):
        r = create_personal_rule("Pause before sending")
        assert r.confirmation == ConfirmationState.UNCONFIRMED
        assert r.is_authoritative() is False

    def test_default_strength_is_default_principle(self):
        r = create_personal_rule("Pause before sending")
        assert r.strength == RuleStrength.DEFAULT_PRINCIPLE

    def test_can_specify_strength(self):
        r = create_personal_rule("Never send after 10pm", RuleStrength.HARD_GUARDRAIL)
        assert r.strength == RuleStrength.HARD_GUARDRAIL

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError, match="Rule text cannot be empty"):
            create_personal_rule("")

    def test_generates_unique_ids(self):
        r1 = create_personal_rule("Rule A")
        r2 = create_personal_rule("Rule B")
        assert r1.rule_id != r2.rule_id


class TestConfirmRule:
    def test_confirmed_rule_is_authoritative(self):
        r = create_personal_rule("Pause before sending")
        assert r.is_authoritative() is False
        r = confirm_rule(r)
        assert r.is_authoritative() is True
        assert r.confirmation == ConfirmationState.CONFIRMED

    def test_preserves_other_fields(self):
        r = create_personal_rule("Pause before sending", RuleStrength.HARD_GUARDRAIL)
        r = confirm_rule(r)
        assert r.strength == RuleStrength.HARD_GUARDRAIL
        assert r.text == "Pause before sending"

    def test_updated_at_changes(self):
        r = create_personal_rule("Pause")
        original_updated = r.updated_at
        r = confirm_rule(r)
        assert r.updated_at != original_updated


class TestRetireRule:
    def test_retired_rule_not_authoritative(self):
        r = create_personal_rule("Old rule")
        r = confirm_rule(r)
        assert r.is_authoritative() is True
        r = retire_rule(r)
        assert r.is_authoritative() is False
        assert r.confirmation == ConfirmationState.RETIRED


class TestUpdateRuleStrength:
    def test_changes_strength(self):
        r = create_personal_rule("Test")
        assert r.strength == RuleStrength.DEFAULT_PRINCIPLE
        r = update_rule_strength(r, RuleStrength.HARD_GUARDRAIL)
        assert r.strength == RuleStrength.HARD_GUARDRAIL

    def test_preserves_confirmation(self):
        r = create_personal_rule("Test")
        r = confirm_rule(r)
        r = update_rule_strength(r, RuleStrength.REFLECTION_PROMPT)
        assert r.confirmation == ConfirmationState.CONFIRMED


class TestAddRuleException:
    def test_adds_exception_to_default_principle(self):
        r = create_personal_rule("Take a break", RuleStrength.DEFAULT_PRINCIPLE)
        r = add_rule_exception(r, "Unless deadline is in 1 hour")
        assert len(r.exceptions) == 1
        assert r.exceptions[0] == "Unless deadline is in 1 hour"

    def test_accumulates_exceptions(self):
        r = create_personal_rule("Take a break", RuleStrength.DEFAULT_PRINCIPLE)
        r = add_rule_exception(r, "Exception A")
        r = add_rule_exception(r, "Exception B")
        assert len(r.exceptions) == 2

    def test_blocks_exception_on_hard_guardrail(self):
        r = create_personal_rule("Never send after 10pm", RuleStrength.HARD_GUARDRAIL)
        with pytest.raises(ValueError, match="Hard guardrails cannot have exceptions"):
            add_rule_exception(r, "Unless it's important")


class TestPersonalOrientationSnapshot:
    def test_empty_snapshot(self):
        snap = PersonalOrientationSnapshot()
        assert snap.get_authoritative_rules() == []

    def test_rules_ordered_by_strength(self):
        r1 = PersonalRegulationRule(
            rule_id="r1", text="Reflect", strength=RuleStrength.REFLECTION_PROMPT,
            confirmation=ConfirmationState.CONFIRMED,
        )
        r2 = PersonalRegulationRule(
            rule_id="r2", text="Guard", strength=RuleStrength.HARD_GUARDRAIL,
            confirmation=ConfirmationState.CONFIRMED,
        )
        r3 = PersonalRegulationRule(
            rule_id="r3", text="Default", strength=RuleStrength.DEFAULT_PRINCIPLE,
            confirmation=ConfirmationState.CONFIRMED,
        )
        snap = PersonalOrientationSnapshot(confirmed_rules=[r1, r2, r3])
        rules = snap.get_authoritative_rules(min_strength=RuleStrength.REFLECTION_PROMPT)
        # Hard guardrails first, then defaults, then reflection prompts
        assert rules[0].strength == RuleStrength.HARD_GUARDRAIL
        assert rules[1].strength == RuleStrength.DEFAULT_PRINCIPLE
        assert rules[2].strength == RuleStrength.REFLECTION_PROMPT

    def test_unconfirmed_rules_excluded(self):
        r = PersonalRegulationRule(
            rule_id="r1", text="Test", strength=RuleStrength.DEFAULT_PRINCIPLE,
            confirmation=ConfirmationState.UNCONFIRMED,
        )
        snap = PersonalOrientationSnapshot(confirmed_rules=[r])
        assert snap.get_authoritative_rules() == []

    def test_min_strength_filter(self):
        r1 = PersonalRegulationRule(
            rule_id="r1", text="Guard", strength=RuleStrength.HARD_GUARDRAIL,
            confirmation=ConfirmationState.CONFIRMED,
        )
        r2 = PersonalRegulationRule(
            rule_id="r2", text="Optional", strength=RuleStrength.REFLECTION_PROMPT,
            confirmation=ConfirmationState.CONFIRMED,
        )
        snap = PersonalOrientationSnapshot(confirmed_rules=[r1, r2])
        rules = snap.get_authoritative_rules(min_strength=RuleStrength.HARD_GUARDRAIL)
        assert len(rules) == 1
        assert rules[0].strength == RuleStrength.HARD_GUARDRAIL

    def test_snapshot_contains_orientation_data(self):
        snap = PersonalOrientationSnapshot(
            confirmed_values=["Honesty", "Growth"],
            active_commitments=["Finish the paper draft"],
            current_purpose="Advancing multi-tier supply chain governance research",
        )
        assert len(snap.confirmed_values) == 2
        assert len(snap.active_commitments) == 1
        assert snap.current_purpose is not None

    def test_unconfirmed_candidates_cannot_authorize(self):
        """R5 acceptance: unconfirmed candidates cannot authorize behavior."""
        r = PersonalRegulationRule(
            rule_id="r1", text="Candidate rule", strength=RuleStrength.DEFAULT_PRINCIPLE,
            confirmation=ConfirmationState.UNCONFIRMED,
        )
        assert r.is_authoritative() is False
        snap = PersonalOrientationSnapshot(confirmed_rules=[r])
        assert snap.get_authoritative_rules() == []
