"""Restart and confidentiality tests for durable Regulation state."""

from __future__ import annotations

from pathlib import Path

from agent_runtime.emotional_regulation import (
    ConfirmationState,
    PersonalRegulationRule,
    RuleStrength,
    begin_safety_screen,
    start_trigger_check_in,
)
from agent_runtime.encryption import KeyManager
from agent_runtime.regulation_persistence import EncryptedRegulationPersistence
from agent_runtime.stores import RegulationStore


def _persistence(tmp_path: Path, monkeypatch) -> tuple[EncryptedRegulationPersistence, Path]:
    event_path = tmp_path / "regulation" / "events.jsonl"
    store = RegulationStore()
    store.set_path(event_path)
    monkeypatch.setenv("REGULATION_KEY", "ab" * 32)
    monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
    monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)
    keys = KeyManager()
    keys.initialize()
    return EncryptedRegulationPersistence(store, keys, owner_id="owner"), event_path


def test_session_survives_restart_without_plaintext(tmp_path: Path, monkeypatch) -> None:
    persistence, event_path = _persistence(tmp_path, monkeypatch)
    session = begin_safety_screen(
        start_trigger_check_in("owner", "A sensitive trigger happened")
    )

    persistence.save_session(session)

    raw = event_path.read_text()
    assert "A sensitive trigger happened" not in raw

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


def test_latest_snapshot_and_tombstone_win(tmp_path: Path, monkeypatch) -> None:
    persistence, _ = _persistence(tmp_path, monkeypatch)
    session = begin_safety_screen(start_trigger_check_in("owner", "trigger"))
    persistence.save_session(session)
    persistence.delete_session(session.session_id)

    sessions, _ = persistence.load()
    assert sessions == {}


def test_rule_survives_restart(tmp_path: Path, monkeypatch) -> None:
    persistence, event_path = _persistence(tmp_path, monkeypatch)
    rule = PersonalRegulationRule(
        rule_id="rule-1",
        text="Pause before sending another message",
        strength=RuleStrength.DEFAULT_PRINCIPLE,
        confirmation=ConfirmationState.CONFIRMED,
    )

    persistence.save_rule(rule)

    assert rule.text not in event_path.read_text()
    _, rules = persistence.load()
    assert rules[rule.rule_id] == rule
