"""Tests for A2: Memory Inbox review queue."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Override conftest autouse fixture
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    """No-op: memory inbox tests are self-contained."""
    pass


from agent_runtime.memory_candidates import (
    CandidateDomain,
    CandidateSensitivity,
    CandidateSource,
    CandidateStatus,
    MemoryCandidate,
    SuppressionFingerprint,
    _compute_fingerprint,
    _candidate_to_dict,
    expire_stale_candidates,
    load_candidates,
    load_suppression_fingerprints,
    save_candidates,
)
from agent_runtime.memory_inbox import (
    InboxItem,
    InboxPage,
    accept_candidate,
    decline_candidate,
    defer_candidate,
    edit_candidate,
    get_inbox,
    suppress_candidate,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_candidate(**overrides: Any) -> MemoryCandidate:
    """Create a MemoryCandidate with defaults."""
    defaults: Dict[str, Any] = {
        "candidate_id": "cand_test001",
        "domain": CandidateDomain.PREFERENCE,
        "sensitivity": CandidateSensitivity.MEDIUM,
        "source": CandidateSource.EXPLICIT_STATEMENT,
        "provenance": {"interaction_timestamp": "2026-07-12T00:00:00Z"},
        "proposition": "I prefer concise answers",
        "evidence": "User said: I prefer concise answers",
        "confidence": 0.85,
        "created_at": "2026-07-12T00:00:00Z",
        "expires_at": "2026-10-10T00:00:00Z",
        "requires_confirmation": True,
    }
    defaults.update(overrides)
    return MemoryCandidate(**defaults)


def _make_temp_candidates_file(candidates: List[MemoryCandidate]) -> Path:
    """Save candidates to a temp file and return the path."""
    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    save_candidates(candidates, base_path=tmp)
    return tmp


# ── Inbox retrieval tests ────────────────────────────────────────────


class TestGetInbox:
    def test_empty_inbox(self):
        page = get_inbox(candidates=[])
        assert page.total_pending == 0
        assert page.items == []
        assert page.has_more is False
        assert "empty" in page.summary.lower()

    def test_single_candidate(self):
        c = _make_candidate()
        page = get_inbox(candidates=[c])
        assert page.total_pending == 1
        assert len(page.items) == 1
        assert page.items[0].candidate.candidate_id == c.candidate_id
        assert page.has_more is False

    def test_batch_size_limit(self):
        candidates = [
            _make_candidate(candidate_id=f"cand_{i:03d}")
            for i in range(10)
        ]
        page = get_inbox(candidates=candidates, batch_size=5, page=0)
        assert page.total_pending == 10
        assert len(page.items) == 5
        assert page.has_more is True

    def test_page_two(self):
        candidates = [
            _make_candidate(candidate_id=f"cand_{i:03d}")
            for i in range(10)
        ]
        page = get_inbox(candidates=candidates, batch_size=5, page=1)
        assert len(page.items) == 5
        assert page.has_more is False
        assert page.page == 1

    def test_requires_confirmation_first(self):
        c_low = _make_candidate(
            candidate_id="cand_low",
            requires_confirmation=False,
            confidence=0.9,
        )
        c_high = _make_candidate(
            candidate_id="cand_high",
            requires_confirmation=True,
            confidence=0.5,
        )
        page = get_inbox(candidates=[c_low, c_high])
        # requires_confirmation=True should come first
        assert page.items[0].candidate.candidate_id == "cand_high"

    def test_source_excerpt_included(self):
        c = _make_candidate(evidence="User said: I like Python")
        page = get_inbox(candidates=[c])
        assert "I like Python" in page.items[0].source_excerpt

    def test_retrieval_explanation_included(self):
        c = _make_candidate()
        page = get_inbox(candidates=[c])
        assert len(page.items[0].retrieval_explanation) > 0

    def test_expires_stale_before_showing(self):
        from datetime import datetime, timedelta, timezone
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        c = _make_candidate(expires_at=past, status=CandidateStatus.PENDING)
        page = get_inbox(candidates=[c])
        assert page.total_pending == 0  # expired, not shown

    def test_no_coercive_language(self):
        candidates = [_make_candidate(candidate_id=f"cand_{i:03d}") for i in range(30)]
        page = get_inbox(candidates=candidates)
        coercive = ["must", "required", "urgent", "immediately", "don't miss", "important"]
        for word in coercive:
            assert word not in page.summary.lower()

    def test_affected_records_for_conflicts(self):
        c1 = _make_candidate(candidate_id="cand_1")
        c2 = _make_candidate(
            candidate_id="cand_2",
            domain=CandidateDomain.PREFERENCE,
            conflicts_with=["cand_1"],
        )
        page = get_inbox(candidates=[c1, c2])
        # Find c2 in items
        c2_item = next((item for item in page.items if item.candidate.candidate_id == "cand_2"), None)
        assert c2_item is not None
        assert len(c2_item.affected_records) >= 1


# ── Accept tests ─────────────────────────────────────────────────────


class TestAcceptCandidate:
    def test_accept_pending(self):
        c = _make_candidate()
        result = accept_candidate(c.candidate_id, candidates=[c])
        assert result["status"] == "ok"
        assert result["action"] == "accepted"
        assert c.status == CandidateStatus.ACCEPTED

    def test_accept_not_found(self):
        result = accept_candidate("nonexistent", candidates=[])
        assert result["status"] == "error"

    def test_accept_already_accepted(self):
        c = _make_candidate(status=CandidateStatus.ACCEPTED)
        result = accept_candidate(c.candidate_id, candidates=[c])
        assert result["status"] == "error"


# ── Edit tests ───────────────────────────────────────────────────────


class TestEditCandidate:
    def test_edit_pending(self):
        c = _make_candidate()
        result = edit_candidate(c.candidate_id, "edited text", candidates=[c])
        assert result["status"] == "ok"
        assert result["action"] == "edited"
        assert c.status == CandidateStatus.EDITED
        assert c.edited_proposition == "edited text"

    def test_edit_preserves_original(self):
        original = "I prefer concise answers"
        c = _make_candidate(proposition=original)
        edit_candidate(c.candidate_id, "I prefer detailed answers", candidates=[c])
        assert c.proposition == original  # original preserved
        assert c.edited_proposition == "I prefer detailed answers"

    def test_edit_not_found(self):
        result = edit_candidate("nonexistent", "new text", candidates=[])
        assert result["status"] == "error"


# ── Defer tests ──────────────────────────────────────────────────────


class TestDeferCandidate:
    def test_defer_pending(self):
        c = _make_candidate()
        result = defer_candidate(c.candidate_id, candidates=[c])
        assert result["status"] == "ok"
        assert c.status == CandidateStatus.DEFERRED

    def test_defer_with_date(self):
        c = _make_candidate()
        result = defer_candidate(
            c.candidate_id,
            until="2026-09-01T00:00:00Z",
            candidates=[c],
        )
        assert result["status"] == "ok"
        assert c.deferred_until == "2026-09-01T00:00:00Z"
        assert c.expires_at == "2026-09-01T00:00:00Z"

    def test_defer_not_found(self):
        result = defer_candidate("nonexistent", candidates=[])
        assert result["status"] == "error"


# ── Decline tests ────────────────────────────────────────────────────


class TestDeclineCandidate:
    def test_decline_pending(self):
        c = _make_candidate()
        result = decline_candidate(c.candidate_id, candidates=[c])
        assert result["status"] == "ok"
        assert c.status == CandidateStatus.DECLINED
        assert c.suppression_fingerprint is not None

    def test_decline_with_reason(self):
        c = _make_candidate()
        decline_candidate(c.candidate_id, "not accurate", candidates=[c])
        assert c.status == CandidateStatus.DECLINED

    def test_decline_creates_fingerprint(self):
        c = _make_candidate(proposition="unique test prop")
        result = decline_candidate(c.candidate_id, candidates=[c])
        assert "fingerprint" in result

    def test_decline_not_found(self):
        result = decline_candidate("nonexistent", candidates=[])
        assert result["status"] == "error"


# ── Suppress tests ───────────────────────────────────────────────────


class TestSuppressCandidate:
    def test_suppress_pending(self):
        c = _make_candidate()
        result = suppress_candidate(c.candidate_id, candidates=[c])
        assert result["status"] == "ok"
        assert c.status == CandidateStatus.SUPPRESSED
        assert c.suppression_fingerprint is not None

    def test_suppress_not_found(self):
        result = suppress_candidate("nonexistent", candidates=[])
        assert result["status"] == "error"


# ── Integration: full inbox flow ─────────────────────────────────────


class TestFullInboxFlow:
    def test_accept_removes_from_inbox(self):
        c = _make_candidate()
        accept_candidate(c.candidate_id, candidates=[c])
        page = get_inbox(candidates=[c])
        assert page.total_pending == 0

    def test_decline_removes_from_inbox(self):
        c = _make_candidate()
        decline_candidate(c.candidate_id, candidates=[c])
        page = get_inbox(candidates=[c])
        assert page.total_pending == 0

    def test_mixed_actions(self):
        c1 = _make_candidate(candidate_id="cand_1")
        c2 = _make_candidate(candidate_id="cand_2")
        c3 = _make_candidate(candidate_id="cand_3")
        candidates = [c1, c2, c3]

        accept_candidate("cand_1", candidates=candidates)
        defer_candidate("cand_2", candidates=candidates)

        page = get_inbox(candidates=candidates)
        assert page.total_pending == 1
        assert page.items[0].candidate.candidate_id == "cand_3"

    def test_decline_suppresses_re_extraction(self):
        """Declined candidates create fingerprints that block re-extraction."""
        c = _make_candidate(
            proposition="I prefer Python",
            evidence="I prefer Python",
        )
        fingerprint = _compute_fingerprint("I prefer Python", "I prefer Python")
        decline_candidate(c.candidate_id, candidates=[c])

        # Simulate suppression check
        from agent_runtime.memory_candidates import _is_suppressed
        suppressed = [SuppressionFingerprint(
            fingerprint=fingerprint,
            candidate_type="preference",
            declined_at="2026-07-12T00:00:00Z",
        )]
        assert _is_suppressed(fingerprint, suppressed) is True
