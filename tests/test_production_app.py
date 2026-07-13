"""Fail-closed startup tests for the production ASGI factory."""

from __future__ import annotations

import hashlib

import pytest

from agent_runtime.asgi import create_production_app
from agent_runtime.record_keys import FileRecordKeyProvider


def test_production_requires_owner_auth(monkeypatch) -> None:
    monkeypatch.delenv("PKM_API_KEY_HASH", raising=False)
    monkeypatch.setenv("REGULATION_KEY", "ab" * 32)
    with pytest.raises(RuntimeError, match="PKM_API_KEY_HASH"):
        create_production_app()


def test_production_does_not_require_vm_master_key_with_off_vm_record_keys(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv(
        "PKM_API_KEY_HASH", hashlib.sha256(b"owner-secret").hexdigest()
    )
    monkeypatch.delenv("REGULATION_KEY", raising=False)
    monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
    monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)
    monkeypatch.setenv("PKM_DATA_DIR", str(tmp_path / "data"))

    app = create_production_app(
        record_key_provider=FileRecordKeyProvider(tmp_path / "record-keys")
    )

    assert app.title == "Personal Knowledge Manager"


def test_production_starts_with_auth_and_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(
        "PKM_API_KEY_HASH", hashlib.sha256(b"owner-secret").hexdigest()
    )
    monkeypatch.setenv("REGULATION_KEY", "ab" * 32)
    monkeypatch.setenv("PKM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AUDIT_LOG_DIR", str(tmp_path / "audit"))

    app = create_production_app(
        record_key_provider=FileRecordKeyProvider(tmp_path / "record-keys")
    )

    assert app.title == "Personal Knowledge Manager"


def test_production_requires_off_vm_record_key_provider(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(
        "PKM_API_KEY_HASH", hashlib.sha256(b"owner-secret").hexdigest()
    )
    monkeypatch.setenv("REGULATION_KEY", "ab" * 32)
    monkeypatch.setenv("PKM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("REGULATION_RECORD_KEY_PROVIDER", raising=False)

    with pytest.raises(RuntimeError, match="must be 'oci'"):
        create_production_app()
