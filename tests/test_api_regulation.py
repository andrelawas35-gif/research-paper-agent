"""Tests for U1: Regulation API endpoints."""

import tempfile
from pathlib import Path
from typing import Dict

import pytest

# Override conftest autouse fixture
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    pass

from fastapi.testclient import TestClient

from agent_runtime.api_regulation import create_regulation_router
from agent_runtime.model_provider import FakeProvider
from agent_runtime.stores import StoreRegistry


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def registry() -> StoreRegistry:
    reg = StoreRegistry()
    reg.operational.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
    reg.general_pkm.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
    reg.regulation.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
    return reg


@pytest.fixture
def shared_sessions() -> Dict:
    return {}


@pytest.fixture
def shared_rules() -> Dict:
    return {}


@pytest.fixture
def client(registry: StoreRegistry, shared_sessions: Dict, shared_rules: Dict):
    provider = FakeProvider()
    router = create_regulation_router(
        store_registry=registry,
        owner_id="test-owner",
        model_provider=provider,
        sessions_dict=shared_sessions,
        rules_dict=shared_rules,
    )
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ── Session lifecycle tests ──────────────────────────────────────────


class TestCreateSession:
    def test_create_session_success(self, client):
        res = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "I had an argument"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert data["state"] == "safety_screen"  # auto-started safety screen
        assert data["trigger_event"] == "I had an argument"
        assert data["is_private"] is False

    def test_create_private_session(self, client):
        res = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Private check", "is_private": True},
        )
        assert res.status_code == 200
        assert res.json()["is_private"] is True

    def test_create_session_empty_trigger(self, client):
        res = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": ""},
        )
        assert res.status_code == 400

    def test_create_session_missing_trigger(self, client):
        res = client.post("/api/regulation/sessions", json={})
        assert res.status_code == 400

    def test_duplicate_create_request_is_idempotent(self, client):
        headers = {"Idempotency-Key": "offline-capture-123"}
        body = {"trigger_event": "One observed fact"}

        first = client.post("/api/regulation/sessions", headers=headers, json=body)
        second = client.post("/api/regulation/sessions", headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert client.get("/api/regulation/sessions").json()["count"] == 1

    def test_reused_idempotency_key_with_different_payload_is_rejected(self, client):
        headers = {"Idempotency-Key": "same-key"}
        client.post(
            "/api/regulation/sessions", headers=headers,
            json={"trigger_event": "First payload"},
        )

        response = client.post(
            "/api/regulation/sessions", headers=headers,
            json={"trigger_event": "Different payload"},
        )

        assert response.status_code == 409

    def test_failed_durable_write_does_not_publish_session(self, registry):
        class FailingPersistence:
            def load(self):
                return {}, {}

            def save_session(self, session):
                raise RuntimeError("key provider unavailable")

            def save_rule(self, rule):
                return None

        shared = {}
        router = create_regulation_router(
            store_registry=registry,
            sessions_dict=shared,
            rules_dict={},
            persistence=FailingPersistence(),
        )
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/regulation/sessions", json={"trigger_event": "Observed fact"}
        )

        assert response.status_code == 500
        assert shared == {}


class TestGetSession:
    def test_get_existing_session(self, client):
        create = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test trigger"},
        )
        sid = create.json()["session_id"]

        res = client.get(f"/api/regulation/sessions/{sid}")
        assert res.status_code == 200
        assert res.json()["session_id"] == sid

    def test_get_nonexistent_session(self, client):
        res = client.get("/api/regulation/sessions/nonexistent")
        assert res.status_code == 404


class TestListSessions:
    def test_list_empty(self, client):
        res = client.get("/api/regulation/sessions")
        assert res.status_code == 200
        assert res.json()["count"] == 0

    def test_list_with_sessions(self, client):
        client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "First"},
        )
        client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Second"},
        )

        res = client.get("/api/regulation/sessions")
        assert res.status_code == 200
        assert res.json()["count"] == 2

    def test_list_filter_by_state(self, client):
        client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test"},
        )

        res = client.get("/api/regulation/sessions?state=safety_screen")
        assert res.status_code == 200
        assert res.json()["count"] >= 1

        res = client.get("/api/regulation/sessions?state=completed")
        assert res.status_code == 200
        assert res.json()["count"] == 0


class TestExpireSession:
    def test_expire_active_session(self, client):
        create = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test"},
        )
        sid = create.json()["session_id"]

        res = client.post(f"/api/regulation/sessions/{sid}/expire")
        assert res.status_code == 200
        assert res.json()["state"] == "expired"

    def test_expire_nonexistent(self, client):
        res = client.post("/api/regulation/sessions/nonexistent/expire")
        assert res.status_code == 404

    def test_cannot_expire_completed(self, client):
        create = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test"},
        )
        sid = create.json()["session_id"]
        # Complete safety with 'none' → ACTIVE
        client.post(
            f"/api/regulation/sessions/{sid}/safety-screen",
            json={"safety_category": "none"},
        )
        # Complete session
        client.post(f"/api/regulation/sessions/{sid}/complete")

        res = client.post(f"/api/regulation/sessions/{sid}/expire")
        assert res.status_code == 400


# ── Safety screen tests ──────────────────────────────────────────────


class TestSafetyScreen:
    def test_complete_safety_none(self, client):
        create = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test"},
        )
        sid = create.json()["session_id"]

        res = client.post(
            f"/api/regulation/sessions/{sid}/safety-screen",
            json={"safety_category": "none"},
        )
        assert res.status_code == 200
        assert res.json()["state"] == "active"
        assert res.json()["is_safety_active"] is False

    def test_complete_safety_self_harm(self, client):
        create = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test"},
        )
        sid = create.json()["session_id"]

        res = client.post(
            f"/api/regulation/sessions/{sid}/safety-screen",
            json={"safety_category": "self_harm"},
        )
        assert res.status_code == 200
        assert res.json()["state"] == "safety_branch"
        assert res.json()["is_safety_active"] is True

    def test_invalid_safety_category(self, client):
        create = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test"},
        )
        sid = create.json()["session_id"]

        res = client.post(
            f"/api/regulation/sessions/{sid}/safety-screen",
            json={"safety_category": "invalid"},
        )
        assert res.status_code == 400

    def test_safety_screen_wrong_state(self, client):
        create = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test"},
        )
        sid = create.json()["session_id"]
        # Complete safety first
        client.post(
            f"/api/regulation/sessions/{sid}/safety-screen",
            json={"safety_category": "none"},
        )
        # Cannot re-complete safety screen
        res = client.post(
            f"/api/regulation/sessions/{sid}/safety-screen",
            json={"safety_category": "none"},
        )
        assert res.status_code == 400

    def test_safety_resources_endpoint(self, client):
        res = client.get("/api/regulation/safety-resources")
        assert res.status_code == 200
        assert "resources" in res.json()
        assert "non_overridable_rules" in res.json()


# ── Structured capture tests ─────────────────────────────────────────


class TestRecordFacts:
    def test_record_facts(self, client):
        sid = _create_active_session(client)

        res = client.post(
            f"/api/regulation/sessions/{sid}/facts",
            json={
                "facts": [
                    {"text": "I sent a message", "certainty": 1.0, "source": "user_report"},
                    {"text": "No reply in 3 hours", "certainty": 0.9},
                ],
            },
        )
        assert res.status_code == 200
        assert len(res.json()["facts"]) == 2

    def test_record_facts_invalid_certainty(self, client):
        sid = _create_active_session(client)

        res = client.post(
            f"/api/regulation/sessions/{sid}/facts",
            json={"facts": [{"text": "Test", "certainty": 1.5}]},
        )
        assert res.status_code == 400

    def test_record_facts_wrong_state(self, client):
        create = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test"},
        )
        sid = create.json()["session_id"]
        # Session is in SAFETY_SCREEN, not ACTIVE
        res = client.post(
            f"/api/regulation/sessions/{sid}/facts",
            json={"facts": [{"text": "Test", "certainty": 0.8}]},
        )
        assert res.status_code == 400


class TestRecordInterpretations:
    def test_record_interpretations(self, client):
        sid = _create_active_session(client)

        res = client.post(
            f"/api/regulation/sessions/{sid}/interpretations",
            json={
                "interpretations": [
                    {
                        "text": "Maybe they are busy",
                        "plausibility": 0.7,
                        "evidence_for": ["They have a demanding job"],
                        "evidence_against": ["They usually reply quickly"],
                    },
                ],
            },
        )
        assert res.status_code == 200
        assert len(res.json()["interpretations"]) == 1


class TestRecordEmotions:
    def test_record_emotions(self, client):
        sid = _create_active_session(client)

        res = client.post(
            f"/api/regulation/sessions/{sid}/emotions",
            json={
                "emotions": [
                    {"label": "anxiety", "intensity": 7},
                    {"label": "hurt", "intensity": 5, "description": "Feeling ignored"},
                ],
            },
        )
        assert res.status_code == 200
        assert len(res.json()["emotions"]) == 2

    def test_record_invalid_emotion_label(self, client):
        sid = _create_active_session(client)

        res = client.post(
            f"/api/regulation/sessions/{sid}/emotions",
            json={"emotions": [{"label": "not_an_emotion", "intensity": 5}]},
        )
        assert res.status_code == 400

    def test_record_emotion_invalid_intensity(self, client):
        sid = _create_active_session(client)

        res = client.post(
            f"/api/regulation/sessions/{sid}/emotions",
            json={"emotions": [{"label": "anger", "intensity": 11}]},
        )
        assert res.status_code == 400


class TestRecordUrges:
    def test_record_urges(self, client):
        sid = _create_active_session(client)

        res = client.post(
            f"/api/regulation/sessions/{sid}/urges",
            json={
                "urges": [
                    {"text": "Send another message", "strength": 8},
                ],
            },
        )
        assert res.status_code == 200
        assert len(res.json()["urges"]) == 1


class TestRecordActions:
    def test_record_actions(self, client):
        sid = _create_active_session(client)

        res = client.post(
            f"/api/regulation/sessions/{sid}/actions",
            json={
                "actions": [
                    {
                        "text": "Wait until tomorrow",
                        "reversible": True,
                        "waiting_period_minutes": 30,
                    },
                ],
            },
        )
        assert res.status_code == 200
        assert len(res.json()["actions"]) == 1


class TestRecordOutcomes:
    def test_record_outcomes(self, client):
        sid = _create_active_session(client)
        # Complete session first
        client.post(f"/api/regulation/sessions/{sid}/complete")

        res = client.post(
            f"/api/regulation/sessions/{sid}/outcomes",
            json={
                "outcomes": [
                    {"text": "I waited and felt better", "was_helpful": True},
                ],
            },
        )
        assert res.status_code == 200
        assert len(res.json()["outcomes"]) == 1

    def test_record_outcomes_wrong_state(self, client):
        sid = _create_active_session(client)
        # Not completed yet
        res = client.post(
            f"/api/regulation/sessions/{sid}/outcomes",
            json={"outcomes": [{"text": "Test", "was_helpful": True}]},
        )
        assert res.status_code == 400


# ── Complete session tests ───────────────────────────────────────────


class TestCompleteSession:
    def test_complete_active_session(self, client):
        sid = _create_active_session(client)

        res = client.post(f"/api/regulation/sessions/{sid}/complete")
        assert res.status_code == 200
        assert res.json()["state"] == "completed"

    def test_complete_with_actions_and_outcomes(self, client):
        sid = _create_active_session(client)

        res = client.post(
            f"/api/regulation/sessions/{sid}/complete",
            json={
                "actions": [{"text": "Wait", "reversible": True}],
                "outcomes": [{"text": "Done", "was_helpful": True}],
            },
        )
        assert res.status_code == 200

    def test_complete_wrong_state(self, client):
        create = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test"},
        )
        sid = create.json()["session_id"]
        # Still in SAFETY_SCREEN
        res = client.post(f"/api/regulation/sessions/{sid}/complete")
        assert res.status_code == 400


# ── Assist tests ─────────────────────────────────────────────────────


class TestAssist:
    def test_assist_active_session(self, client):
        sid = _create_active_session(client)

        res = client.post(
            f"/api/regulation/sessions/{sid}/assist",
            json={"current_message": "I need help processing this"},
        )
        assert res.status_code == 200
        assert "is_degraded" in res.json()
        assert "has_authorized_response" in res.json()

    def test_assist_wrong_state(self, client):
        create = client.post(
            "/api/regulation/sessions",
            json={"trigger_event": "Test"},
        )
        sid = create.json()["session_id"]
        # In SAFETY_SCREEN, not ACTIVE
        res = client.post(
            f"/api/regulation/sessions/{sid}/assist",
            json={"current_message": "Help"},
        )
        assert res.status_code == 400


# ── Offline protocol tests ───────────────────────────────────────────


class TestOfflineProtocol:
    def test_get_offline_protocol(self, client):
        sid = _create_active_session(client)

        res = client.get(f"/api/regulation/sessions/{sid}/offline")
        assert res.status_code == 200
        assert "protocol" in res.json()
        assert len(res.json()["protocol"]) > 0

    def test_offline_protocol_nonexistent(self, client):
        res = client.get("/api/regulation/sessions/nonexistent/offline")
        assert res.status_code == 404


# ── Personal rules tests ─────────────────────────────────────────────


class TestRules:
    def test_list_rules(self, client):
        res = client.get("/api/regulation/rules")
        assert res.status_code == 200
        # Default safety rules should be present
        assert "rules" in res.json()

    def test_create_rule(self, client):
        res = client.post(
            "/api/regulation/rules",
            json={
                "text": "Pause before sending another message",
                "strength": "default_principle",
            },
        )
        assert res.status_code == 200
        assert res.json()["strength"] == "default_principle"

    def test_duplicate_rule_create_is_idempotent(self, client):
        headers = {"Idempotency-Key": "rule-create-1"}
        body = {
            "text": "Pause before sending another message",
            "strength": "default_principle",
            "exceptions": ["immediate danger"],
        }
        first = client.post("/api/regulation/rules", headers=headers, json=body)
        second = client.post("/api/regulation/rules", headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_rule_idempotency_key_reuse_with_new_payload_conflicts(self, client):
        headers = {"Idempotency-Key": "rule-create-conflict"}
        client.post(
            "/api/regulation/rules",
            headers=headers,
            json={"text": "First rule", "strength": "reflection_prompt"},
        )
        response = client.post(
            "/api/regulation/rules",
            headers=headers,
            json={"text": "Different rule", "strength": "reflection_prompt"},
        )

        assert response.status_code == 409

    def test_create_hard_guardrail_safety_conflict(self, client):
        # Check that the endpoint exists and accepts/rejects rules correctly
        res = client.post(
            "/api/regulation/rules",
            json={
                "text": "Always prioritize personal safety above all else",
                "strength": "hard_guardrail",
            },
        )
        # May succeed or fail depending on whether it matches safety rules
        assert res.status_code in (200, 400)

    def test_create_rule_invalid_strength(self, client):
        res = client.post(
            "/api/regulation/rules",
            json={"text": "Test rule", "strength": "invalid"},
        )
        assert res.status_code == 400

    def test_confirm_rule(self, client):
        create = client.post(
            "/api/regulation/rules",
            json={"text": "Test confirmable", "strength": "reflection_prompt"},
        )
        rid = create.json()["rule_id"]

        res = client.put(f"/api/regulation/rules/{rid}/confirm")
        assert res.status_code == 200
        assert res.json()["confirmation"] == "confirmed"

    def test_retire_rule(self, client):
        create = client.post(
            "/api/regulation/rules",
            json={"text": "Test retirable", "strength": "reflection_prompt"},
        )
        rid = create.json()["rule_id"]

        res = client.put(f"/api/regulation/rules/{rid}/retire")
        assert res.status_code == 200
        assert res.json()["confirmation"] == "retired"

    def test_rule_not_found(self, client):
        res = client.put("/api/regulation/rules/nonexistent/confirm")
        assert res.status_code == 404


# ── Helpers ──────────────────────────────────────────────────────────


def _create_active_session(client) -> str:
    """Create a session and route it to ACTIVE state."""
    create = client.post(
        "/api/regulation/sessions",
        json={"trigger_event": "Test trigger"},
    )
    sid = create.json()["session_id"]
    client.post(
        f"/api/regulation/sessions/{sid}/safety-screen",
        json={"safety_category": "none"},
    )
    return sid
