"""Tests for S2: Daily and weekly reviews."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Override conftest autouse fixture
@pytest.fixture(autouse=True)
def _isolate_paths(monkeypatch) -> None:
    """Redirect review paths to temporary directory."""
    import agent_runtime.reviews as mod

    fd, tmp_log = tempfile.mkstemp(suffix=".jsonl")
    Path(tmp_log).unlink()  # Remove; we'll create it fresh

    tmp_dir = Path(tempfile.mkdtemp())
    reviews_dir = tmp_dir / "reviews"
    reviews_dir.mkdir()

    monkeypatch.setattr(mod, "INTERACTION_LOG_PATH", Path(tmp_log))
    monkeypatch.setattr(mod, "REVIEWS_DIR", reviews_dir)

    yield

    try:
        Path(tmp_log).unlink()
    except FileNotFoundError:
        pass
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)


from agent_runtime.reviews import (
    MIN_COMPARABLE_SAMPLE,
    BehaviorCategory,
    OutcomeSummary,
    ReviewDomain,
    ReviewFinding,
    ReviewPeriod,
    ReviewResult,
    _choose_provisional_focus,
    _classify_behavior,
    _classify_behaviors,
    _count_domain_records,
    _count_outcomes,
    _cross_domain_synthesis_text,
    _domain_summary,
    _uncertainty_text,
    generate_review,
    get_latest_review,
    load_reviews,
    save_review,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _write_interaction(
    timestamp: str,
    outcome: str = "",
    tags: Optional[List[str]] = None,
    user_message: str = "test message",
) -> None:
    """Write a single interaction to the test log."""
    import agent_runtime.reviews as mod

    record = {
        "timestamp": timestamp,
        "user_message": user_message,
        "agent_response": "",
        "outcome": outcome,
        "tags": tags or [],
    }
    log_path = mod.INTERACTION_LOG_PATH
    existing = []
    if log_path.exists():
        existing = log_path.read_text(encoding="utf-8").strip().split("\n")
        existing = [e for e in existing if e.strip()]
    existing.append(json.dumps(record))
    log_path.write_text("\n".join(existing) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _period_range(hours_back: int = 24) -> tuple:
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=hours_back)).isoformat(timespec="seconds")
    end = now.isoformat(timespec="seconds")
    return start, end


# ── Domain summary tests ─────────────────────────────────────────────


class TestDomainSummary:
    def test_knowledge_summary(self):
        text = _domain_summary(ReviewDomain.KNOWLEDGE, 5)
        assert "knowledge" in text.lower()
        assert "5" in text

    def test_values_summary(self):
        text = _domain_summary(ReviewDomain.VALUES, 3)
        assert "value" in text.lower()
        assert "3" in text

    def test_regulation_summary(self):
        text = _domain_summary(ReviewDomain.REGULATION, 7)
        assert "regulation" in text.lower()
        assert "7" in text

    def test_summary_never_states_personality_conclusion(self):
        """ADR 0109: reviews never state personality conclusions as facts."""
        for domain in ReviewDomain:
            text = _domain_summary(domain, 10)
            # Should not contain personality labels
            assert "you are" not in text.lower()
            assert "your personality" not in text.lower()
            assert "characterized by" not in text.lower()


# ── Uncertainty text tests ───────────────────────────────────────────


class TestUncertaintyText:
    def test_insufficient_sample_shows_uncertainty(self):
        text = _uncertainty_text(1, 2)
        assert "insufficient" in text.lower()

    def test_sufficient_sample_shows_percentage(self):
        text = _uncertainty_text(5, 10)
        assert "50%" in text

    def test_uncertainty_always_visible(self):
        """ADR 0088: uncertainty is always shown."""
        text = _uncertainty_text(100, 100)
        assert len(text) > 0
        assert "small samples" in text.lower() or "%" in text


# ── Behavior classification tests ────────────────────────────────────


class TestClassifyBehavior:
    def test_helpful_outcome(self):
        assert _classify_behavior({"outcome": "helpful"}) == BehaviorCategory.HELPFUL
        assert _classify_behavior({"outcome": "positive"}) == BehaviorCategory.HELPFUL
        assert _classify_behavior({"outcome": "resolved"}) == BehaviorCategory.HELPFUL

    def test_harmful_outcome(self):
        assert _classify_behavior({"outcome": "harmful"}) == BehaviorCategory.HARMFUL
        assert _classify_behavior({"outcome": "negative"}) == BehaviorCategory.HARMFUL
        assert _classify_behavior({"outcome": "unhelpful"}) == BehaviorCategory.HARMFUL

    def test_neutral_outcome(self):
        assert _classify_behavior({"outcome": "neutral"}) == BehaviorCategory.NEUTRAL
        assert _classify_behavior({"outcome": "mixed"}) == BehaviorCategory.NEUTRAL
        assert _classify_behavior({"outcome": "observation"}) == BehaviorCategory.NEUTRAL

    def test_unknown_outcome_returns_none(self):
        assert _classify_behavior({"outcome": "something_else"}) is None
        assert _classify_behavior({"outcome": ""}) is None
        assert _classify_behavior({}) is None


# ── Outcome counting tests ───────────────────────────────────────────


class TestCountOutcomes:
    def test_counts_completed(self):
        start, end = _period_range(24)
        _write_interaction(start, outcome="completed")
        summary = _count_outcomes(start, end)
        assert summary.completed == 1

    def test_counts_pending(self):
        start, end = _period_range(24)
        _write_interaction(start, outcome="pending")
        summary = _count_outcomes(start, end)
        assert summary.pending == 1

    def test_counts_unknown(self):
        start, end = _period_range(24)
        _write_interaction(start, outcome="something_weird")
        summary = _count_outcomes(start, end)
        assert summary.unknown == 1

    def test_counts_acted_not_acted(self):
        start, end = _period_range(24)
        _write_interaction(start, outcome="completed", tags=["acted"])
        _write_interaction(start, outcome="pending", tags=["not_acted"])
        summary = _count_outcomes(start, end)
        assert summary.acted_upon == 1
        assert summary.not_acted == 1

    def test_ignores_outside_period(self):
        start, end = _period_range(24)
        outside = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(timespec="seconds")
        _write_interaction(outside, outcome="completed")
        summary = _count_outcomes(start, end)
        assert summary.completed == 0


# ── Review generation tests ──────────────────────────────────────────


class TestGenerateReview:
    def test_generates_daily_review_with_insufficient_samples(self):
        start, end = _period_range(24)
        _write_interaction(start, outcome="helpful", tags=["knowledge"])

        review = generate_review(
            ReviewPeriod.DAILY,
            period_start=start,
            period_end=end,
        )
        assert review.period == ReviewPeriod.DAILY
        assert review.minimum_sample_met is False
        assert review.insufficient_samples_note is not None
        assert "incomplete evidence" in review.insufficient_samples_note.lower()

    def test_generates_review_with_sufficient_samples(self):
        start, end = _period_range(24)
        for i in range(5):
            ts = (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(timespec="seconds")
            _write_interaction(ts, outcome="helpful", tags=["knowledge"])

        review = generate_review(
            ReviewPeriod.DAILY,
            period_start=start,
            period_end=end,
        )
        assert review.minimum_sample_met is True
        assert review.total_records_examined >= 5

    def test_review_has_no_global_scores(self):
        """ADR 0109: No global self-improvement, stability, productivity scores."""
        start, end = _period_range(24)
        for i in range(5):
            ts = (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(timespec="seconds")
            _write_interaction(ts, outcome="helpful", tags=["knowledge"])

        review = generate_review(
            ReviewPeriod.DAILY,
            period_start=start,
            period_end=end,
        )
        review_dict = _review_to_dict(review)
        # Check no score-like fields
        text = json.dumps(review_dict).lower()
        assert "self_improvement_score" not in text
        assert "stability_score" not in text
        assert "productivity_score" not in text
        assert "personal_worth" not in text

    def test_provisional_focus_at_most_one(self):
        """ADR 0088: at most one provisional focus."""
        start, end = _period_range(24)
        for i in range(5):
            ts = (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(timespec="seconds")
            _write_interaction(ts, outcome="helpful", tags=["knowledge"])

        review = generate_review(
            ReviewPeriod.DAILY,
            period_start=start,
            period_end=end,
        )
        assert review.provisional_focus is not None
        # Should be exactly one focus
        assert "\n" not in review.provisional_focus  # single line

    def test_insufficient_samples_no_focus(self):
        """ADR 0088: insufficient samples = no recurrence proposal."""
        start, end = _period_range(24)
        _write_interaction(start, outcome="helpful", tags=["knowledge"])

        review = generate_review(
            ReviewPeriod.DAILY,
            period_start=start,
            period_end=end,
        )
        assert review.minimum_sample_met is False
        assert review.provisional_focus is None

    def test_weekly_review(self):
        start = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
        end = _now_iso()
        for i in range(10):
            ts = (datetime.now(timezone.utc) - timedelta(days=i % 6)).isoformat(timespec="seconds")
            _write_interaction(ts, outcome="helpful", tags=["knowledge"])

        review = generate_review(
            ReviewPeriod.WEEKLY,
            period_start=start,
            period_end=end,
        )
        assert review.period == ReviewPeriod.WEEKLY

    def test_domains_remain_separate(self):
        """ADR 0109: domains kept separate."""
        start, end = _period_range(24)
        _write_interaction(start, outcome="helpful", tags=["knowledge"])
        _write_interaction(start, outcome="helpful", tags=["regulation"])
        _write_interaction(start, outcome="helpful", tags=["values"])

        review = generate_review(
            ReviewPeriod.DAILY,
            period_start=start,
            period_end=end,
        )
        domains_in_findings = {f.domain for f in review.findings}
        assert len(domains_in_findings) >= 2  # multiple domains present

    def test_cross_domain_only_on_request(self):
        """ADR 0109: cross-domain only on explicit request."""
        start, end = _period_range(24)
        for i in range(3):
            ts = (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(timespec="seconds")
            _write_interaction(ts, outcome="helpful", tags=["knowledge"])
        for i in range(3):
            ts = (datetime.now(timezone.utc) - timedelta(hours=i + 3)).isoformat(timespec="seconds")
            _write_interaction(ts, outcome="helpful", tags=["values"])

        # Without explicit request
        review = generate_review(
            ReviewPeriod.DAILY,
            period_start=start,
            period_end=end,
            cross_domain_synthesis=False,
        )
        assert review.cross_domain_synthesis is None

        # With explicit request
        review2 = generate_review(
            ReviewPeriod.DAILY,
            period_start=start,
            period_end=end,
            cross_domain_synthesis=True,
        )
        assert review2.cross_domain_synthesis is not None

    def test_finding_has_domain_evidence(self):
        """ADR 0109: every finding retains domain evidence."""
        start, end = _period_range(24)
        for i in range(5):
            ts = (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(timespec="seconds")
            _write_interaction(ts, outcome="helpful", tags=["knowledge"])

        review = generate_review(
            ReviewPeriod.DAILY,
            period_start=start,
            period_end=end,
        )
        for finding in review.findings:
            assert finding.domain is not None
            assert finding.description  # non-empty
            assert finding.denominator > 0
            assert finding.uncertainty  # non-empty
            assert finding.status in ("proposed", "confirmed", "corrected", "rejected", "excluded")


# ── Persistence tests ────────────────────────────────────────────────


class TestReviewPersistence:
    def test_save_and_load(self):
        review = ReviewResult(
            review_id="test-001",
            period=ReviewPeriod.DAILY,
            period_start=_now_iso(),
            period_end=_now_iso(),
            created_at=_now_iso(),
            domains_covered=[ReviewDomain.KNOWLEDGE],
            minimum_sample_met=True,
            total_records_examined=5,
            findings=[
                ReviewFinding(
                    finding_id="f-001",
                    domain=ReviewDomain.KNOWLEDGE,
                    description="test finding",
                    denominator=5,
                    occurrence_count=3,
                    uncertainty="test uncertainty",
                )
            ],
            outcomes=OutcomeSummary(completed=3, pending=1, unknown=1),
            provisional_focus="test focus",
        )
        save_review(review)
        loaded = load_reviews(ReviewPeriod.DAILY)
        assert len(loaded) == 1
        assert loaded[0].review_id == "test-001"
        assert loaded[0].findings[0].description == "test finding"

    def test_get_latest_review(self):
        r1 = ReviewResult(
            review_id="r1", period=ReviewPeriod.DAILY,
            period_start=_now_iso(), period_end=_now_iso(),
            created_at=_now_iso(),
            domains_covered=[ReviewDomain.KNOWLEDGE],
            minimum_sample_met=True, total_records_examined=5,
        )
        r2 = ReviewResult(
            review_id="r2", period=ReviewPeriod.DAILY,
            period_start=_now_iso(), period_end=_now_iso(),
            created_at=_now_iso(),
            domains_covered=[ReviewDomain.VALUES],
            minimum_sample_met=True, total_records_examined=3,
        )
        save_review(r1)
        save_review(r2)

        latest = get_latest_review(ReviewPeriod.DAILY)
        assert latest is not None
        assert latest.review_id == "r2"

    def test_load_returns_empty_for_no_data(self):
        reviews = load_reviews(ReviewPeriod.WEEKLY)
        assert reviews == []

    def test_round_trip_no_findings(self):
        review = ReviewResult(
            review_id="empty-1",
            period=ReviewPeriod.DAILY,
            period_start=_now_iso(),
            period_end=_now_iso(),
            created_at=_now_iso(),
            domains_covered=[ReviewDomain.KNOWLEDGE],
            minimum_sample_met=False,
            total_records_examined=0,
            insufficient_samples_note="not enough data",
        )
        save_review(review)
        loaded = load_reviews(ReviewPeriod.DAILY)
        assert len(loaded) == 1
        assert loaded[0].insufficient_samples_note == "not enough data"
        assert loaded[0].minimum_sample_met is False


# ── Provisional focus tests ──────────────────────────────────────────


class TestProvisionalFocus:
    def test_no_focus_with_insufficient_samples(self):
        findings = [
            ReviewFinding(
                finding_id="f1", domain=ReviewDomain.KNOWLEDGE,
                description="test", denominator=2, occurrence_count=2,
                uncertainty="low sample",
            )
        ]
        focus = _choose_provisional_focus(findings, minimum_sample_met=False)
        assert focus is None

    def test_no_focus_with_empty_findings(self):
        focus = _choose_provisional_focus([], minimum_sample_met=True)
        assert focus is None

    def test_focus_chooses_highest_occurrence(self):
        findings = [
            ReviewFinding(
                finding_id="f1", domain=ReviewDomain.KNOWLEDGE,
                description="a", denominator=10, occurrence_count=3,
                uncertainty="test",
            ),
            ReviewFinding(
                finding_id="f2", domain=ReviewDomain.VALUES,
                description="b", denominator=10, occurrence_count=7,
                uncertainty="test",
            ),
        ]
        focus = _choose_provisional_focus(findings, minimum_sample_met=True)
        assert focus is not None
        assert "values" in focus.lower()

    def test_focus_is_provisional_not_conclusive(self):
        """ADR 0088: focus is provisional, not a conclusion."""
        findings = [
            ReviewFinding(
                finding_id="f1", domain=ReviewDomain.KNOWLEDGE,
                description="test", denominator=5, occurrence_count=5,
                uncertainty="test",
            )
        ]
        focus = _choose_provisional_focus(findings, minimum_sample_met=True)
        assert focus is not None
        assert "provisional" in focus.lower()


# ── Cross-domain synthesis tests ─────────────────────────────────────


class TestCrossDomainSynthesis:
    def test_preserves_source_domain(self):
        """ADR 0109: cross-domain preserves source domain of each conclusion."""
        findings = [
            ReviewFinding(
                finding_id="f1", domain=ReviewDomain.KNOWLEDGE,
                description="a", denominator=10, occurrence_count=5,
                uncertainty="test",
            ),
            ReviewFinding(
                finding_id="f2", domain=ReviewDomain.VALUES,
                description="b", denominator=10, occurrence_count=5,
                uncertainty="test",
            ),
        ]
        text = _cross_domain_synthesis_text(findings)
        assert "knowledge" in text.lower()
        assert "values" in text.lower()
        assert "tentative" in text.lower()


# ── Behavior classification over period tests ────────────────────────


class TestClassifyBehaviors:
    def test_counts_helpful_behaviors(self):
        start, end = _period_range(24)
        _write_interaction(start, outcome="helpful")
        _write_interaction(start, outcome="positive")
        counts = _classify_behaviors(start, end)
        assert counts["helpful"] == 2

    def test_counts_harmful_behaviors(self):
        start, end = _period_range(24)
        _write_interaction(start, outcome="harmful")
        counts = _classify_behaviors(start, end)
        assert counts["harmful"] == 1

    def test_empty_log_returns_zeros(self):
        start, end = _period_range(24)
        counts = _classify_behaviors(start, end)
        assert counts["helpful"] == 0
        assert counts["harmful"] == 0
        assert counts["neutral"] == 0


# ── Helper for serialization ─────────────────────────────────────────


def _review_to_dict(review: ReviewResult) -> dict:
    """Quick serialization helper for tests."""
    from agent_runtime.reviews import _review_to_dict as _rtd
    return _rtd(review)
