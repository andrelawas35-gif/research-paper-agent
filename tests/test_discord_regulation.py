"""Tests for U2: Discord Regulation rapid entry."""

import pytest

# Override the conftest autouse fixture — these tests are self-contained.
@pytest.fixture(autouse=True)
def _isolate_paths(monkeypatch, tmp_path):
    """No-op: Discord regulation tests do not need file-system isolation."""
    pass

from agent_runtime.discord_regulation import (
    DiscordRegulationHandler,
    process_discord_message,
    ProcessResult,
)
from agent_runtime.emotional_regulation import SafetyCategory


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def handler() -> DiscordRegulationHandler:
    return DiscordRegulationHandler(
        owner_id="test-owner",
        pwa_base_url="http://localhost:5173",
    )


# ── Intent detection tests ───────────────────────────────────────────


class TestIntentDetection:
    def test_detect_spiraling(self, handler):
        assert handler.is_regulation_intent("I'm spiraling")
        assert handler.is_regulation_intent("i'm spiraling right now")
        assert handler.is_regulation_intent("IM SPIRALING")

    def test_detect_check_in(self, handler):
        assert handler.is_regulation_intent("I need to check in")
        assert handler.is_regulation_intent("trigger check please")
        assert handler.is_regulation_intent("start a regulation session")

    def test_detect_overwhelmed(self, handler):
        assert handler.is_regulation_intent("I'm feeling overwhelmed")
        assert handler.is_regulation_intent("i can't calm down")
        assert handler.is_regulation_intent("I need to pause")

    def test_detect_help_phrases(self, handler):
        assert handler.is_regulation_intent("help me process something")
        assert handler.is_regulation_intent("talk me down please")
        assert handler.is_regulation_intent("i need to stop myself")

    def test_no_false_positive(self, handler):
        assert not handler.is_regulation_intent("hello world")
        assert not handler.is_regulation_intent("how are you today")
        assert not handler.is_regulation_intent("check in at the hotel")


# ── Safety detection tests ───────────────────────────────────────────


class TestSafetyDetection:
    def test_detect_self_harm(self, handler):
        cat = handler.detect_safety_concern("I want to hurt myself")
        assert cat == SafetyCategory.SELF_HARM

        cat = handler.detect_safety_concern("i'm gonna kill myself")
        assert cat == SafetyCategory.SELF_HARM

    def test_detect_violence(self, handler):
        cat = handler.detect_safety_concern("I want to hurt someone")
        assert cat == SafetyCategory.VIOLENCE

    def test_detect_abuse(self, handler):
        cat = handler.detect_safety_concern("someone is abusing me")
        assert cat == SafetyCategory.ABUSE

    def test_detect_no_safety_concern(self, handler):
        cat = handler.detect_safety_concern("I'm spiraling about work")
        assert cat is None


# ── Channel authorization tests ──────────────────────────────────────


class TestChannelAuthorization:
    def test_all_channels_authorized_when_none_configured(self, handler):
        assert handler.is_authorized_channel("any-channel-id")

    def test_specific_channel_authorized(self):
        handler = DiscordRegulationHandler(
            owner_id="test",
            authorized_channels={"chan-123", "chan-456"},
        )
        assert handler.is_authorized_channel("chan-123")
        assert not handler.is_authorized_channel("chan-999")


# ── Cooldown tests ───────────────────────────────────────────────────


class TestCooldown:
    def test_no_cooldown_initially(self, handler):
        assert handler.check_cooldown("chan-1") is None

    def test_cooldown_after_intent(self, handler):
        process_discord_message(handler, "I'm spiraling", "chan-1")
        cooldown = handler.check_cooldown("chan-1")
        assert cooldown is not None
        assert "seconds" in cooldown


# ── Duplicate detection tests ────────────────────────────────────────


class TestDuplicateDetection:
    def test_duplicate_detected(self, handler):
        result1 = process_discord_message(handler, "I'm spiraling", "chan-1")
        assert result1.is_regulation
        assert result1.session_id is not None

        # Manually reset cooldown to test duplicate detection
        handler._recent_intents.clear()
        result2 = process_discord_message(handler, "I'm spiraling", "chan-1")
        assert result2.is_regulation
        assert "already have an active" in (result2.response or "")

    def test_different_messages_not_duplicates(self, handler):
        result1 = process_discord_message(handler, "I'm spiraling", "chan-1")
        assert result1.session_id is not None

        result2 = process_discord_message(handler, "I need to check in", "chan-1")
        assert result2.is_regulation
        # Should not say "already have an active" because it's a different trigger
        assert "already have an active" not in (result2.response or "")


# ── Session creation tests ───────────────────────────────────────────


class TestSessionCreation:
    def test_creates_session_with_handoff_link(self, handler):
        result = process_discord_message(handler, "I'm spiraling about a text", "chan-1")
        assert result.is_regulation
        assert result.response is not None
        assert "http://localhost:5173/regulation?session=" in result.response
        assert result.session_id is not None

    def test_truncates_long_message(self, handler):
        long_msg = "I'm spiraling " + "very " * 100 + "badly"
        result = process_discord_message(handler, long_msg, "chan-1")
        assert result.is_regulation
        # Session should have been created with truncated trigger
        session = handler.get_session(result.session_id or "")
        assert session is not None
        assert len(session.trigger_event or "") <= 200


# ── Safety escalation tests ──────────────────────────────────────────


class TestSafetyEscalation:
    def test_safety_concern_creates_private_session(self, handler):
        result = process_discord_message(handler, "I want to hurt myself", "chan-1")
        assert result.is_regulation
        assert result.safety_concern
        assert result.session_id is not None

        session = handler.get_session(result.session_id or "")
        assert session is not None
        assert session.is_private is True

    def test_safety_response_has_resources(self, handler):
        result = process_discord_message(handler, "I want to hurt myself", "chan-1")
        assert "Safety resources" in (result.response or "")
        assert "http://localhost:5173/regulation?session=" in (result.response or "")


# ── Provider outage tests ────────────────────────────────────────────


class TestProviderOutage:
    def test_offline_response(self, handler):
        result = process_discord_message(
            handler,
            "I'm spiraling",
            "chan-1",
            provider_available=False,
        )
        assert result.is_regulation
        assert "AI assistance is currently unavailable" in (result.response or "")
        assert "offline regulation protocol" in (result.response or "")


# ── Non-regulation messages ──────────────────────────────────────────


class TestNonRegulationMessages:
    def test_normal_message_not_regulation(self, handler):
        result = process_disscord_message = process_discord_message(
            handler, "hello how are you", "chan-1"
        )
        assert not result.is_regulation
        assert result.response is None


# ── Unauthorized channel ─────────────────────────────────────────────


class TestUnauthorizedChannel:
    def test_unauthorized_channel_ignored(self):
        handler = DiscordRegulationHandler(
            owner_id="test",
            authorized_channels={"chan-123"},
        )
        result = process_discord_message(handler, "I'm spiraling", "chan-999")
        assert not result.is_regulation
