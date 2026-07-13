"""Tests for A3: Historical backfill."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Override conftest autouse fixture
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    """No-op: historical backfill tests are self-contained."""
    pass


from agent_runtime.historical_backfill import (
    BackfillJob,
    BackfillScope,
    BackfillState,
    EXCLUDED_BY_DEFAULT,
    PERMANENTLY_EXCLUDED,
    _extract_facts_for_backfill,
    _redact_sensitive,
    cancel_backfill,
    commit_backfill_candidates,
    create_backfill_job,
    delete_backfill,
    estimate_backfill_cost,
    execute_backfill_batch,
    get_backfill_status,
    grant_backfill_consent,
    pause_backfill,
    preview_backfill_payload,
    resume_backfill,
)
from agent_runtime.memory_candidates import (
    CandidateDomain,
    CandidateStatus,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_temp_log(entries: List[Dict[str, Any]]) -> Path:
    """Create a temporary interaction log file."""
    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    with tmp.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return tmp


def _default_scope(**overrides: Any) -> BackfillScope:
    """Create a default backfill scope."""
    defaults: Dict[str, Any] = {
        "source": "interaction_log",
        "max_candidates": 10,
        "batch_size": 3,
    }
    defaults.update(overrides)
    return BackfillScope(**defaults)


# ── Cost estimation tests ────────────────────────────────────────────


class TestEstimateCost:
    def test_empty_log(self):
        log = _make_temp_log([])
        result = estimate_backfill_cost(_default_scope(), interaction_log_path=log)
        assert result["status"] == "ok"
        assert result["total_interactions"] == 0

    def test_missing_log(self):
        result = estimate_backfill_cost(
            _default_scope(),
            interaction_log_path=Path("/nonexistent/log.jsonl"),
        )
        assert result["status"] == "error"

    def test_counts_interactions(self):
        log = _make_temp_log([
            {"user_message": "hello", "timestamp": "2026-07-01T00:00:00Z"},
            {"user_message": "world", "timestamp": "2026-07-02T00:00:00Z"},
        ])
        result = estimate_backfill_cost(_default_scope(), interaction_log_path=log)
        assert result["status"] == "ok"
        assert result["matching_interactions"] == 2

    def test_respects_date_range(self):
        log = _make_temp_log([
            {"user_message": "old", "timestamp": "2026-01-01T00:00:00Z"},
            {"user_message": "new", "timestamp": "2026-07-01T00:00:00Z"},
            {"user_message": "newer", "timestamp": "2026-08-01T00:00:00Z"},
        ])
        scope = _default_scope(
            date_from="2026-06-01T00:00:00Z",
            date_to="2026-07-31T00:00:00Z",
        )
        result = estimate_backfill_cost(scope, interaction_log_path=log)
        assert result["matching_interactions"] == 1

    def test_includes_domains_in_result(self):
        log = _make_temp_log([])
        result = estimate_backfill_cost(_default_scope(), interaction_log_path=log)
        assert "domains_in_scope" in result


# ── Payload preview tests ────────────────────────────────────────────


class TestPreviewPayload:
    def test_preview_shows_excerpts(self):
        log = _make_temp_log([
            {"user_message": "I prefer Python for data science", "timestamp": "2026-07-01T00:00:00Z"},
        ])
        result = preview_backfill_payload(_default_scope(), interaction_log_path=log)
        assert result["status"] == "ok"
        assert len(result["preview_entries"]) >= 1

    def test_preview_redacts_sensitive(self):
        log = _make_temp_log([
            {"user_message": "Contact me at user@example.com", "timestamp": "2026-07-01T00:00:00Z"},
        ])
        result = preview_backfill_payload(_default_scope(), interaction_log_path=log)
        content = str(result["preview_entries"])
        assert "user@example.com" not in content
        assert "[email]" in content


# ── Redaction tests ──────────────────────────────────────────────────


class TestRedactSensitive:
    def test_redacts_email(self):
        result = _redact_sensitive("Email me at john@example.com please")
        assert "john@example.com" not in result
        assert "[email]" in result

    def test_redacts_phone(self):
        result = _redact_sensitive("Call 555-123-4567 for help")
        assert "555-123-4567" not in result
        assert "[phone]" in result

    def test_redacts_url(self):
        result = _redact_sensitive("Visit https://example.com/page for info")
        assert "https://example.com/page" not in result
        assert "[url]" in result

    def test_preserves_normal_text(self):
        text = "I prefer concise answers and Python programming"
        result = _redact_sensitive(text)
        assert result == text


# ── Backfill lifecycle tests ─────────────────────────────────────────


class TestBackfillLifecycle:
    def test_create_in_draft_state(self):
        job = create_backfill_job(_default_scope())
        assert job.state == BackfillState.DRAFT
        assert job.candidates_produced == 0

    def test_grant_consent_moves_to_running(self):
        job = create_backfill_job(_default_scope())
        job = grant_backfill_consent(job)
        assert job.state == BackfillState.RUNNING
        assert job.consent_granted_at is not None

    def test_pause_and_resume(self):
        job = create_backfill_job(_default_scope())
        job = grant_backfill_consent(job)
        job = pause_backfill(job)
        assert job.state == BackfillState.PAUSED
        job = resume_backfill(job)
        assert job.state == BackfillState.RUNNING

    def test_cancel(self):
        job = create_backfill_job(_default_scope())
        job = grant_backfill_consent(job)
        job = cancel_backfill(job)
        assert job.state == BackfillState.CANCELLED
        assert job.cancelled_at is not None

    def test_delete(self):
        job = create_backfill_job(_default_scope())
        job = delete_backfill(job)
        assert job.state == BackfillState.DELETED
        assert job.deleted_at is not None

    def test_cannot_run_without_consent(self):
        job = create_backfill_job(_default_scope())
        log = _make_temp_log([
            {"user_message": "I prefer Python", "timestamp": "2026-07-01T00:00:00Z"},
        ])
        job = execute_backfill_batch(job, interaction_log_path=log)
        assert job.state == BackfillState.DRAFT
        assert job.candidates_produced == 0

    def test_get_status(self):
        job = create_backfill_job(_default_scope())
        status = get_backfill_status(job)
        assert status["state"] == "draft"
        assert "progress" in status


# ── Backfill execution tests ─────────────────────────────────────────


class TestExecuteBackfill:
    def test_extracts_candidates_from_log(self):
        job = create_backfill_job(_default_scope())
        job = grant_backfill_consent(job)
        log = _make_temp_log([
            {"user_message": "I prefer concise answers", "timestamp": "2026-07-01T00:00:00Z"},
            {"user_message": "I'm interested in AI", "timestamp": "2026-07-02T00:00:00Z"},
        ])
        job = execute_backfill_batch(job, interaction_log_path=log)
        assert job.candidates_produced > 0

    def test_respects_batch_size(self):
        job = create_backfill_job(_default_scope(batch_size=2))
        job = grant_backfill_consent(job)
        entries = []
        for i in range(10):
            entries.append({
                "user_message": f"I prefer option {i}",
                "timestamp": f"2026-07-{i+1:02d}T00:00:00Z",
            })
        log = _make_temp_log(entries)
        job = execute_backfill_batch(job, interaction_log_path=log)
        assert job.candidates_produced <= 2
        assert job.state == BackfillState.PAUSED  # paused for review

    def test_respects_max_candidates(self):
        job = create_backfill_job(_default_scope(max_candidates=3, batch_size=10))
        job = grant_backfill_consent(job)
        entries = []
        for i in range(20):
            entries.append({
                "user_message": f"I prefer option {i}",
                "timestamp": f"2026-07-{i+1:02d}T00:00:00Z",
            })
        log = _make_temp_log(entries)
        # Run multiple batches
        while job.state == BackfillState.RUNNING:
            job = execute_backfill_batch(job, interaction_log_path=log)
            if job.state == BackfillState.PAUSED:
                job = resume_backfill(job)
        assert job.candidates_produced <= 3

    def test_respects_date_range(self):
        job = create_backfill_job(_default_scope(
            date_from="2026-07-05T00:00:00Z",
            date_to="2026-07-10T00:00:00Z",
            batch_size=20,
        ))
        job = grant_backfill_consent(job)
        entries = []
        for i in range(15):
            entries.append({
                "user_message": f"I prefer option {i}",
                "timestamp": f"2026-07-{i+1:02d}T00:00:00Z",
            })
        log = _make_temp_log(entries)
        job = execute_backfill_batch(job, interaction_log_path=log)
        # Only days 5-10 should match, and within those only some have preference markers
        assert job.candidates_produced <= 6  # 6 days in range

    def test_all_candidates_require_confirmation(self):
        job = create_backfill_job(_default_scope(batch_size=10))
        job = grant_backfill_consent(job)
        log = _make_temp_log([
            {"user_message": "I prefer Python", "timestamp": "2026-07-01T00:00:00Z"},
        ])
        job = execute_backfill_batch(job, interaction_log_path=log)
        for c in job.candidates:
            assert c.requires_confirmation is True

    def test_commit_candidates(self):
        job = create_backfill_job(_default_scope())
        job = grant_backfill_consent(job)
        log = _make_temp_log([
            {"user_message": "I prefer Python", "timestamp": "2026-07-01T00:00:00Z"},
        ])
        job = execute_backfill_batch(job, interaction_log_path=log)
        tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        committed = commit_backfill_candidates(job, base_path=tmp)
        assert len(committed) == job.candidates_produced

    def test_completed_job_stays_completed(self):
        job = create_backfill_job(_default_scope(batch_size=10))
        job = grant_backfill_consent(job)
        log = _make_temp_log([
            {"user_message": "I prefer Python", "timestamp": "2026-07-01T00:00:00Z"},
        ])
        job = execute_backfill_batch(job, interaction_log_path=log)
        # Should be completed (no more interactions)
        assert job.state == BackfillState.COMPLETED
        # Re-executing should not change state
        job2 = execute_backfill_batch(job, interaction_log_path=log)
        assert job2.state == BackfillState.COMPLETED


# ── Fact extraction for backfill tests ───────────────────────────────


class TestExtractFactsForBackfill:
    def test_includes_pattern_facts(self):
        scope = _default_scope()
        facts = _extract_facts_for_backfill("I always work better in the morning", scope)
        assert any(f["domain"] == CandidateDomain.PATTERN for f in facts)

    def test_includes_cognitive_facts(self):
        scope = _default_scope()
        facts = _extract_facts_for_backfill("I get distracted by notifications", scope)
        assert any(f["domain"] == CandidateDomain.COGNITIVE for f in facts)

    def test_excludes_patterns_when_not_in_scope(self):
        scope = _default_scope(domains=[CandidateDomain.PREFERENCE])
        facts = _extract_facts_for_backfill("I always work better in the morning", scope)
        # Pattern extraction is suppressed when not in scope — no preference marker in this text
        pattern_facts = [f for f in facts if f["domain"] != CandidateDomain.PREFERENCE]
        assert len(pattern_facts) == 0
