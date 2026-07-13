"""Restart and confidentiality tests for durable Regulation state."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from agent_runtime.emotional_regulation import (
    Action,
    ConfirmationState,
    Emotion,
    EmotionLabel,
    Fact,
    Interpretation,
    Outcome,
    PersonalRegulationRule,
    RuleStrength,
    SafetyCategory,
    Urge,
    begin_safety_screen,
    complete_safety_screen,
    complete_trigger_check_in,
    record_trigger_response,
    start_trigger_check_in,
)
from agent_runtime.encryption import KeyManager
from agent_runtime.regulation_persistence import EncryptedRegulationPersistence
from agent_runtime.record_keys import FileRecordKeyProvider
from agent_runtime.stores import RegulationStore


def _persistence(tmp_path: Path, monkeypatch) -> tuple[EncryptedRegulationPersistence, Path]:
    event_path = tmp_path / "regulation" / "events.db"
    store = RegulationStore()
    store.set_path(event_path)
    monkeypatch.setenv("REGULATION_KEY", "ab" * 32)
    monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
    monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)
    keys = KeyManager()
    keys.initialize()
    record_keys = FileRecordKeyProvider(tmp_path / "record-keys")
    return EncryptedRegulationPersistence(
        store,
        keys,
        owner_id="owner",
        record_keys=record_keys,
    ), event_path


def test_session_survives_restart_without_plaintext(tmp_path: Path, monkeypatch) -> None:
    persistence, event_path = _persistence(tmp_path, monkeypatch)
    session = begin_safety_screen(
        start_trigger_check_in("owner", "A sensitive trigger happened")
    )

    persistence.save_session(session)

    raw = event_path.read_bytes()
    assert b"A sensitive trigger happened" not in raw

    sessions, rules = persistence.load()
    assert rules == {}
    assert sessions[session.session_id] == session


def test_private_session_is_never_written(tmp_path: Path, monkeypatch) -> None:
    persistence, event_path = _persistence(tmp_path, monkeypatch)
    session = begin_safety_screen(
        start_trigger_check_in("owner", "private", is_private=True)
    )

    persistence.save_session(session)

    assert not event_path.exists()


def test_completed_session_restarts_without_raw_narrative(
    tmp_path: Path, monkeypatch
) -> None:
    persistence, _ = _persistence(tmp_path, monkeypatch)
    session = begin_safety_screen(
        start_trigger_check_in("owner", "A private accusation")
    )
    session = complete_safety_screen(session, SafetyCategory.NONE)
    session = record_trigger_response(
        session,
        facts=[Fact(text="A message arrived", certainty=1.0, source="user_report")],
        interpretations=[
            Interpretation(text="They intended to embarrass me", plausibility=0.5)
        ],
        emotions=[Emotion(label=EmotionLabel.HURT, intensity=8)],
        urges=[Urge(text="Demand another answer", strength=9)],
    )
    session = complete_trigger_check_in(
        session,
        actions=[Action(text="Wait thirty minutes", waiting_period_minutes=30)],
        outcomes=[Outcome(text="I became calmer", was_helpful=True)],
    )

    persistence.save_session(session)
    sessions, _ = persistence.load()

    restored = sessions[session.session_id]
    assert restored.state == session.state
    assert restored.trigger_event is None
    assert restored.facts == []
    assert restored.interpretations == []
    assert restored.urges == []
    assert restored.actions == []
    assert restored.outcomes == []
    assert restored.emotions[0].label == EmotionLabel.HURT
    assert restored.emotions[0].intensity == 8
    assert restored.compact_record is not None
    assert restored.compact_record.action_count == 1
    assert restored.compact_record.helpful_outcome_count == 1


def test_save_completion_returns_memory_safe_projection(
    tmp_path: Path, monkeypatch
) -> None:
    persistence, _ = _persistence(tmp_path, monkeypatch)
    session = begin_safety_screen(
        start_trigger_check_in("owner", "Narrative only needed while active")
    )
    session = complete_safety_screen(session, SafetyCategory.NONE)
    session = complete_trigger_check_in(
        session,
        actions=[Action(text="Wait before replying")],
    )

    safe = persistence.save_session(session)

    assert safe.trigger_event is None
    assert safe.actions == []
    assert safe.compact_record is not None
    assert safe.compact_record.action_count == 1


def test_safety_branch_destroys_narrative_immediately(
    tmp_path: Path, monkeypatch
) -> None:
    persistence, event_path = _persistence(tmp_path, monkeypatch)
    key_provider = FileRecordKeyProvider(tmp_path / "record-keys")
    session = begin_safety_screen(
        start_trigger_check_in("owner", "Highly sensitive safety narrative")
    )
    persistence.save_session(session)

    safety = complete_safety_screen(session, SafetyCategory.SELF_HARM)
    safe = persistence.save_session(safety)

    assert not key_provider.exists(f"session:{session.session_id}")
    assert key_provider.exists(f"record:{session.session_id}")
    assert safe.trigger_event is None
    assert safe.state.value == "safety_branch"
    assert b"Highly sensitive safety narrative" not in event_path.read_bytes()
    restored, _ = persistence.load()
    assert restored[session.session_id].safety_state.category == SafetyCategory.SELF_HARM


def test_expiry_destroys_active_narrative_key(
    tmp_path: Path, monkeypatch
) -> None:
    from agent_runtime.emotional_regulation import expire_session

    persistence, _ = _persistence(tmp_path, monkeypatch)
    key_provider = FileRecordKeyProvider(tmp_path / "record-keys")
    session = begin_safety_screen(
        start_trigger_check_in("owner", "Narrative abandoned during check-in")
    )
    persistence.save_session(session)

    safe = persistence.save_session(expire_session(session))

    assert not key_provider.exists(f"session:{session.session_id}")
    assert safe.trigger_event is None
    assert safe.state.value == "expired"


def test_completion_destroys_narrative_key_but_keeps_compact_record_key(
    tmp_path: Path, monkeypatch
) -> None:
    persistence, _ = _persistence(tmp_path, monkeypatch)
    record_keys = FileRecordKeyProvider(tmp_path / "record-keys")
    session = begin_safety_screen(
        start_trigger_check_in("owner", "Narrative that must be forgotten")
    )
    session = complete_safety_screen(session, SafetyCategory.NONE)
    persistence.save_session(session)
    assert record_keys.exists(f"session:{session.session_id}")

    session = complete_trigger_check_in(session)
    persistence.save_session(session)

    assert not record_keys.exists(f"session:{session.session_id}")
    assert record_keys.exists(f"record:{session.session_id}")
    sessions, _ = persistence.load()
    assert sessions[session.session_id].trigger_event is None


def test_deletion_makes_retained_database_backup_cryptographically_unreadable(
    tmp_path: Path, monkeypatch
) -> None:
    persistence, event_path = _persistence(tmp_path, monkeypatch)
    session = begin_safety_screen(start_trigger_check_in("owner", "sensitive"))
    session = complete_safety_screen(session, SafetyCategory.NONE)
    session = complete_trigger_check_in(session)
    persistence.save_session(session)

    backup_path = tmp_path / "backup" / "events.db"
    backup_path.parent.mkdir()
    with sqlite3.connect(event_path) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)

    persistence.delete_session(session.session_id)

    backup_store = RegulationStore()
    backup_store.set_path(backup_path)
    assert backup_store.replay()
    master_keys = KeyManager()
    master_keys.initialize()
    restored_backup = EncryptedRegulationPersistence(
        backup_store,
        master_keys,
        owner_id="owner",
        record_keys=FileRecordKeyProvider(tmp_path / "record-keys"),
    )
    sessions, _ = restored_backup.load()
    assert sessions == {}


def test_latest_snapshot_and_tombstone_win(tmp_path: Path, monkeypatch) -> None:
    persistence, _ = _persistence(tmp_path, monkeypatch)
    session = begin_safety_screen(start_trigger_check_in("owner", "trigger"))
    persistence.save_session(session)
    persistence.delete_session(session.session_id)

    sessions, _ = persistence.load()
    assert sessions == {}


def test_unexpected_missing_key_fails_closed(tmp_path: Path, monkeypatch) -> None:
    import pytest
    from agent_runtime.encryption import KeyNotFoundError

    persistence, _ = _persistence(tmp_path, monkeypatch)
    session = begin_safety_screen(start_trigger_check_in("owner", "trigger"))
    persistence.save_session(session)
    next((tmp_path / "record-keys").glob("*.key")).unlink()

    with pytest.raises(KeyNotFoundError):
        persistence.load()


def test_expired_compact_record_is_cryptographically_purged(
    tmp_path: Path, monkeypatch
) -> None:
    from agent_runtime.emotional_regulation import _new_version

    persistence, _ = _persistence(tmp_path, monkeypatch)
    session = begin_safety_screen(start_trigger_check_in("owner", "old trigger"))
    session = complete_safety_screen(session, SafetyCategory.NONE)
    session = _new_version(session, retention_days=0)
    session = complete_trigger_check_in(session)
    safe = persistence.save_session(session)
    sessions = {safe.session_id: safe}

    removed = persistence.purge_expired_sessions(sessions)

    assert removed == 1
    assert sessions == {}
    assert FileRecordKeyProvider(tmp_path / "record-keys").was_destroyed(
        f"record:{session.session_id}"
    )


def test_production_mode_rejects_legacy_master_key_events(
    tmp_path: Path, monkeypatch
) -> None:
    import pytest

    persistence, _ = _persistence(tmp_path, monkeypatch)
    persistence._append("regulation_session_snapshot", {"session": {}})  # noqa: SLF001
    strict = EncryptedRegulationPersistence(
        persistence._store,  # noqa: SLF001
        persistence._keys,  # noqa: SLF001
        owner_id="owner",
        record_keys=FileRecordKeyProvider(tmp_path / "record-keys"),
        allow_legacy=False,
    )

    with pytest.raises(RuntimeError, match="Legacy Regulation event"):
        strict.load()


def test_rule_survives_restart(tmp_path: Path, monkeypatch) -> None:
    persistence, event_path = _persistence(tmp_path, monkeypatch)
    rule = PersonalRegulationRule(
        rule_id="rule-1",
        text="Pause before sending another message",
        strength=RuleStrength.DEFAULT_PRINCIPLE,
        confirmation=ConfirmationState.CONFIRMED,
    )

    persistence.save_rule(rule)

    assert rule.text.encode() not in event_path.read_bytes()
    assert FileRecordKeyProvider(tmp_path / "record-keys").exists(
        f"rule:{rule.rule_id}"
    )
    _, rules = persistence.load()
    assert rules[rule.rule_id] == rule
