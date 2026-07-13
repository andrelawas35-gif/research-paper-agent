"""Discord Regulation rapid entry — U2 from implementation-plan-regulation-pkm.md.

ADR 0095: Web App Is Primary and Discord Is Rapid Entry.
ADR 0096: Single-Owner Private Access and Explicit Channel Linking.

Maps short Discord messages to private linked Regulation sessions.
Handles:
- Intent detection ("I'm spiraling", etc.)
- Session creation with explicit channel authorization
- Short handoff to the PWA for full guided flow
- Duplicate detection (same message → same session)
- Provider outage fallback (deterministic protocol)
- Safety keyword escalation
"""

import hashlib
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .emotional_regulation import (
    SafetyCategory,
    TriggerSession,
    begin_safety_screen,
    complete_safety_screen,
    get_deterministic_protocol,
    get_safety_resources,
    is_safety_blocking,
    start_trigger_check_in,
)
from .stores import StoreRegistry

# ═══════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════

# Base URL for PWA handoff links
_PWA_BASE_URL = os.getenv("PKM_PWA_URL", "http://localhost:5173")

# Authorized Discord channel IDs (empty = all channels authorized for owner)
_AUTHORIZED_CHANNEL_IDS: Set[str] = set(
    cid.strip()
    for cid in os.getenv("PKM_DISCORD_REGULATION_CHANNELS", "").split(",")
    if cid.strip()
)

# Maximum active sessions per channel to prevent abuse
_MAX_SESSIONS_PER_CHANNEL = 5

# Cooldown between regulation intents from the same channel (seconds)
_COOLDOWN_SECONDS = 30

# Duplicate detection window (seconds) — same trigger text in this window
# maps to the same session
_DUPLICATE_WINDOW_SECONDS = 300  # 5 minutes


# ── Intent keywords ──────────────────────────────────────────────────

_REGULATION_INTENT_PATTERNS: List[str] = [
    r"i'?m spiraling",
    r"i'?m spiral+ing",
    r"spiral(?:ing|ed)",
    r"i need to check in",
    r"trigger check",
    r"regulation check",
    r"i'?m triggered",
    r"i'?m (really )?struggling",
    r"i need (the |a )?regulation mode",
    r"start (a |the )?regulation",
    r"begin (a |the )?check.?in",
    r"quick check.?in",
    r"emergency check",
    r"help me process",
    r"talk me down",
    r"i'?m (feeling |really )?overwhelmed",
    r"i can'?t calm down",
    r"i need to pause",
    r"i need to stop (myself|before)",
]

_SAFETY_KEYWORDS: List[str] = [
    # Self-harm patterns first (most specific)
    r"(?:want to|gonna|going to) (?:hurt|harm|kill) (?:myself|me\b)",
    r"self.?harm",
    r"suicid",
    # Abuse patterns (someone hurting me)
    r"someone is (?:hurting|abusing|harming) me",
    r"i'?m being (?:abused|hurt|harmed)",
    # General danger
    r"i'?m not safe",
    r"i don'?t feel safe",
    r"immediate danger",
    # Violence toward others (least specific)
    r"(?:want to|gonna|going to) (?:hurt|harm|kill) (?:someone\b|them\b|him\b|her\b)",
]


# ═══════════════════════════════════════════════════════════════════════
# Discord Regulation Handler
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class DiscordRegulationHandler:
    """Handles regulation rapid entry from Discord.

    Maps trigger messages to private Regulation sessions and provides
    a handoff link to the PWA for full guided flow.
    """

    owner_id: str
    pwa_base_url: str = _PWA_BASE_URL
    authorized_channels: Set[str] = field(default_factory=lambda: _AUTHORIZED_CHANNEL_IDS)

    # Internal state
    _sessions: Dict[str, Tuple[TriggerSession, str]] = field(default_factory=dict)
    _recent_intents: Dict[str, float] = field(default_factory=dict)
    _channel_sessions: Dict[str, List[str]] = field(default_factory=dict)
    _dedup_hashes: Dict[str, Tuple[str, float]] = field(default_factory=dict)

    def is_authorized_channel(self, channel_id: str) -> bool:
        """Check if a Discord channel is authorized for regulation.

        If no authorized channels are configured, all channels are
        authorized (single-owner private access).
        """
        if not self.authorized_channels:
            return True
        return channel_id in self.authorized_channels

    def is_regulation_intent(self, message: str) -> bool:
        """Detect if a message signals intent to start regulation."""
        lower = message.lower().strip()
        for pattern in _REGULATION_INTENT_PATTERNS:
            if re.search(pattern, lower):
                return True
        return False

    def detect_safety_concern(self, message: str) -> Optional[SafetyCategory]:
        """Check for safety keywords requiring immediate escalation."""
        lower = message.lower().strip()
        for idx, pattern in enumerate(_SAFETY_KEYWORDS):
            if re.search(pattern, lower):
                # Patterns 0-2: self-harm
                if idx <= 2:
                    return SafetyCategory.SELF_HARM
                # Patterns 3-4: abuse (someone hurting me)
                elif idx <= 4:
                    return SafetyCategory.ABUSE
                # Patterns 5-7: immediate danger
                elif idx <= 7:
                    return SafetyCategory.IMMEDIATE_DANGER
                # Pattern 8: violence toward others
                else:
                    return SafetyCategory.VIOLENCE
        return None

    def check_cooldown(self, channel_id: str) -> Optional[str]:
        """Check if a channel is in cooldown. Returns None if OK."""
        last = self._recent_intents.get(channel_id)
        if last:
            elapsed = _now_ts() - last
            if elapsed < _COOLDOWN_SECONDS:
                remaining = int(_COOLDOWN_SECONDS - elapsed)
                return (
                    f"Please wait {remaining} seconds before starting "
                    f"another regulation session. Your last session is still "
                    f"active."
                )
        return None

    def find_duplicate_session(self, message: str) -> Optional[str]:
        """Find an existing session for a duplicate message.

        If the same trigger was sent within _DUPLICATE_WINDOW_SECONDS,
        return the existing session ID.
        """
        msg_hash = _hash_message(message)
        existing = self._dedup_hashes.get(msg_hash)
        if existing:
            session_id, timestamp = existing
            if _now_ts() - timestamp < _DUPLICATE_WINDOW_SECONDS:
                return session_id
        return None

    def create_session(
        self,
        trigger_event: str,
        channel_id: str,
        is_private: bool = False,
    ) -> Tuple[TriggerSession, str]:
        """Create a new Regulation session from a Discord message.

        Args:
            trigger_event: The message text as trigger description.
            channel_id: Discord channel ID for authorization tracking.
            is_private: If True, session is ephemeral (Private Check-In).

        Returns:
            Tuple of (session, handoff_url).
        """
        # Check channel session limit
        channel_sessions = self._channel_sessions.get(channel_id, [])
        if len(channel_sessions) >= _MAX_SESSIONS_PER_CHANNEL:
            # Expire oldest sessions
            while len(channel_sessions) >= _MAX_SESSIONS_PER_CHANNEL:
                oldest = channel_sessions.pop(0)
                self._sessions.pop(oldest, None)

        # Create session
        session = start_trigger_check_in(
            owner_id=self.owner_id,
            trigger_event=trigger_event,
            is_private=is_private,
        )

        # Auto-begin safety screen
        session = begin_safety_screen(session)

        # Track
        sid = session.session_id
        self._sessions[sid] = (session, channel_id)
        self._recent_intents[channel_id] = _now_ts()
        channel_sessions.append(sid)
        self._channel_sessions[channel_id] = channel_sessions

        # Dedup tracking
        msg_hash = _hash_message(trigger_event)
        self._dedup_hashes[msg_hash] = (sid, _now_ts())

        # Build handoff URL
        handoff_url = f"{self.pwa_base_url}/regulation?session={sid}"

        return session, handoff_url

    def get_session(self, session_id: str) -> Optional[TriggerSession]:
        """Get an active session by ID."""
        entry = self._sessions.get(session_id)
        if entry:
            return entry[0]
        return None

    def complete_safety_for_session(
        self,
        session_id: str,
        safety_category: SafetyCategory,
    ) -> Optional[TriggerSession]:
        """Complete the safety screen for a Discord-created session."""
        entry = self._sessions.get(session_id)
        if not entry:
            return None
        session, channel_id = entry
        session = complete_safety_screen(session, safety_category)
        self._sessions[session_id] = (session, channel_id)
        return session

    def build_response(
        self,
        session: TriggerSession,
        handoff_url: str,
        *,
        safety_category: Optional[SafetyCategory] = None,
        provider_available: bool = True,
    ) -> str:
        """Build the Discord response message.

        Returns a short message with session info and handoff link.
        For safety concerns, includes resources and escalation instructions.
        """
        if safety_category and is_safety_blocking(safety_category):
            return self._build_safety_response(safety_category, handoff_url)

        if not provider_available:
            return self._build_offline_response(handoff_url)

        pwa_link = f"{self.pwa_base_url}/regulation?session={session.session_id}"
        private_note = " (Private — not saved)" if session.is_private else ""

        return (
            f"**Regulation check-in started**{private_note}\n\n"
            f"Continue in the PWA for the full guided flow:\n"
            f"👉 {pwa_link}\n\n"
            f"_Session: `{session.session_id[:8]}`... — "
            f"Your progress is preserved if you close the page._\n\n"
            f"*Tip: The PWA works offline. Safety resources are always available.*"
        )

    def _build_safety_response(
        self,
        category: SafetyCategory,
        handoff_url: str,
    ) -> str:
        """Build a safety-escalation response."""
        resources = get_safety_resources(category)
        lines = [
            "⚠️ **Safety resources are available**\n",
        ]

        msg = resources.get("message", "")
        if msg:
            lines.append(msg + "\n")

        intl = resources.get("international", "")
        if intl:
            lines.append(f"**International:** {intl}")

        us = resources.get("us", "")
        if us:
            lines.append(f"**US:** {us}")

        ph = resources.get("ph", "")
        if ph:
            lines.append(f"**PH:** {ph}")

        lines.append("")
        lines.append(
            "Continue in the PWA for additional resources and guidance:\n"
            f"👉 {handoff_url}"
        )

        return "\n".join(lines)

    def _build_offline_response(self, handoff_url: str) -> str:
        """Build response when model is unavailable."""
        protocol = get_deterministic_protocol()
        steps = "\n".join(
            f"**{s['step']}:** {s['prompt']}" for s in protocol[:4]
        )

        return (
            "**AI assistance is currently unavailable.**\n\n"
            "Here's the offline regulation protocol to help you work through "
            "this on your own:\n\n"
            f"{steps}\n\n"
            "Continue in the PWA for the full guided flow:\n"
            f"👉 {handoff_url}\n\n"
            "_Safety resources remain available at all times._"
        )


# ═══════════════════════════════════════════════════════════════════════
# Message processor (call from discord_bot.py)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ProcessResult:
    """Result of processing a Discord message for regulation intent."""
    is_regulation: bool
    response: Optional[str] = None
    session_id: Optional[str] = None
    safety_concern: bool = False


def process_discord_message(
    handler: DiscordRegulationHandler,
    message: str,
    channel_id: str,
    *,
    provider_available: bool = True,
) -> ProcessResult:
    """Process a Discord message for regulation intent.

    This is the main entry point called from discord_bot.py before
    the message reaches the ADK agent.

    Args:
        handler: The DiscordRegulationHandler instance.
        message: The raw message text.
        channel_id: The Discord channel ID.
        provider_available: Whether the model provider is available.

    Returns:
        ProcessResult indicating whether this was a regulation intent
        and the response to send.
    """
    # 1. Check channel authorization
    if not handler.is_authorized_channel(channel_id):
        return ProcessResult(is_regulation=False)

    # 2. Check safety keywords FIRST — safety bypasses all other checks
    safety_category = handler.detect_safety_concern(message)
    if safety_category:
        # Safety concerns always create a private session
        session, handoff = handler.create_session(
            message[:200],
            channel_id,
            is_private=True,
        )
        handler.complete_safety_for_session(session.session_id, safety_category)
        return ProcessResult(
            is_regulation=True,
            response=handler.build_response(
                session,
                handoff,
                safety_category=safety_category,
                provider_available=provider_available,
            ),
            session_id=session.session_id,
            safety_concern=True,
        )

    # 3. Check regulation intent
    if not handler.is_regulation_intent(message):
        return ProcessResult(is_regulation=False)

    # 4. Check cooldown
    cooldown = handler.check_cooldown(channel_id)
    if cooldown:
        return ProcessResult(
            is_regulation=True,
            response=cooldown,
        )

    # 5. Check for duplicate
    existing_id = handler.find_duplicate_session(message)
    if existing_id:
        session = handler.get_session(existing_id)
        if session:
            handoff = f"{handler.pwa_base_url}/regulation?session={existing_id}"
            return ProcessResult(
                is_regulation=True,
                response=(
                    "You already have an active regulation session for this. "
                    f"Continue here:\n👉 {handoff}"
                ),
                session_id=existing_id,
            )

    # 6. Create normal regulation session
    session, handoff = handler.create_session(
        message[:200],
        channel_id,
        is_private=False,
    )
    return ProcessResult(
        is_regulation=True,
        response=handler.build_response(
            session,
            handoff,
            provider_available=provider_available,
        ),
        session_id=session.session_id,
    )


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _hash_message(message: str) -> str:
    """Create a short hash of a message for dedup."""
    return hashlib.sha256(
        message.lower().strip().encode()
    ).hexdigest()[:16]
