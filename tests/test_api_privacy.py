"""Tests for U3: Privacy Center API endpoints."""

import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

# Override conftest autouse fixture
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    pass

from fastapi.testclient import TestClient

from agent_runtime.api_privacy import create_privacy_router
from agent_runtime.api_regulation import create_regulation_router
from agent_runtime.model_provider import FakeProvider
from agent_runtime.stores import StoreRegistry
from agent_runtime.emotional_regulation import start_trigger_check_in


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def registry() -> StoreRegistry:
    reg = StoreRegistry()
    reg.operational.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
    reg.general_pkm.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
    reg.regulation.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
    return reg


@pytest.fixture
def shared_sessions() -> Dict[str, Any]:
    return {}


@pytest.fixture
def shared_rules() -> Dict[str, Any]:
    return {}


@pytest.fixture
def client(
    registry: StoreRegistry,
    shared_sessions: Dict[str, Any],
    shared_rules: Dict[str, Any],
):
    """Create a test client with both regulation and privacy routers sharing state."""
    provider = FakeProvider()
    from fastapi import FastAPI
    app = FastAPI()

    reg_router = create_regulation_router(
        store_registry=registry,
        owner_id="test-owner",
        model_provider=provider,
        sessions_dict=shared_sessions,
        rules_dict=shared_rules,
    )
    priv_router = create_privacy_router(
        store_registry=registry,
        owner_id="test-owner",
        sessions_dict=shared_sessions,
        rules_dict=shared_rules,
    )
    app.include_router(reg_router)
    app.include_router(priv_router)
    return TestClient(app)


def _create_session(client) -> str:
    """Create a session via the regulation API and return its ID."""
    create = client.post(
        "/api/regulation/sessions",
        json={"trigger_event": "Test trigger for privacy"},
    )
    assert create.status_code == 200
    sid = create.json()["session_id"]
    # Complete safety screen to activate
    client.post(
        f"/api/regulation/sessions/{sid}/safety-screen",
        json={"safety_category": "none"},
    )
    # Complete the session
    client.post(f"/api/regulation/sessions/{sid}/complete")
    return sid


# ── Summary tests ────────────────────────────────────────────────────


class TestPrivacySummary:
    def test_empty_summary(self, client):
        res = client.get("/api/privacy/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["session_count"] == 0
        assert data["rule_count"] >= 0  # might have default safety rules


# ── Session listing tests ────────────────────────────────────────────


class TestListSessions:
    def test_list_sessions(self, client):
        _create_session(client)

        res = client.get("/api/privacy/sessions")
        assert res.status_code == 200
        assert len(res.json()["sessions"]) >= 1

    def test_session_has_expiry(self, client):
        sid = _create_session(client)

        res = client.get("/api/privacy/sessions")
        sessions = res.json()["sessions"]
        session = next(s for s in sessions if s["session_id"] == sid)
        assert "expires_at" in session


# ── Session inspection tests ─────────────────────────────────────────


class TestInspectSession:
    def test_inspect_session(self, client):
        sid = _create_session(client)

        res = client.get(f"/api/privacy/sessions/{sid}")
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == sid
        assert data["trigger_event"] == "Test trigger for privacy"
        assert "facts" in data
        assert "interpretations" in data
        assert "emotions" in data

    def test_inspect_nonexistent(self, client):
        res = client.get("/api/privacy/sessions/nonexistent")
        assert res.status_code == 404


# ── Deletion tests ───────────────────────────────────────────────────


class TestDeleteSession:
    def test_delete_single_session(self, client):
        sid = _create_session(client)

        res = client.delete(f"/api/privacy/sessions/{sid}")
        assert res.status_code == 200
        assert res.json()["deleted"] is True

        # Verify deletion
        res = client.get(f"/api/privacy/sessions/{sid}")
        assert res.status_code == 404

    def test_delete_nonexistent(self, client):
        res = client.delete("/api/privacy/sessions/nonexistent")
        assert res.status_code == 404

    def test_delete_all_sessions(self, client):
        _create_session(client)
        _create_session(client)

        res = client.delete("/api/privacy/sessions")
        assert res.status_code == 200
        assert res.json()["deleted_count"] == 2

        # Verify all gone
        res = client.get("/api/privacy/sessions")
        assert len(res.json()["sessions"]) == 0

    def test_failed_key_deletion_keeps_session_in_memory(self, registry):
        from fastapi import FastAPI

        session = start_trigger_check_in("test-owner", "still recoverable")
        sessions = {session.session_id: session}

        class FailingPersistence:
            def delete_session(self, session_id: str) -> None:
                raise RuntimeError("key custody unavailable")

        app = FastAPI()
        app.include_router(create_privacy_router(
            store_registry=registry,
            owner_id="test-owner",
            sessions_dict=sessions,
            rules_dict={},
            persistence=FailingPersistence(),
        ))

        with TestClient(app, raise_server_exceptions=False) as failing_client:
            response = failing_client.delete(
                f"/api/privacy/sessions/{session.session_id}"
            )

        assert response.status_code == 500
        assert session.session_id in sessions

    def test_failed_bulk_key_deletion_keeps_sessions_in_memory(self, registry):
        from fastapi import FastAPI

        session = start_trigger_check_in("test-owner", "still recoverable")
        sessions = {session.session_id: session}

        class FailingPersistence:
            def delete_all_sessions(self) -> None:
                raise RuntimeError("key custody unavailable")

        app = FastAPI()
        app.include_router(create_privacy_router(
            store_registry=registry,
            owner_id="test-owner",
            sessions_dict=sessions,
            rules_dict={},
            persistence=FailingPersistence(),
        ))

        with TestClient(app, raise_server_exceptions=False) as failing_client:
            response = failing_client.delete("/api/privacy/sessions")

        assert response.status_code == 500
        assert session.session_id in sessions


# ── Export tests ─────────────────────────────────────────────────────


class TestExport:
    def test_export_all_data(self, client):
        _create_session(client)

        res = client.post("/api/privacy/export", json={"scope": "all"})
        assert res.status_code == 200
        data = res.json()
        assert "export_id" in data
        assert data["session_count"] >= 1
        assert "sessions" in data
        assert "rules" in data

    def test_export_durable_only(self, client):
        _create_session(client)

        res = client.post("/api/privacy/export", json={"scope": "durable"})
        assert res.status_code == 200
        assert res.json()["scope"] == "durable"


# ── Audit tests ──────────────────────────────────────────────────────


class TestAudit:
    def test_get_audit_log(self, client):
        res = client.get("/api/privacy/audit")
        assert res.status_code == 200
        assert "count" in res.json()
        assert "entries" in res.json()


# ── Retention tests ──────────────────────────────────────────────────


class TestRetention:
    def test_retention_info(self, client):
        _create_session(client)

        res = client.get("/api/privacy/retention")
        assert res.status_code == 200
        data = res.json()
        assert data["default_retention_days"] == 365
        assert data["private_checkin_retention_hours"] == 24
        assert "sessions" in data


# ── Consent tests ────────────────────────────────────────────────────


class TestConsent:
    def test_update_consent(self, client):
        res = client.put(
            "/api/privacy/consent",
            json={"consent_type": "model_assisted_regulation", "granted": True},
        )
        assert res.status_code == 200
        assert res.json()["granted"] is True

    def test_update_consent_invalid(self, client):
        res = client.put(
            "/api/privacy/consent",
            json={"consent_type": "", "granted": True},
        )
        assert res.status_code == 400

    def test_update_consent_non_bool(self, client):
        res = client.put(
            "/api/privacy/consent",
            json={"consent_type": "test", "granted": "not_a_bool"},
        )
        assert res.status_code == 400


# ── Cross-router state sharing tests ─────────────────────────────────


class TestCrossRouterSharing:
    def test_regulation_session_visible_in_privacy(self, client):
        """Sessions created via regulation API should be visible in privacy API."""
        sid = _create_session(client)

        # Privacy API should see the same session
        res = client.get(f"/api/privacy/sessions/{sid}")
        assert res.status_code == 200

    def test_rule_created_in_regulation_visible_in_privacy_summary(self, client):
        """Rules created via regulation API should affect privacy summary."""
        client.post(
            "/api/regulation/rules",
            json={"text": "Cross-router test rule"},
        )

        # Privacy summary should reflect the new rule
        res = client.get("/api/privacy/summary")
        assert res.json()["rule_count"] >= 1
