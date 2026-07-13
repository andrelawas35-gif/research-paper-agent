"""Short-lived, revocable owner sessions for the single-owner PWA."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable


class InvalidSessionError(ValueError):
    pass


class RecentAuthenticationRequired(PermissionError):
    pass


@dataclass(frozen=True)
class IssuedSession:
    token: str
    expires_at: str
    recent_auth_until: str


@dataclass
class _SessionState:
    absolute_expires_at: datetime
    expires_at: datetime
    recent_auth_until: datetime


class OwnerSessionManager:
    """Keeps only token digests and enforces idle, absolute, and recent TTLs."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        idle_ttl: timedelta = timedelta(minutes=15),
        absolute_ttl: timedelta = timedelta(hours=8),
        recent_auth_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._idle_ttl = idle_ttl
        self._absolute_ttl = absolute_ttl
        self._recent_auth_ttl = recent_auth_ttl
        self._sessions: dict[str, _SessionState] = {}

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(self) -> IssuedSession:
        now = self._clock()
        token = secrets.token_urlsafe(32)
        absolute = now + self._absolute_ttl
        expires = min(now + self._idle_ttl, absolute)
        recent = min(now + self._recent_auth_ttl, absolute)
        self._sessions[self._digest(token)] = _SessionState(
            absolute_expires_at=absolute,
            expires_at=expires,
            recent_auth_until=recent,
        )
        return IssuedSession(
            token=token,
            expires_at=expires.isoformat(),
            recent_auth_until=recent.isoformat(),
        )

    def validate(self, token: str, *, require_recent: bool = False) -> None:
        digest = self._digest(token)
        state = self._sessions.get(digest)
        now = self._clock()
        if state is None or now >= state.expires_at or now >= state.absolute_expires_at:
            self._sessions.pop(digest, None)
            raise InvalidSessionError("Session is missing or expired")
        if require_recent and now >= state.recent_auth_until:
            raise RecentAuthenticationRequired("Recent owner authentication required")
        state.expires_at = min(now + self._idle_ttl, state.absolute_expires_at)

    def revoke(self, token: str) -> None:
        self._sessions.pop(self._digest(token), None)
