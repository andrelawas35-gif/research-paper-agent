"""Tests for F2: Store boundaries."""

from __future__ import annotations

import tempfile
import sqlite3
from pathlib import Path

import pytest


# Override the conftest autouse fixture — store tests are self-contained.
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    """No-op: store tests do not need file-system isolation."""
    pass


from agent_runtime.event_envelope import (
    Domain,
    EventEnvelope,
    EventStore,
    Sensitivity,
)
from agent_runtime.stores import (
    GeneralPKMStore,
    OperationalStore,
    RegulationStore,
    RetrievalGuard,
    StoreBoundaryError,
    StoreRegistry,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_envelope(domain: Domain, event_type: str = "test_event", **overrides: object) -> EventEnvelope:
    kwargs: dict[str, object] = dict(
        owner_id="test-owner",
        domain=domain,
        event_type=event_type,
        schema_version=1,
        sensitivity=Sensitivity.CONFIDENTIAL,
        provenance={"source": "test"},
        payload={"key": "value"},
    )
    kwargs.update(overrides)
    return EventEnvelope.create(**kwargs)  # type: ignore[arg-type]


def _temp_store(cls: type) -> object:
    """Create a store pointed at a temp file."""
    store = cls()
    tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)  # noqa: SIM115
    store.set_path(Path(tmp.name))
    return store


# ── OperationalStore ─────────────────────────────────────────────────


class TestOperationalStore:
    def test_accepts_operational_events(self) -> None:
        store = _temp_store(OperationalStore)
        env = _make_envelope(Domain.OPERATIONAL)
        store.append(env)
        assert len(store.replay()) == 1

    def test_rejects_regulation_events(self) -> None:
        store = _temp_store(OperationalStore)
        env = _make_envelope(Domain.REGULATION, sensitivity=Sensitivity.RESTRICTED)
        with pytest.raises(StoreBoundaryError, match="Cannot append regulation"):
            store.append(env)

    def test_rejects_general_pkm_events(self) -> None:
        store = _temp_store(OperationalStore)
        env = _make_envelope(Domain.GENERAL_PKM)
        with pytest.raises(StoreBoundaryError, match="Cannot append general_pkm"):
            store.append(env)

    def test_event_ids(self) -> None:
        store = _temp_store(OperationalStore)
        env = _make_envelope(Domain.OPERATIONAL, event_id="00000000-0000-0000-0000-000000000001")
        store.append(env)
        assert store.event_ids() == {"00000000-0000-0000-0000-000000000001"}


# ── GeneralPKMStore ──────────────────────────────────────────────────


class TestGeneralPKMStore:
    def test_accepts_general_pkm_events(self) -> None:
        store = _temp_store(GeneralPKMStore)
        env = _make_envelope(Domain.GENERAL_PKM)
        store.append(env)
        assert len(store.replay()) == 1

    def test_rejects_regulation_events(self) -> None:
        store = _temp_store(GeneralPKMStore)
        env = _make_envelope(Domain.REGULATION, sensitivity=Sensitivity.RESTRICTED)
        with pytest.raises(StoreBoundaryError, match="Regulation events cannot enter"):
            store.append(env)

    def test_rejects_operational_events(self) -> None:
        store = _temp_store(GeneralPKMStore)
        env = _make_envelope(Domain.OPERATIONAL)
        with pytest.raises(StoreBoundaryError, match="Cannot append operational"):
            store.append(env)


# ── RegulationStore ──────────────────────────────────────────────────


class TestRegulationStore:
    def test_uses_sqlite_wal_and_replays_after_restart(self, tmp_path: Path) -> None:
        database_path = tmp_path / "regulation.db"
        first = RegulationStore()
        first.set_path(database_path)
        event = _make_envelope(
            Domain.REGULATION,
            sensitivity=Sensitivity.RESTRICTED,
        )

        first.append(event)

        reopened = RegulationStore()
        reopened.set_path(database_path)
        assert reopened.replay() == [event]
        assert database_path.read_bytes().startswith(b"SQLite format 3\x00")
        with sqlite3.connect(database_path) as connection:
            assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"

    def test_imports_legacy_jsonl_once_without_losing_events(
        self, tmp_path: Path
    ) -> None:
        database_path = tmp_path / "events.db"
        legacy_path = tmp_path / "events.jsonl"
        event = _make_envelope(
            Domain.REGULATION,
            sensitivity=Sensitivity.RESTRICTED,
        )
        EventStore(legacy_path).append(event)

        migrated = RegulationStore()
        migrated.set_path(database_path)

        assert migrated.replay() == [event]
        assert database_path.exists()
        assert not legacy_path.exists()
        assert (tmp_path / "events.jsonl.migrated").exists()

    def test_uncommitted_interrupted_write_is_not_replayed(self, tmp_path: Path) -> None:
        database_path = tmp_path / "events.db"
        store = RegulationStore()
        store.set_path(database_path)
        durable = _make_envelope(
            Domain.REGULATION, sensitivity=Sensitivity.RESTRICTED
        )
        interrupted = _make_envelope(
            Domain.REGULATION, sensitivity=Sensitivity.RESTRICTED
        )
        store.append(durable)

        connection = sqlite3.connect(database_path)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO events (event_id, domain, timestamp, envelope_json) VALUES (?, ?, ?, ?)",
            (
                interrupted.event_id,
                interrupted.domain.value,
                interrupted.timestamp,
                __import__("json").dumps(interrupted.to_dict()),
            ),
        )
        connection.close()  # process interruption before COMMIT

        restarted = RegulationStore()
        restarted.set_path(database_path)
        assert restarted.replay() == [durable]

    def test_duplicate_event_write_fails_without_corrupting_original(
        self, tmp_path: Path
    ) -> None:
        database_path = tmp_path / "events.db"
        store = RegulationStore()
        store.set_path(database_path)
        event = _make_envelope(
            Domain.REGULATION, sensitivity=Sensitivity.RESTRICTED
        )
        store.append(event)

        with pytest.raises(sqlite3.IntegrityError):
            store.append(event)

        assert store.replay() == [event]

    def test_accepts_regulation_events(self) -> None:
        store = _temp_store(RegulationStore)
        env = _make_envelope(Domain.REGULATION, sensitivity=Sensitivity.RESTRICTED)
        store.append(env)
        assert len(store.replay()) == 1

    def test_rejects_general_pkm_events(self) -> None:
        store = _temp_store(RegulationStore)
        env = _make_envelope(Domain.GENERAL_PKM)
        with pytest.raises(StoreBoundaryError, match="Cannot append general_pkm"):
            store.append(env)

    def test_rejects_operational_events(self) -> None:
        store = _temp_store(RegulationStore)
        env = _make_envelope(Domain.OPERATIONAL)
        with pytest.raises(StoreBoundaryError, match="Cannot append operational"):
            store.append(env)


# ── StoreRegistry ────────────────────────────────────────────────────


class TestStoreRegistry:
    def test_routes_events_to_correct_store(self) -> None:
        reg = StoreRegistry()
        reg.operational.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
        reg.general_pkm.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
        reg.regulation.set_path(Path(tempfile.mktemp(suffix=".jsonl")))

        reg.append(_make_envelope(Domain.OPERATIONAL))
        reg.append(_make_envelope(Domain.GENERAL_PKM))
        reg.append(_make_envelope(Domain.REGULATION, sensitivity=Sensitivity.RESTRICTED))

        assert len(reg.operational.replay()) == 1
        assert len(reg.general_pkm.replay()) == 1
        assert len(reg.regulation.replay()) == 1

    def test_read_general_for_regulation_context(self) -> None:
        reg = StoreRegistry()
        reg.general_pkm.set_path(Path(tempfile.mktemp(suffix=".jsonl")))

        # Add a confirmed rule
        rule_env = _make_envelope(
            Domain.GENERAL_PKM,
            event_type="personal_rule_confirmed",
            payload={"rule_id": "r1", "label": "pause-before-send", "strength": "hard", "text": "Pause 5 min before sending"},
        )
        reg.general_pkm.append(rule_env)

        # Read only confirmed rules
        results = reg.read_general_for_regulation_context(["r1"])
        assert len(results) == 1
        assert results[0]["rule_id"] == "r1"
        assert results[0]["label"] == "pause-before-send"
        # Stripped fields
        assert "provenance" not in results[0]

    def test_read_general_for_regulation_context_filters_by_ids(self) -> None:
        reg = StoreRegistry()
        reg.general_pkm.set_path(Path(tempfile.mktemp(suffix=".jsonl")))

        reg.general_pkm.append(_make_envelope(
            Domain.GENERAL_PKM,
            event_type="personal_rule_confirmed",
            payload={"rule_id": "r1", "label": "rule-1", "strength": "hard", "text": "Rule 1"},
        ))
        reg.general_pkm.append(_make_envelope(
            Domain.GENERAL_PKM,
            event_type="personal_rule_confirmed",
            payload={"rule_id": "r2", "label": "rule-2", "strength": "default", "text": "Rule 2"},
        ))

        results = reg.read_general_for_regulation_context(["r1"])
        assert len(results) == 1
        assert results[0]["rule_id"] == "r1"

    def test_regulation_store_is_empty(self) -> None:
        reg = StoreRegistry()
        reg.regulation.set_path(Path(tempfile.mktemp(suffix=".jsonl")))
        assert reg.regulation_store_is_empty()
        reg.append(_make_envelope(Domain.REGULATION, sensitivity=Sensitivity.RESTRICTED))
        assert not reg.regulation_store_is_empty()


# ── RetrievalGuard ───────────────────────────────────────────────────


class TestRetrievalGuard:
    def test_filter_regulation_removes_regulation_candidates(self) -> None:
        candidates = [
            {"id": "1", "domain": "general_pkm", "text": "ok"},
            {"id": "2", "domain": "regulation", "text": "secret"},
            {"id": "3", "domain": "general_pkm", "sensitivity": "restricted", "text": "sensitive"},
        ]
        filtered = RetrievalGuard.filter_regulation(candidates)
        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"

    def test_assert_no_regulation_raises(self) -> None:
        candidates = [
            {"id": "1", "domain": "general_pkm"},
            {"id": "2", "domain": "regulation"},
        ]
        with pytest.raises(StoreBoundaryError, match="Regulation record attempted"):
            RetrievalGuard.assert_no_regulation(candidates)

    def test_assert_no_regulation_passes_on_clean_data(self) -> None:
        candidates = [{"id": "1", "domain": "general_pkm"}]
        # Should not raise
        RetrievalGuard.assert_no_regulation(candidates)


# ── StoreBoundaryError ───────────────────────────────────────────────


class TestStoreBoundaryError:
    def test_is_value_error(self) -> None:
        err = StoreBoundaryError("test")
        assert isinstance(err, ValueError)
