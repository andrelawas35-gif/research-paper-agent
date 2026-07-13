"""Tests for F4: API, authentication, health, and audit seams."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


# Override the conftest autouse fixture — API tests are self-contained.
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    """No-op: API tests do not need file-system isolation."""
    pass


from fastapi.testclient import TestClient

from agent_runtime.api import (
    ApiConfig,
    AuditLogger,
    create_app,
    verify_api_key,
)
from agent_runtime.stores import StoreRegistry


# ── Helpers ──────────────────────────────────────────────────────────


@pytest.fixture
def api_key_hash() -> str:
    import hashlib
    return hashlib.sha256("test-api-key".encode()).hexdigest()


@pytest.fixture
def config(api_key_hash: str) -> ApiConfig:
    return ApiConfig(owner_api_key_hash=api_key_hash)


@pytest.fixture
def registry() -> StoreRegistry:
    reg = StoreRegistry()
    reg.operational.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
    reg.general_pkm.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
    reg.regulation.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
    return reg


@pytest.fixture
def audit() -> AuditLogger:
    al = AuditLogger()
    al.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
    return al


@pytest.fixture
def client(config: ApiConfig, registry: StoreRegistry, audit: AuditLogger) -> TestClient:
    app = create_app(
        store_registry=registry,
        config=config,
        audit=audit,
        owner_id="test-owner",
    )
    return TestClient(app)


# ── API Key Verification ─────────────────────────────────────────────


class TestVerifyApiKey:
    def test_correct_key_passes(self, api_key_hash: str) -> None:
        assert verify_api_key("test-api-key", api_key_hash) is True

    def test_wrong_key_fails(self, api_key_hash: str) -> None:
        assert verify_api_key("wrong-key", api_key_hash) is False

    def test_empty_key_fails(self, api_key_hash: str) -> None:
        assert verify_api_key("", api_key_hash) is False

    def test_empty_hash_fails(self) -> None:
        assert verify_api_key("any-key", "") is False

    def test_constant_time(self, api_key_hash: str) -> None:
        # Should not leak timing info — just verify it works
        assert verify_api_key("test-api-key", api_key_hash) is True
        assert verify_api_key("test-api-keyx", api_key_hash) is False


# ── Health endpoints ─────────────────────────────────────────────────


class TestHealthEndpoints:
    def test_health_no_auth_required(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_does_not_reveal_sensitive_data(self, client: TestClient) -> None:
        response = client.get("/health")
        data = response.json()
        assert "regulation" not in str(data).lower()
        assert "events" not in data
        assert "keys" not in data

    def test_ready_no_auth_required(self, client: TestClient) -> None:
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "operational_store" in data["checks"]
        assert "general_pkm_store" in data["checks"]
        assert "regulation_store" in data["checks"]


# ── Authentication ───────────────────────────────────────────────────


class TestAuthentication:
    def test_protected_endpoint_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/me")
        assert response.status_code == 401

    def test_protected_endpoint_with_valid_key(self, client: TestClient) -> None:
        response = client.get("/api/me", headers={"X-API-Key": "test-api-key"})
        assert response.status_code == 200
        data = response.json()
        assert data["owner_id"] == "test-owner"
        assert data["authenticated"] is True

    def test_protected_endpoint_with_invalid_key(self, client: TestClient) -> None:
        response = client.get("/api/me", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401

    def test_401_message_does_not_leak_details(self, client: TestClient) -> None:
        response = client.get("/api/me")
        assert response.status_code == 401
        # Generic message, no hints about key format or owner
        data = response.json()
        assert "detail" in data
        assert "key" not in data["detail"].lower()
        assert "sha" not in data["detail"].lower()


# ── Audit ────────────────────────────────────────────────────────────


class TestAudit:
    def test_audit_endpoint_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/audit")
        assert response.status_code == 401

    def test_audit_returns_metadata_only(self, client: TestClient) -> None:
        # Make a request to generate audit entry
        client.get("/api/me", headers={"X-API-Key": "test-api-key"})
        response = client.get("/api/audit", headers={"X-API-Key": "test-api-key"})
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "entries" in data
        for entry in data["entries"]:
            # Metadata-only: no payload content
            assert "endpoint" in entry
            assert "payload" not in entry


# ── Store summary ────────────────────────────────────────────────────


class TestStoreSummary:
    def test_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/stores/summary")
        assert response.status_code == 401

    def test_returns_event_counts(self, client: TestClient) -> None:
        response = client.get(
            "/api/stores/summary",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "operational_events" in data
        assert "general_pkm_events" in data
        assert "regulation_events" in data
        # All should be 0 for fresh stores
        assert data["regulation_events"] == 0


# ── ApiConfig ────────────────────────────────────────────────────────


class TestApiConfig:
    def test_is_configured_with_key(self, api_key_hash: str) -> None:
        cfg = ApiConfig(owner_api_key_hash=api_key_hash)
        assert cfg.is_configured is True

    def test_is_not_configured_without_key(self) -> None:
        cfg = ApiConfig(owner_api_key_hash="")
        assert cfg.is_configured is False
