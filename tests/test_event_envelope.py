"""Tests for F1: Shared event envelope."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# Override the conftest autouse fixture — event_envelope tests are
# self-contained and do not require the full agent bootstrap.
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    """No-op: event envelope tests do not need file-system isolation."""
    pass


from agent_runtime.event_envelope import (
    Domain,
    EventEnvelope,
    EventStore,
    MalformedEnvelopeError,
    Sensitivity,
    _canonical_json,
    _sha256_hex,
    _uuid7,
    _validate_envelope_shape,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_envelope(**overrides: object) -> EventEnvelope:
    kwargs: dict[str, object] = dict(
        owner_id="test-owner",
        domain=Domain.REGULATION,
        event_type="trigger_session_started",
        schema_version=1,
        sensitivity=Sensitivity.RESTRICTED,
        provenance={"source": "test"},
        payload={"session_id": "abc"},
    )
    kwargs.update(overrides)
    return EventEnvelope.create(**kwargs)  # type: ignore[arg-type]


# ── Envelope creation ────────────────────────────────────────────────


class TestEventEnvelopeCreate:
    def test_creates_with_all_fields(self) -> None:
        env = _make_envelope()
        assert env.owner_id == "test-owner"
        assert env.domain == Domain.REGULATION
        assert env.schema_version == 1
        assert env.event_type == "trigger_session_started"
        assert env.sensitivity == Sensitivity.RESTRICTED
        assert isinstance(env.event_id, str)
        assert len(env.event_id) == 36  # UUID string length
        assert env.correlation_id is None

    def test_event_id_is_unique(self) -> None:
        ids = {_make_envelope().event_id for _ in range(100)}
        assert len(ids) == 100

    def test_timestamp_is_iso8601_utc(self) -> None:
        env = _make_envelope()
        assert env.timestamp.endswith("+00:00") or env.timestamp.endswith("Z")
        from datetime import datetime
        parsed = datetime.fromisoformat(env.timestamp)
        assert parsed.tzinfo is not None

    def test_injectable_event_id_and_timestamp(self) -> None:
        env = _make_envelope(
            event_id="00000000-0000-0000-0000-000000000001",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        assert env.event_id == "00000000-0000-0000-0000-000000000001"
        assert env.timestamp == "2026-01-01T00:00:00+00:00"

    def test_payload_checksum_is_deterministic(self) -> None:
        payload = {"a": 1, "b": [2, 3]}
        env1 = _make_envelope(payload=payload)
        env2 = _make_envelope(payload=payload)
        assert env1.payload_checksum == env2.payload_checksum

    def test_correlation_id_preserved(self) -> None:
        env = _make_envelope(correlation_id="corr-123")
        assert env.correlation_id == "corr-123"


# ── Serialization round-trip ─────────────────────────────────────────


class TestEventEnvelopeRoundTrip:
    def test_to_dict_and_from_dict(self) -> None:
        env = _make_envelope()
        d = env.to_dict()
        env2 = EventEnvelope.from_dict(d)
        assert env2 == env

    def test_from_dict_detects_checksum_mismatch(self) -> None:
        env = _make_envelope()
        d = env.to_dict()
        d["payload"]["tampered"] = True
        with pytest.raises(MalformedEnvelopeError, match="payload_checksum mismatch"):
            EventEnvelope.from_dict(d)


# ── Validation ───────────────────────────────────────────────────────


class TestValidateEnvelopeShape:
    def test_valid_envelope_passes(self) -> None:
        env = _make_envelope()
        errors = _validate_envelope_shape(env.to_dict())
        assert errors == []

    def test_missing_required_field_fails(self) -> None:
        d = _make_envelope().to_dict()
        del d["event_id"]
        errors = _validate_envelope_shape(d)
        assert any("event_id" in e for e in errors)

    def test_invalid_domain_fails(self) -> None:
        d = _make_envelope().to_dict()
        d["domain"] = "invalid_domain"
        errors = _validate_envelope_shape(d)
        assert any("domain" in e for e in errors)

    def test_invalid_sensitivity_fails(self) -> None:
        d = _make_envelope().to_dict()
        d["sensitivity"] = "top_secret"
        errors = _validate_envelope_shape(d)
        assert any("sensitivity" in e for e in errors)

    def test_invalid_schema_version_fails(self) -> None:
        d = _make_envelope().to_dict()
        d["schema_version"] = 0
        errors = _validate_envelope_shape(d)
        assert any("schema_version" in e for e in errors)

    def test_timestamp_without_timezone_fails(self) -> None:
        d = _make_envelope().to_dict()
        d["timestamp"] = "2026-01-01T00:00:00"
        errors = _validate_envelope_shape(d)
        assert any("timezone" in e for e in errors)

    def test_correlation_id_null_passes(self) -> None:
        d = _make_envelope().to_dict()
        d["correlation_id"] = None
        errors = _validate_envelope_shape(d)
        assert errors == []

    def test_correlation_id_empty_string_fails(self) -> None:
        d = _make_envelope().to_dict()
        d["correlation_id"] = ""
        errors = _validate_envelope_shape(d)
        assert any("correlation_id" in e for e in errors)


# ── EventStore append & replay ───────────────────────────────────────


class TestEventStore:
    def test_append_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            store = EventStore(path)
            env1 = _make_envelope(event_id="00000000-0000-0000-0000-000000000001")
            env2 = _make_envelope(event_id="00000000-0000-0000-0000-000000000002")

            store.append(env1)
            store.append(env2)

            replayed = store.replay()
            assert len(replayed) == 2
            assert replayed[0].event_id == env1.event_id
            assert replayed[1].event_id == env2.event_id

    def test_replay_empty_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(Path(tmp) / "nonexistent.jsonl")
            assert store.replay() == []

    def test_replay_by_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(Path(tmp) / "events.jsonl")
            store.append(_make_envelope(
                event_id="00000000-0000-0000-0000-000000000001",
                domain=Domain.REGULATION,
            ))
            store.append(_make_envelope(
                event_id="00000000-0000-0000-0000-000000000002",
                domain=Domain.GENERAL_PKM,
            ))

            reg = store.replay_by_domain(Domain.REGULATION)
            assert len(reg) == 1
            assert reg[0].domain == Domain.REGULATION

    def test_replay_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(Path(tmp) / "events.jsonl")
            store.append(_make_envelope(event_id="00000000-0000-0000-0000-000000000001"))
            store.append(_make_envelope(event_id="00000000-0000-0000-0000-000000000002"))
            r1 = store.replay()
            r2 = store.replay()
            assert [e.event_id for e in r1] == [e.event_id for e in r2]

    def test_duplicate_ids_not_rejected_at_envelope_level(self) -> None:
        """Duplicate detection belongs to domain stores, not the raw EventStore."""
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(Path(tmp) / "events.jsonl")
            env = _make_envelope(event_id="00000000-0000-0000-0000-000000000001")
            store.append(env)
            store.append(env)  # same ID — raw store does not reject
            assert len(store.replay()) == 2

    def test_event_ids_collection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(Path(tmp) / "events.jsonl")
            store.append(_make_envelope(event_id="00000000-0000-0000-0000-000000000001"))
            assert store.event_ids() == {"00000000-0000-0000-0000-000000000001"}


# ── Domain and Sensitivity enums ─────────────────────────────────────


class TestDomainEnum:
    def test_all_expected_domains(self) -> None:
        values = {d.value for d in Domain}
        assert values >= {"operational", "general_pkm", "regulation", "values"}


class TestSensitivityEnum:
    def test_all_expected_levels(self) -> None:
        values = {s.value for s in Sensitivity}
        assert values >= {"public", "internal", "confidential", "restricted"}


# ── UUID7 ────────────────────────────────────────────────────────────


class TestUUID7:
    def test_generates_valid_uuid(self) -> None:
        import uuid as _uuid
        val = _uuid7()
        parsed = _uuid.UUID(val)
        assert parsed.version == 7

    def test_uniqueness(self) -> None:
        ids = {_uuid7() for _ in range(100)}
        assert len(ids) == 100


# ── MalformedEnvelopeError ───────────────────────────────────────────


class TestMalformedEnvelopeError:
    def test_carries_errors_list(self) -> None:
        err = MalformedEnvelopeError(["field missing", "bad type"])
        assert len(err.errors) == 2
        assert "field missing" in str(err)
