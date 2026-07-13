"""Tests for F4: API, authentication, health, and audit seams."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
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
from agent_runtime.auth_sessions import OwnerSessionManager


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


def session_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/session", headers={"X-API-Key": "test-api-key"}
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['token']}"}


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

    def test_ready_degrades_when_external_key_custody_is_unavailable(
        self, config: ApiConfig, registry: StoreRegistry, audit: AuditLogger
    ) -> None:
        def unavailable() -> None:
            raise RuntimeError("provider unavailable")

        app = create_app(
            store_registry=registry,
            config=config,
            audit=audit,
            readiness_checks={"record_key_provider": unavailable},
        )

        response = TestClient(app).get("/health/ready")

        assert response.status_code == 503
        assert response.json()["checks"]["record_key_provider"] == "error"


# ── Authentication ───────────────────────────────────────────────────


class TestAuthentication:
    def test_owner_key_exchanges_for_server_session(self, client: TestClient) -> None:
        login = client.post(
            "/api/auth/session", headers={"X-API-Key": "test-api-key"}
        )

        assert login.status_code == 201
        body = login.json()
        assert body["token"]
        assert body["expires_at"]
        response = client.get(
            "/api/me", headers={"Authorization": f"Bearer {body['token']}"}
        )
        assert response.status_code == 200
        assert response.json()["authenticated"] is True

    def test_sensitive_governance_requires_recent_auth(
        self,
        config: ApiConfig,
        registry: StoreRegistry,
        audit: AuditLogger,
    ) -> None:
        now = [datetime(2026, 7, 13, tzinfo=timezone.utc)]
        sessions = OwnerSessionManager(clock=lambda: now[0])
        app = create_app(
            store_registry=registry,
            config=config,
            audit=audit,
            owner_id="test-owner",
            auth_sessions=sessions,
        )
        scoped_client = TestClient(app)
        token = scoped_client.post(
            "/api/auth/session", headers={"X-API-Key": "test-api-key"}
        ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        now[0] += timedelta(minutes=6)

        assert scoped_client.get(
            "/api/privacy/sessions", headers=headers
        ).status_code == 200
        response = scoped_client.post(
            "/api/privacy/export", headers=headers, json={"scope": "all"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Recent owner authentication required"

    def test_protected_endpoint_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/me")
        assert response.status_code == 401

    def test_protected_endpoint_with_valid_session(self, client: TestClient) -> None:
        response = client.get("/api/me", headers=session_headers(client))
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

    def test_regulation_endpoints_require_auth(self, client: TestClient) -> None:
        response = client.get("/api/regulation/sessions")
        assert response.status_code == 401

    def test_privacy_endpoints_require_auth(self, client: TestClient) -> None:
        response = client.get("/api/privacy/summary")
        assert response.status_code == 401

    def test_discarding_private_session_removes_it_from_memory(
        self, client: TestClient
    ) -> None:
        headers = session_headers(client)
        created = client.post(
            "/api/regulation/sessions",
            headers=headers,
            json={"trigger_event": "temporary", "is_private": True},
        ).json()

        response = client.post(
            f"/api/regulation/sessions/{created['session_id']}/expire",
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["state"] == "expired"
        assert client.get(
            f"/api/regulation/sessions/{created['session_id']}", headers=headers
        ).status_code == 404


# ── Audit ────────────────────────────────────────────────────────────


class TestAudit:
    def test_audit_endpoint_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/audit")
        assert response.status_code == 401

    def test_audit_returns_metadata_only(self, client: TestClient) -> None:
        # Make a request to generate audit entry
        headers = session_headers(client)
        client.get("/api/me", headers=headers)
        response = client.get("/api/audit", headers=headers)
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
            headers=session_headers(client),
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
