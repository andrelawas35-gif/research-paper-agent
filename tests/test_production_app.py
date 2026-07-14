"""Fail-closed startup tests for the production ASGI factory."""

from __future__ import annotations

import hashlib

import pytest

from agent_runtime import asgi
from agent_runtime.record_keys import FileRecordKeyProvider


def _create_without_project_env(**kwargs):
    return asgi.create_production_app(load_project_env=False, **kwargs)


def test_production_requires_owner_auth(monkeypatch) -> None:
    monkeypatch.delenv("PKM_API_KEY_HASH", raising=False)
    monkeypatch.setenv("REGULATION_KEY", "ab" * 32)
    with pytest.raises(RuntimeError, match="PKM_API_KEY_HASH"):
        _create_without_project_env()


def test_production_loads_project_env_for_local_launch(monkeypatch, tmp_path) -> None:
    project_env = tmp_path / ".env"
    project_env.write_text(
        "PKM_API_KEY_HASH=" + hashlib.sha256(b"owner-secret").hexdigest() + "\n"
    )
    monkeypatch.delenv("PKM_API_KEY_HASH", raising=False)
    monkeypatch.setattr(asgi, "PROJECT_ENV_PATH", project_env)

    app = asgi.create_production_app(
        record_key_provider=FileRecordKeyProvider(tmp_path / "record-keys")
    )

    assert app.title == "Personal Knowledge Manager"


def test_local_app_uses_file_record_keys_without_oci(monkeypatch, tmp_path) -> None:
    project_env = tmp_path / ".env"
    project_env.write_text(
        "PKM_API_KEY_HASH=" + hashlib.sha256(b"owner-secret").hexdigest() + "\n"
    )
    monkeypatch.delenv("PKM_API_KEY_HASH", raising=False)
    monkeypatch.delenv("REGULATION_RECORD_KEY_PROVIDER", raising=False)
    monkeypatch.setenv("PKM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(asgi, "PROJECT_ENV_PATH", project_env)

    app = asgi.create_local_app()

    assert app.title == "Personal Knowledge Manager"


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

    app = _create_without_project_env(
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

    app = _create_without_project_env(
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
        _create_without_project_env()
