"""Daily and weekly reviews — S2 from implementation-plan-regulation-pkm.md.

ADR 0109: Reviews Remain Domain-Separated and Unscored.
ADR 0088: Regulation Pattern Reviews Show Denominators and Uncertainty.

Summarizes denominators, uncertainty, minimum comparable sample,
helpful/harmful behaviors, outcomes, and one provisional focus per
review. Domains stay separate unless cross-domain synthesis is explicit.
Insufficient samples are shown as insufficient; reviews never state
personality conclusions as facts.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .paths import INTERACTION_LOG_PATH, SESSION_META_PATH, USER_MODEL_DIR, ensure_dirs, now_iso


# ── Review types ─────────────────────────────────────────────────────


class ReviewPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class ReviewDomain(str, Enum):
    """ADR 0109: Domains remain separated; cross-domain only on explicit request."""
    KNOWLEDGE = "knowledge"
    VALUES = "values"
    REGULATION = "regulation"
    COGNITIVE = "cognitive"
    RELATIONSHIPS = "relationships"
    SYSTEM_BELIEFS = "system_beliefs"


class BehaviorCategory(str, Enum):
    HELPFUL = "helpful"
    HARMFUL = "harmful"
    NEUTRAL = "neutral"


@dataclass
class ReviewFinding:
    """A single finding in a review.

    ADR 0109: Every finding retains domain evidence and controls to
    confirm, correct, reject, exclude, delete, or turn into a chosen
    Goal or Commitment.
    """

    finding_id: str
    domain: ReviewDomain
    description: str
    denominator: int  # total comparable records
    occurrence_count: int
    uncertainty: str  # human-readable uncertainty explanation
    evidence_excerpts: List[str] = field(default_factory=list)  # source excerpts
    contradictory_examples: int = 0
    status: str = "proposed"  # proposed, confirmed, corrected, rejected, excluded


@dataclass
class OutcomeSummary:
    """Summary of outcomes tracked across the review period."""

    completed: int = 0
    pending: int = 0
    unknown: int = 0
    acted_upon: int = 0
    not_acted: int = 0


@dataclass
class ReviewResult:
    """The result of a daily or weekly review.

    ADR 0088: Reviews require minimum comparable sample, distinguish
    completed/pending/unknown outcomes, preserve contradictory examples,
    and propose at most one user-confirmable focus.

    ADR 0109: No global scores (self-improvement, stability, productivity,
    relationship-quality, personal-worth).
    """

    review_id: str
    period: ReviewPeriod
    period_start: str
    period_end: str
    created_at: str
    domains_covered: List[ReviewDomain]
    minimum_sample_met: bool  # True if at least 3 comparable records exist
    total_records_examined: int
    findings: List[ReviewFinding] = field(default_factory=list)
    behaviors: Dict[str, int] = field(default_factory=dict)  # helpful/harmful/neutral counts
    outcomes: OutcomeSummary = field(default_factory=OutcomeSummary)
    provisional_focus: Optional[str] = None  # at most one
    insufficient_samples_note: Optional[str] = None
    cross_domain_synthesis: Optional[str] = None  # only on explicit request


# ── Constants ────────────────────────────────────────────────────────

REVIEWS_DIR: Path = USER_MODEL_DIR / "reviews"
MIN_COMPARABLE_SAMPLE: int = 3  # ADR 0088: at least 3 before proposing recurrence


# ── Persistence ──────────────────────────────────────────────────────


def _reviews_path(period: ReviewPeriod) -> Path:
    """Get the file path for a review period's log."""
    ensure_dirs()
    REVIEWS_DIR.mkdir(exist_ok=True)
    return REVIEWS_DIR / f"{period.value}_reviews.jsonl"


def _review_to_dict(review: ReviewResult) -> Dict[str, Any]:
    """Serialize a ReviewResult to a dictionary."""
    return {
        "review_id": review.review_id,
        "period": review.period.value,
        "period_start": review.period_start,
        "period_end": review.period_end,
        "created_at": review.created_at,
        "domains_covered": [d.value for d in review.domains_covered],
        "minimum_sample_met": review.minimum_sample_met,
        "total_records_examined": review.total_records_examined,
        "findings": [
            {
                "finding_id": f.finding_id,
                "domain": f.domain.value,
                "description": f.description,
                "denominator": f.denominator,
                "occurrence_count": f.occurrence_count,
                "uncertainty": f.uncertainty,
                "evidence_excerpts": f.evidence_excerpts,
                "contradictory_examples": f.contradictory_examples,
                "status": f.status,
            }
            for f in review.findings
        ],
        "behaviors": review.behaviors,
        "outcomes": {
            "completed": review.outcomes.completed,
            "pending": review.outcomes.pending,
            "unknown": review.outcomes.unknown,
            "acted_upon": review.outcomes.acted_upon,
            "not_acted": review.outcomes.not_acted,
        },
        "provisional_focus": review.provisional_focus,
        "insufficient_samples_note": review.insufficient_samples_note,
        "cross_domain_synthesis": review.cross_domain_synthesis,
    }


def _dict_to_review(d: Dict[str, Any]) -> ReviewResult:
    """Deserialize a dictionary to a ReviewResult."""
    return ReviewResult(
        review_id=d["review_id"],
        period=ReviewPeriod(d["period"]),
        period_start=d["period_start"],
        period_end=d["period_end"],
        created_at=d["created_at"],
        domains_covered=[ReviewDomain(rd) for rd in d["domains_covered"]],
        minimum_sample_met=d["minimum_sample_met"],
        total_records_examined=d["total_records_examined"],
        findings=[
            ReviewFinding(
                finding_id=f["finding_id"],
                domain=ReviewDomain(f["domain"]),
                description=f["description"],
                denominator=f["denominator"],
                occurrence_count=f["occurrence_count"],
                uncertainty=f["uncertainty"],
                evidence_excerpts=f.get("evidence_excerpts", []),
                contradictory_examples=f.get("contradictory_examples", 0),
                status=f.get("status", "proposed"),
            )
            for f in d.get("findings", [])
        ],
        behaviors=d.get("behaviors", {}),
        outcomes=OutcomeSummary(**d.get("outcomes", {})),
        provisional_focus=d.get("provisional_focus"),
        insufficient_samples_note=d.get("insufficient_samples_note"),
        cross_domain_synthesis=d.get("cross_domain_synthesis"),
    )


def save_review(review: ReviewResult) -> None:
    """Append a review result to the appropriate period log."""
    path = _reviews_path(review.period)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_review_to_dict(review)) + "\n")


def load_reviews(
    period: ReviewPeriod,
    limit: int = 20,
) -> List[ReviewResult]:
    """Load recent reviews for a period."""
    path = _reviews_path(period)
    if not path.exists():
        return []
    reviews: List[ReviewResult] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            reviews.append(_dict_to_review(json.loads(line)))
    return reviews[-limit:]


def get_latest_review(period: ReviewPeriod) -> Optional[ReviewResult]:
    """Get the most recent review for a period."""
    reviews = load_reviews(period, limit=1)
    return reviews[0] if reviews else None


# ── Review generation ────────────────────────────────────────────────


def _count_domain_records(
    domain: ReviewDomain,
    period_start: str,
    period_end: str,
) -> int:
    """Count interaction records within the period for a given domain.

    This is a simplified counting method — real implementation would
    parse interaction logs and filter by domain tags.
    """
    path = INTERACTION_LOG_PATH
    if not path.exists():
        return 0

    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                ts = record.get("timestamp", "")
                if period_start <= ts <= period_end:
                    tags = record.get("tags", [])
                    if domain.value in tags:
                        count += 1
            except (json.JSONDecodeError, KeyError):
                continue
    return count


def _classify_behavior(
    record: Dict[str, Any],
) -> Optional[BehaviorCategory]:
    """Classify a record's behavioral signal.

    Returns None if no classification can be made.
    """
    outcome = record.get("outcome", "")
    if outcome in ("helpful", "positive", "resolved"):
        return BehaviorCategory.HELPFUL
    elif outcome in ("harmful", "negative", "unhelpful"):
        return BehaviorCategory.HARMFUL
    elif outcome in ("neutral", "mixed", "observation"):
        return BehaviorCategory.NEUTRAL
    return None


def _count_outcomes(
    period_start: str,
    period_end: str,
) -> OutcomeSummary:
    """Count outcomes from interaction logs within the period."""
    summary = OutcomeSummary()
    path = INTERACTION_LOG_PATH
    if not path.exists():
        return summary

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                ts = record.get("timestamp", "")
                if not (period_start <= ts <= period_end):
                    continue
                outcome = record.get("outcome", "")
                tags = record.get("tags", [])
                if "acted" in tags:
                    summary.acted_upon += 1
                if "not_acted" in tags:
                    summary.not_acted += 1
                if outcome in ("completed", "resolved"):
                    summary.completed += 1
                elif outcome in ("pending", "in_progress"):
                    summary.pending += 1
                else:
                    summary.unknown += 1
            except (json.JSONDecodeError, KeyError):
                continue
    return summary


def generate_review(
    period: ReviewPeriod,
    domains: Optional[List[ReviewDomain]] = None,
    *,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    cross_domain_synthesis: bool = False,
) -> ReviewResult:
    """Generate a daily or weekly review.

    ADR 0088: At least MIN_COMPARABLE_SAMPLE (3) records required before
    proposing recurrence. Denominators and uncertainty are always shown.

    ADR 0109: Domains are kept separate. Cross-domain synthesis only on
    explicit request and preserves source domain of each conclusion.
    No global scores.
    """
    now = now_iso()

    if period_start is None:
        # Default: last 24 hours for daily, last 7 days for weekly
        now_dt = datetime.now(timezone.utc)
        if period == ReviewPeriod.DAILY:
            start_dt = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Start of the week (Monday)
            days_since_monday = now_dt.weekday()
            start_dt = (now_dt - __import__("datetime").timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        period_start = start_dt.isoformat(timespec="seconds")
        period_end = now

    if domains is None:
        domains = list(ReviewDomain)

    # Count records per domain
    domain_counts: Dict[ReviewDomain, int] = {}
    for domain in domains:
        domain_counts[domain] = _count_domain_records(domain, period_start, period_end)

    total_records = sum(domain_counts.values())
    minimum_sample_met = total_records >= MIN_COMPARABLE_SAMPLE

    # Generate findings per domain
    findings: List[ReviewFinding] = []
    for domain in domains:
        count = domain_counts[domain]
        if count == 0:
            continue

        finding = ReviewFinding(
            finding_id=str(uuid.uuid4()),
            domain=domain,
            description=_domain_summary(domain, count),
            denominator=total_records,
            occurrence_count=count,
            uncertainty=_uncertainty_text(count, total_records),
        )
        findings.append(finding)

    # Classify behaviors
    behaviors = _classify_behaviors(period_start, period_end)

    # Count outcomes
    outcomes = _count_outcomes(period_start, period_end)

    # Insufficient samples note
    insufficient_note = None
    if not minimum_sample_met:
        insufficient_note = (
            f"Only {total_records} comparable record(s) found in this period "
            f"(minimum {MIN_COMPARABLE_SAMPLE} required for pattern proposals). "
            f"Low logging volume is incomplete evidence, not poor progress."
        )

    # Cross-domain synthesis only on explicit request
    cross_domain_text = None
    if cross_domain_synthesis and len(findings) > 1:
        cross_domain_text = _cross_domain_synthesis_text(findings)

    return ReviewResult(
        review_id=str(uuid.uuid4()),
        period=period,
        period_start=period_start,
        period_end=period_end,
        created_at=now,
        domains_covered=domains,
        minimum_sample_met=minimum_sample_met,
        total_records_examined=total_records,
        findings=findings,
        behaviors=behaviors,
        outcomes=outcomes,
        provisional_focus=_choose_provisional_focus(findings, minimum_sample_met),
        insufficient_samples_note=insufficient_note,
        cross_domain_synthesis=cross_domain_text,
    )


def _domain_summary(domain: ReviewDomain, count: int) -> str:
    """Generate a domain-specific summary line.

    ADR 0109: No personality conclusions stated as facts.
    """
    templates = {
        ReviewDomain.KNOWLEDGE: f"{count} knowledge-related interaction(s) recorded",
        ReviewDomain.VALUES: f"{count} value-oriented interaction(s) recorded",
        ReviewDomain.REGULATION: f"{count} regulation interaction(s) recorded",
        ReviewDomain.COGNITIVE: f"{count} cognitive support interaction(s) recorded",
        ReviewDomain.RELATIONSHIPS: f"{count} relationship-oriented interaction(s) recorded",
        ReviewDomain.SYSTEM_BELIEFS: f"{count} system belief interaction(s) recorded",
    }
    return templates.get(domain, f"{count} interaction(s) in {domain.value}")


def _uncertainty_text(count: int, total: int) -> str:
    """Generate an uncertainty explanation.

    ADR 0088: Uncertainty is always shown alongside counts.
    """
    if total < MIN_COMPARABLE_SAMPLE:
        return (
            f"Insufficient records ({count}/{total}) to assess patterns. "
            f"These observations do not support confident conclusions."
        )
    pct = (count / total * 100) if total > 0 else 0
    return (
        f"Based on {count} of {total} records ({pct:.0f}%). "
        f"Small samples may not represent typical behavior. "
        f"Contradictory examples are preserved alongside patterns."
    )


def _classify_behaviors(
    period_start: str,
    period_end: str,
) -> Dict[str, int]:
    """Classify behavioral signals from interaction logs.

    Returns counts of helpful, harmful, and neutral behaviors.
    """
    counts: Dict[str, int] = {
        "helpful": 0,
        "harmful": 0,
        "neutral": 0,
    }
    path = INTERACTION_LOG_PATH
    if not path.exists():
        return counts

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                ts = record.get("timestamp", "")
                if not (period_start <= ts <= period_end):
                    continue
                category = _classify_behavior(record)
                if category is not None:
                    counts[category.value] += 1
            except (json.JSONDecodeError, KeyError):
                continue
    return counts


def _choose_provisional_focus(
    findings: List[ReviewFinding],
    minimum_sample_met: bool,
) -> Optional[str]:
    """Choose at most one provisional focus from findings.

    ADR 0088: Each review proposes at most one user-confirmable focus.
    """
    if not minimum_sample_met or not findings:
        return None

    # Find the domain with the most occurrences
    sorted_findings = sorted(findings, key=lambda f: f.occurrence_count, reverse=True)
    top = sorted_findings[0]
    return (
        f"Your {top.domain.value} domain had the most interactions this period "
        f"({top.occurrence_count} of {top.denominator}). Would you like to explore "
        f"this area further? This is a provisional observation, not a conclusion."
    )


def _cross_domain_synthesis_text(findings: List[ReviewFinding]) -> str:
    """Generate cross-domain synthesis text.

    ADR 0109: Cross-domain synthesis preserves source domain of each conclusion.
    """
    domains = [f.domain.value for f in findings]
    return (
        f"Cross-domain patterns observed across: {', '.join(domains)}. "
        f"Each finding below retains its source domain. These connections are "
        f"tentative and should be confirmed individually."
    )
