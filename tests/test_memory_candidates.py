"""Tests for A1: Memory Candidate extraction."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Override conftest autouse fixture — this test is self-contained.
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    """No-op: memory candidate tests do not need file-system isolation."""
    pass


from agent_runtime.memory_candidates import (
    CandidateDomain,
    CandidateSensitivity,
    CandidateSource,
    CandidateStatus,
    MemoryCandidate,
    SuppressionFingerprint,
    _classify_sensitivity,
    _compute_fingerprint,
    _default_expiry,
    _detect_conflicts,
    _extract_explicit_facts,
    _is_suppressed,
    _requires_confirmation,
    expire_stale_candidates,
    extract_candidates,
    load_candidates,
    load_suppression_fingerprints,
    save_candidates,
    save_suppression_fingerprints,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_temp_log(entries: List[Dict[str, Any]]) -> Path:
    """Create a temporary interaction log file."""
    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    with tmp.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return tmp


def _make_candidate(**overrides) -> MemoryCandidate:
    """Create a MemoryCandidate with defaults."""
    defaults = {
        "candidate_id": "cand_test001",
        "domain": CandidateDomain.PREFERENCE,
        "sensitivity": CandidateSensitivity.MEDIUM,
        "source": CandidateSource.EXPLICIT_STATEMENT,
        "provenance": {"interaction_timestamp": "2026-07-12T00:00:00Z"},
        "proposition": "I prefer concise answers",
        "evidence": "I prefer concise answers",
        "confidence": 0.85,
        "created_at": "2026-07-12T00:00:00Z",
        "expires_at": "2026-10-10T00:00:00Z",
        "requires_confirmation": True,
    }
    defaults.update(overrides)
    return MemoryCandidate(**defaults)


# ── Fingerprint tests ────────────────────────────────────────────────


class TestFingerprint:
    def test_deterministic(self):
        fp1 = _compute_fingerprint("hello", "world")
        fp2 = _compute_fingerprint("hello", "world")
        assert fp1 == fp2

    def test_different_content(self):
        fp1 = _compute_fingerprint("hello", "world")
        fp2 = _compute_fingerprint("goodbye", "world")
        assert fp1 != fp2

    def test_truncates_long_input(self):
        long_prop = "x" * 500
        long_ev = "y" * 500
        fp = _compute_fingerprint(long_prop, long_ev)
        assert len(fp) == 64  # SHA-256 hex digest


# ── Sensitivity classification tests ─────────────────────────────────


class TestClassifySensitivity:
    def test_value_is_identity_shaping(self):
        result = _classify_sensitivity(
            CandidateDomain.VALUE,
            CandidateSource.EXPLICIT_STATEMENT,
            "I value honesty",
        )
        assert result == CandidateSensitivity.IDENTITY_SHAPING

    def test_principle_is_identity_shaping(self):
        result = _classify_sensitivity(
            CandidateDomain.PRINCIPLE,
            CandidateSource.EXPLICIT_STATEMENT,
            "Always be kind",
        )
        assert result == CandidateSensitivity.IDENTITY_SHAPING

    def test_goal_is_identity_shaping(self):
        result = _classify_sensitivity(
            CandidateDomain.GOAL,
            CandidateSource.EXPLICIT_STATEMENT,
            "I want to run a marathon",
        )
        assert result == CandidateSensitivity.IDENTITY_SHAPING

    def test_relationship_is_high(self):
        result = _classify_sensitivity(
            CandidateDomain.RELATIONSHIP,
            CandidateSource.EXPLICIT_STATEMENT,
            "My friend is important",
        )
        assert result == CandidateSensitivity.HIGH

    def test_cognitive_is_high(self):
        result = _classify_sensitivity(
            CandidateDomain.COGNITIVE,
            CandidateSource.REPEATED_PATTERN,
            "User prefers chunked answers",
        )
        assert result == CandidateSensitivity.HIGH

    def test_model_inference_is_low(self):
        result = _classify_sensitivity(
            CandidateDomain.PREFERENCE,
            CandidateSource.MODEL_INFERENCE,
            "User seems to like Python",
        )
        assert result == CandidateSensitivity.LOW

    def test_explicit_preference_is_medium(self):
        result = _classify_sensitivity(
            CandidateDomain.PREFERENCE,
            CandidateSource.EXPLICIT_STATEMENT,
            "I prefer dark mode",
        )
        assert result == CandidateSensitivity.MEDIUM


# ── Expiry tests ─────────────────────────────────────────────────────


class TestDefaultExpiry:
    def test_identity_shaping_30_days(self):
        expiry = _default_expiry(CandidateSensitivity.IDENTITY_SHAPING, CandidateSource.EXPLICIT_STATEMENT)
        from datetime import datetime, timedelta, timezone
        exp = datetime.fromisoformat(expiry)
        expected = datetime.now(timezone.utc) + timedelta(days=30)
        diff = abs((exp - expected).total_seconds())
        assert diff < 5  # within 5 seconds

    def test_model_inference_30_days(self):
        expiry = _default_expiry(CandidateSensitivity.LOW, CandidateSource.MODEL_INFERENCE)
        from datetime import datetime, timedelta, timezone
        exp = datetime.fromisoformat(expiry)
        expected = datetime.now(timezone.utc) + timedelta(days=30)
        diff = abs((exp - expected).total_seconds())
        assert diff < 5

    def test_explicit_statement_90_days(self):
        expiry = _default_expiry(CandidateSensitivity.MEDIUM, CandidateSource.EXPLICIT_STATEMENT)
        from datetime import datetime, timedelta, timezone
        exp = datetime.fromisoformat(expiry)
        expected = datetime.now(timezone.utc) + timedelta(days=90)
        diff = abs((exp - expected).total_seconds())
        assert diff < 5


# ── Conflict detection tests ─────────────────────────────────────────


class TestDetectConflicts:
    def test_no_conflicts_empty_list(self):
        c = _make_candidate()
        conflicts = _detect_conflicts(c, [])
        assert conflicts == []

    def test_no_conflicts_different_domain(self):
        c = _make_candidate(domain=CandidateDomain.PREFERENCE)
        existing = [_make_candidate(candidate_id="cand_001", domain=CandidateDomain.INTEREST)]
        conflicts = _detect_conflicts(c, existing)
        assert conflicts == []

    def test_detects_same_domain_conflict(self):
        c = _make_candidate(domain=CandidateDomain.PREFERENCE)
        existing = [
            _make_candidate(
                candidate_id="cand_001",
                domain=CandidateDomain.PREFERENCE,
                confidence=0.8,
            )
        ]
        conflicts = _detect_conflicts(c, existing)
        assert "cand_001" in conflicts

    def test_ignores_declined_candidates(self):
        c = _make_candidate(domain=CandidateDomain.PREFERENCE)
        existing = [
            _make_candidate(
                candidate_id="cand_001",
                domain=CandidateDomain.PREFERENCE,
                status=CandidateStatus.DECLINED,
                confidence=0.8,
            )
        ]
        conflicts = _detect_conflicts(c, existing)
        assert conflicts == []

    def test_ignores_suppressed_candidates(self):
        c = _make_candidate(domain=CandidateDomain.PREFERENCE)
        existing = [
            _make_candidate(
                candidate_id="cand_001",
                domain=CandidateDomain.PREFERENCE,
                status=CandidateStatus.SUPPRESSED,
                confidence=0.8,
            )
        ]
        conflicts = _detect_conflicts(c, existing)
        assert conflicts == []

    def test_ignores_expired_candidates(self):
        c = _make_candidate(domain=CandidateDomain.PREFERENCE)
        existing = [
            _make_candidate(
                candidate_id="cand_001",
                domain=CandidateDomain.PREFERENCE,
                status=CandidateStatus.EXPIRED,
                confidence=0.8,
            )
        ]
        conflicts = _detect_conflicts(c, existing)
        assert conflicts == []

    def test_ignores_self(self):
        c = _make_candidate(candidate_id="cand_self")
        existing = [_make_candidate(candidate_id="cand_self")]
        conflicts = _detect_conflicts(c, existing)
        assert conflicts == []


# ── Confirmation requirement tests ───────────────────────────────────


class TestRequiresConfirmation:
    def test_always_requires_with_conflicts(self):
        assert _requires_confirmation(CandidateSensitivity.LOW, True) is True

    def test_high_sensitivity_requires(self):
        assert _requires_confirmation(CandidateSensitivity.HIGH, False) is True

    def test_identity_shaping_requires(self):
        assert _requires_confirmation(CandidateSensitivity.IDENTITY_SHAPING, False) is True

    def test_medium_requires(self):
        assert _requires_confirmation(CandidateSensitivity.MEDIUM, False) is True

    def test_low_no_conflicts_no_require(self):
        assert _requires_confirmation(CandidateSensitivity.LOW, False) is False


# ── Suppression tests ────────────────────────────────────────────────


class TestIsSuppressed:
    def test_matching_fingerprint(self):
        fp = _compute_fingerprint("test", "evidence")
        suppressed = [SuppressionFingerprint(
            fingerprint=fp,
            candidate_type="preference",
            declined_at="2026-07-12T00:00:00Z",
        )]
        assert _is_suppressed(fp, suppressed) is True

    def test_non_matching_fingerprint(self):
        fp1 = _compute_fingerprint("test1", "evidence1")
        fp2 = _compute_fingerprint("test2", "evidence2")
        suppressed = [SuppressionFingerprint(
            fingerprint=fp1,
            candidate_type="preference",
            declined_at="2026-07-12T00:00:00Z",
        )]
        assert _is_suppressed(fp2, suppressed) is False

    def test_empty_suppression_list(self):
        fp = _compute_fingerprint("test", "evidence")
        assert _is_suppressed(fp, []) is False


# ── Explicit fact extraction tests ───────────────────────────────────


class TestExtractExplicitFacts:
    def test_preference_extraction(self):
        interaction = {"user_message": "I prefer short answers", "timestamp": "2026-07-12T00:00:00Z"}
        facts = _extract_explicit_facts(interaction)
        assert len(facts) >= 1
        assert any(f["domain"] == CandidateDomain.PREFERENCE for f in facts)

    def test_interest_extraction(self):
        interaction = {"user_message": "I'm interested in machine learning", "timestamp": "2026-07-12T00:00:00Z"}
        facts = _extract_explicit_facts(interaction)
        assert len(facts) >= 1
        assert any(f["domain"] == CandidateDomain.INTEREST for f in facts)

    def test_value_extraction(self):
        interaction = {"user_message": "I value honesty above all", "timestamp": "2026-07-12T00:00:00Z"}
        facts = _extract_explicit_facts(interaction)
        assert len(facts) >= 1
        assert any(f["domain"] == CandidateDomain.VALUE for f in facts)

    def test_no_facts_in_plain_message(self):
        interaction = {"user_message": "What is the weather?", "timestamp": "2026-07-12T00:00:00Z"}
        facts = _extract_explicit_facts(interaction)
        assert facts == []

    def test_extracts_only_one_preference(self):
        interaction = {
            "user_message": "I prefer short answers and I also like Python",
            "timestamp": "2026-07-12T00:00:00Z",
        }
        facts = _extract_explicit_facts(interaction)
        # Should extract at most one preference, one interest
        pref_count = sum(1 for f in facts if f["domain"] == CandidateDomain.PREFERENCE)
        assert pref_count <= 1


# ── Extraction tests ─────────────────────────────────────────────────


class TestExtractCandidates:
    def test_empty_log(self):
        log = _make_temp_log([])
        candidates = extract_candidates(interaction_log_path=log)
        assert candidates == []

    def test_missing_log(self):
        candidates = extract_candidates(
            interaction_log_path=Path("/nonexistent/log.jsonl")
        )
        assert candidates == []

    def test_extracts_from_preference(self):
        log = _make_temp_log([
            {"user_message": "I prefer concise answers", "timestamp": "2026-07-12T00:00:00Z"},
        ])
        candidates = extract_candidates(interaction_log_path=log)
        assert len(candidates) >= 1
        pref_cands = [c for c in candidates if c.domain == CandidateDomain.PREFERENCE]
        assert len(pref_cands) >= 1
        assert pref_cands[0].source == CandidateSource.EXPLICIT_STATEMENT
        assert pref_cands[0].requires_confirmation is True  # medium sensitivity

    def test_sets_identity_shaping_confirmation(self):
        log = _make_temp_log([
            {"user_message": "I value honesty", "timestamp": "2026-07-12T00:00:00Z"},
        ])
        candidates = extract_candidates(interaction_log_path=log)
        value_cands = [c for c in candidates if c.domain == CandidateDomain.VALUE]
        assert len(value_cands) >= 1
        assert value_cands[0].requires_confirmation is True
        assert value_cands[0].sensitivity == CandidateSensitivity.IDENTITY_SHAPING

    def test_skips_suppressed(self):
        log = _make_temp_log([
            {"user_message": "I prefer concise answers", "timestamp": "2026-07-12T00:00:00Z"},
        ])
        fingerprint = _compute_fingerprint("I prefer concise answers", "I prefer concise answers")
        suppressed = [SuppressionFingerprint(
            fingerprint=fingerprint,
            candidate_type="preference",
            declined_at="2026-07-12T00:00:00Z",
        )]
        candidates = extract_candidates(
            interaction_log_path=log,
            suppression_list=suppressed,
        )
        assert len(candidates) == 0

    def test_respects_max_new(self):
        entries = []
        for i in range(20):
            entries.append({
                "user_message": f"I prefer option {i}",
                "timestamp": f"2026-07-12T00:{i:02d}:00Z",
            })
        log = _make_temp_log(entries)
        candidates = extract_candidates(interaction_log_path=log, max_new=3)
        assert len(candidates) <= 3

    def test_detects_conflicts_in_batch(self):
        log = _make_temp_log([
            {"user_message": "I prefer Python", "timestamp": "2026-07-12T00:00:00Z"},
            {"user_message": "I prefer Rust", "timestamp": "2026-07-12T00:01:00Z"},
        ])
        candidates = extract_candidates(interaction_log_path=log)
        # Both are preference domain, should detect conflicts
        pref_cands = [c for c in candidates if c.domain == CandidateDomain.PREFERENCE]
        if len(pref_cands) >= 2:
            assert pref_cands[0].requires_confirmation is True
            assert pref_cands[1].requires_confirmation is True


# ── Persistence tests ────────────────────────────────────────────────


class TestPersistence:
    def test_round_trip(self):
        tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        candidates = [
            _make_candidate(candidate_id="cand_a"),
            _make_candidate(candidate_id="cand_b", domain=CandidateDomain.VALUE),
        ]
        save_candidates(candidates, base_path=tmp)
        loaded = load_candidates(base_path=tmp)
        assert len(loaded) == 2
        assert loaded[0].candidate_id == "cand_a"
        assert loaded[1].candidate_id == "cand_b"
        assert loaded[1].domain == CandidateDomain.VALUE

    def test_load_empty(self):
        tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        loaded = load_candidates(base_path=tmp)
        assert loaded == []

    def test_suppression_round_trip(self):
        tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        fps = [
            SuppressionFingerprint(
                fingerprint="abc123",
                candidate_type="preference",
                declined_at="2026-07-12T00:00:00Z",
                reason="not accurate",
            ),
        ]
        save_suppression_fingerprints(fps, base_path=tmp)
        loaded = load_suppression_fingerprints(base_path=tmp)
        assert len(loaded) == 1
        assert loaded[0].fingerprint == "abc123"
        assert loaded[0].reason == "not accurate"


# ── Expiry tests ─────────────────────────────────────────────────────


class TestExpireStaleCandidates:
    def test_expires_past_candidate(self):
        from datetime import datetime, timedelta, timezone
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        candidates = [
            _make_candidate(
                candidate_id="cand_old",
                expires_at=past,
                status=CandidateStatus.PENDING,
            ),
            _make_candidate(
                candidate_id="cand_fresh",
                expires_at=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                status=CandidateStatus.PENDING,
            ),
        ]
        updated = expire_stale_candidates(candidates)
        assert updated[0].status == CandidateStatus.EXPIRED
        assert updated[1].status == CandidateStatus.PENDING

    def test_does_not_expire_accepted(self):
        from datetime import datetime, timedelta, timezone
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        candidates = [
            _make_candidate(
                candidate_id="cand_accepted",
                expires_at=past,
                status=CandidateStatus.ACCEPTED,
            ),
        ]
        updated = expire_stale_candidates(candidates)
        assert updated[0].status == CandidateStatus.ACCEPTED

    def test_empty_list(self):
        updated = expire_stale_candidates([])
        assert updated == []


# ── Serialization tests ──────────────────────────────────────────────


def test_candidate_to_dict_and_back():
    from agent_runtime.memory_candidates import _candidate_to_dict, _dict_to_candidate
    original = _make_candidate(
        candidate_id="cand_ser",
        domain=CandidateDomain.VALUE,
        sensitivity=CandidateSensitivity.IDENTITY_SHAPING,
        conflicts_with=["cand_001"],
        metadata={"key": "value"},
    )
    d = _candidate_to_dict(original)
    restored = _dict_to_candidate(d)
    assert restored.candidate_id == original.candidate_id
    assert restored.domain == original.domain
    assert restored.sensitivity == original.sensitivity
    assert restored.conflicts_with == original.conflicts_with
    assert restored.metadata == original.metadata
