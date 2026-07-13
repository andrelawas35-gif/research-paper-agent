"""Fail-closed startup tests for the production ASGI factory."""

from __future__ import annotations

import hashlib

import pytest

from agent_runtime.asgi import create_production_app


def test_production_requires_owner_auth(monkeypatch) -> None:
    monkeypatch.delenv("PKM_API_KEY_HASH", raising=False)
    monkeypatch.setenv("REGULATION_KEY", "ab" * 32)
    with pytest.raises(RuntimeError, match="PKM_API_KEY_HASH"):
        create_production_app()


def test_production_requires_regulation_key(monkeypatch) -> None:
    monkeypatch.setenv(
        "PKM_API_KEY_HASH", hashlib.sha256(b"owner-secret").hexdigest()
    )
    monkeypatch.delenv("REGULATION_KEY", raising=False)
    monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
    monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)
    with pytest.raises(Exception, match="encryption key"):
        create_production_app()


def test_production_starts_with_auth_and_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(
        "PKM_API_KEY_HASH", hashlib.sha256(b"owner-secret").hexdigest()
    )
    monkeypatch.setenv("REGULATION_KEY", "ab" * 32)
    monkeypatch.setenv("PKM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AUDIT_LOG_DIR", str(tmp_path / "audit"))

    app = create_production_app()

    assert app.title == "Personal Knowledge Manager"
