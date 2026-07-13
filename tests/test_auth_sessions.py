"""Behavioral tests for expiring and revocable owner sessions."""

from datetime import datetime, timedelta, timezone

import pytest

from agent_runtime.auth_sessions import (
    InvalidSessionError,
    OwnerSessionManager,
    RecentAuthenticationRequired,
)


def test_session_expires_on_idle_and_can_be_revoked() -> None:
    now = [datetime(2026, 7, 13, tzinfo=timezone.utc)]
    manager = OwnerSessionManager(clock=lambda: now[0])
    issued = manager.issue()
    manager.validate(issued.token)

    now[0] += timedelta(minutes=16)
    with pytest.raises(InvalidSessionError):
        manager.validate(issued.token)

    replacement = manager.issue()
    manager.revoke(replacement.token)
    with pytest.raises(InvalidSessionError):
        manager.validate(replacement.token)


def test_recent_auth_window_is_shorter_than_session_lifetime() -> None:
    now = [datetime(2026, 7, 13, tzinfo=timezone.utc)]
    manager = OwnerSessionManager(clock=lambda: now[0])
    issued = manager.issue()
    now[0] += timedelta(minutes=6)

    manager.validate(issued.token)
    with pytest.raises(RecentAuthenticationRequired):
        manager.validate(issued.token, require_recent=True)
