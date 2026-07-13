"""Memory Inbox — A2 from implementation-plan-regulation-pkm.md.

ADR 0129: Memory Candidates Expire and Declines Are Suppressed.
ADR 0094: Historical Conversations Feed a Reviewed Candidate Queue.

Provides batched review of ~5 memory candidates with accept, edit, defer,
decline, and suppress actions. Weak candidates expire automatically.
No coercive badges or repeated declined suggestions. Source excerpts and
retrieval explanations are inspectable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .memory_candidates import (
    CandidateDomain,
    CandidateSensitivity,
    CandidateSource,
    CandidateStatus,
    MemoryCandidate,
    SuppressionFingerprint,
    _compute_fingerprint,
    _candidates_path,
    _suppression_path,
    _candidate_to_dict,
    _dict_to_candidate,
    expire_stale_candidates,
    load_candidates,
    load_suppression_fingerprints,
    save_suppression_fingerprints,
)


# ── Inbox configuration ──────────────────────────────────────────────

BATCH_SIZE_DEFAULT = 5
MAX_INBOX_SIZE = 20  # cap pending candidates before forcing review


# ── Inbox types ──────────────────────────────────────────────────────


@dataclass
class InboxItem:
    """A single review item in the memory inbox.

    Presents the proposed record, source evidence, affected existing
    records, and available actions.
    """

    candidate: MemoryCandidate
    source_excerpt: str  # the evidence excerpt for inspectability
    retrieval_explanation: str  # why this candidate was surfaced
    affected_records: List[Dict[str, Any]] = field(default_factory=list)
    available_actions: List[str] = field(
        default_factory=lambda: ["accept", "edit", "defer", "decline", "suppress"]
    )


@dataclass
class InboxPage:
    """A page of the memory inbox for review."""

    items: List[InboxItem]
    total_pending: int
    batch_size: int
    page: int
    has_more: bool
    summary: str = ""  # human-readable summary, no coercive language


# ── Inbox retrieval ──────────────────────────────────────────────────


def _build_retrieval_explanation(candidate: MemoryCandidate) -> str:
    """Build an inspectable retrieval explanation for a candidate.

    ADR 0129: Explanations are inspectable without exposing hidden reasoning.
    """
    domain_labels: Dict[CandidateDomain, str] = {
        CandidateDomain.PREFERENCE: "a stated preference",
        CandidateDomain.INTEREST: "an expressed interest",
        CandidateDomain.VALUE: "a possible value",
        CandidateDomain.PRINCIPLE: "a possible personal principle",
        CandidateDomain.GOAL: "a stated goal",
        CandidateDomain.PATTERN: "an observed pattern",
        CandidateDomain.RELATIONSHIP: "a relationship observation",
        CandidateDomain.COGNITIVE: "a cognitive support observation",
    }
    source_labels: Dict[CandidateSource, str] = {
        CandidateSource.EXPLICIT_STATEMENT: "explicitly stated",
        CandidateSource.MODEL_INFERENCE: "inferred from conversation",
        CandidateSource.REPEATED_PATTERN: "observed across multiple interactions",
        CandidateSource.HISTORICAL_BACKFILL: "imported from historical data",
    }

    domain_desc = domain_labels.get(candidate.domain, "an observation")
    source_desc = source_labels.get(candidate.source, "derived")

    explanation = f"This candidate represents {domain_desc}, {source_desc}."

    if candidate.requires_confirmation:
        explanation += " It requires your explicit confirmation before becoming durable memory."
    else:
        explanation += " It has low sensitivity and can be auto-accepted."

    if candidate.conflicts_with:
        explanation += f" It conflicts with {len(candidate.conflicts_with)} other pending candidate(s)."

    return explanation


def get_inbox(
    candidates: Optional[List[MemoryCandidate]] = None,
    page: int = 0,
    batch_size: int = BATCH_SIZE_DEFAULT,
    base_path: Optional[Any] = None,
) -> InboxPage:
    """Get a batched page of the memory inbox for review.

    Returns at most batch_size pending candidates. Automatically expires
    stale candidates before presenting the inbox.

    ADR 0129: No coercive badges. Expired candidates are summarized
    quietly without demanding action.
    """
    cands = candidates if candidates is not None else load_candidates(base_path)

    # Expire stale first
    cands = expire_stale_candidates(cands)

    # Only pending candidates
    pending = [c for c in cands if c.status == CandidateStatus.PENDING]

    # Sort by: requires_confirmation first, then by confidence descending
    pending.sort(key=lambda c: (not c.requires_confirmation, -c.confidence))

    total = len(pending)
    start = page * batch_size
    page_items = pending[start:start + batch_size]

    items: List[InboxItem] = []
    for candidate in page_items:
        # Build affected records info
        affected: List[Dict[str, Any]] = []
        for conflict_id in candidate.conflicts_with:
            conflict = next((c for c in cands if c.candidate_id == conflict_id), None)
            if conflict:
                affected.append({
                    "candidate_id": conflict.candidate_id,
                    "proposition": conflict.proposition[:200],
                    "status": conflict.status.value,
                })

        items.append(InboxItem(
            candidate=candidate,
            source_excerpt=candidate.evidence[:500],
            retrieval_explanation=_build_retrieval_explanation(candidate),
            affected_records=affected,
        ))

    has_more = start + batch_size < total

    # Build summary — capacity-aware, no pressure
    if total == 0:
        summary = "Your memory inbox is empty. No pending candidates to review."
    elif total <= batch_size:
        summary = f"You have {total} pending memory candidate(s). Review at your convenience."
    else:
        summary = (
            f"You have {total} pending memory candidates. "
            f"Showing {len(items)} in this batch. "
            "There is no deadline — review when you're ready."
        )

    return InboxPage(
        items=items,
        total_pending=total,
        batch_size=batch_size,
        page=page,
        has_more=has_more,
        summary=summary,
    )


# ── Inbox actions ────────────────────────────────────────────────────


def _find_candidate(
    candidate_id: str,
    candidates: List[MemoryCandidate],
) -> Optional[MemoryCandidate]:
    """Find a candidate by ID."""
    for c in candidates:
        if c.candidate_id == candidate_id:
            return c
    return None


def accept_candidate(
    candidate_id: str,
    candidates: Optional[List[MemoryCandidate]] = None,
    base_path: Optional[Any] = None,
) -> Dict[str, Any]:
    """Accept a memory candidate, promoting it to durable memory.

    Returns the accepted candidate and its new status.
    """
    cands = candidates if candidates is not None else load_candidates(base_path)
    candidate = _find_candidate(candidate_id, cands)
    if candidate is None:
        return {"status": "error", "message": f"Candidate {candidate_id} not found"}

    if candidate.status != CandidateStatus.PENDING:
        return {
            "status": "error",
            "message": f"Candidate {candidate_id} is already {candidate.status.value}",
        }

    candidate.status = CandidateStatus.ACCEPTED
    _persist_candidates(cands, base_path)

    return {
        "status": "ok",
        "candidate_id": candidate_id,
        "action": "accepted",
        "proposition": candidate.proposition,
        "domain": candidate.domain.value,
    }


def edit_candidate(
    candidate_id: str,
    edited_proposition: str,
    candidates: Optional[List[MemoryCandidate]] = None,
    base_path: Optional[Any] = None,
) -> Dict[str, Any]:
    """Edit a memory candidate's proposition before accepting.

    The original proposition is preserved for audit.
    """
    cands = candidates if candidates is not None else load_candidates(base_path)
    candidate = _find_candidate(candidate_id, cands)
    if candidate is None:
        return {"status": "error", "message": f"Candidate {candidate_id} not found"}

    if candidate.status != CandidateStatus.PENDING:
        return {
            "status": "error",
            "message": f"Candidate {candidate_id} is already {candidate.status.value}",
        }

    candidate.edited_proposition = edited_proposition
    candidate.status = CandidateStatus.EDITED
    _persist_candidates(cands, base_path)

    return {
        "status": "ok",
        "candidate_id": candidate_id,
        "action": "edited",
        "original_proposition": candidate.proposition,
        "edited_proposition": edited_proposition,
        "domain": candidate.domain.value,
    }


def defer_candidate(
    candidate_id: str,
    until: Optional[str] = None,
    candidates: Optional[List[MemoryCandidate]] = None,
    base_path: Optional[Any] = None,
) -> Dict[str, Any]:
    """Defer a memory candidate for later review.

    If `until` is provided, the candidate resurfaces after that date.
    Otherwise, it resurfaces when directly relevant.
    """
    cands = candidates if candidates is not None else load_candidates(base_path)
    candidate = _find_candidate(candidate_id, cands)
    if candidate is None:
        return {"status": "error", "message": f"Candidate {candidate_id} not found"}

    if candidate.status != CandidateStatus.PENDING:
        return {
            "status": "error",
            "message": f"Candidate {candidate_id} is already {candidate.status.value}",
        }

    candidate.status = CandidateStatus.DEFERRED
    if until:
        candidate.deferred_until = until
        candidate.expires_at = until  # don't expire before deferral date

    _persist_candidates(cands, base_path)

    return {
        "status": "ok",
        "candidate_id": candidate_id,
        "action": "deferred",
        "deferred_until": until or "when directly relevant",
        "domain": candidate.domain.value,
    }


def decline_candidate(
    candidate_id: str,
    reason: str = "",
    candidates: Optional[List[MemoryCandidate]] = None,
    base_path: Optional[Any] = None,
) -> Dict[str, Any]:
    """Decline a memory candidate with an optional reason.

    Creates a suppression fingerprint so the same candidate is not
    re-proposed without materially new evidence.
    """
    cands = candidates if candidates is not None else load_candidates(base_path)
    candidate = _find_candidate(candidate_id, cands)
    if candidate is None:
        return {"status": "error", "message": f"Candidate {candidate_id} not found"}

    if candidate.status != CandidateStatus.PENDING:
        return {
            "status": "error",
            "message": f"Candidate {candidate_id} is already {candidate.status.value}",
        }

    candidate.status = CandidateStatus.DECLINED
    now = datetime.now(timezone.utc).isoformat()

    # Create suppression fingerprint
    fingerprint = _compute_fingerprint(candidate.proposition, candidate.evidence)
    candidate.suppression_fingerprint = fingerprint

    suppression = SuppressionFingerprint(
        fingerprint=fingerprint,
        candidate_type=candidate.domain.value,
        declined_at=now,
        reason=reason,
    )
    save_suppression_fingerprints([suppression])

    _persist_candidates(cands, base_path)

    return {
        "status": "ok",
        "candidate_id": candidate_id,
        "action": "declined",
        "fingerprint": fingerprint[:16] + "...",
        "domain": candidate.domain.value,
    }


def suppress_candidate(
    candidate_id: str,
    reason: str = "",
    candidates: Optional[List[MemoryCandidate]] = None,
    base_path: Optional[Any] = None,
) -> Dict[str, Any]:
    """Suppress a memory candidate permanently.

    Stronger than decline — the fingerprint is retained and the candidate
    is marked suppressed. Only bypassed by materially new evidence.
    """
    cands = candidates if candidates is not None else load_candidates(base_path)
    candidate = _find_candidate(candidate_id, cands)
    if candidate is None:
        return {"status": "error", "message": f"Candidate {candidate_id} not found"}

    if candidate.status != CandidateStatus.PENDING:
        return {
            "status": "error",
            "message": f"Candidate {candidate_id} is already {candidate.status.value}",
        }

    candidate.status = CandidateStatus.SUPPRESSED
    now = datetime.now(timezone.utc).isoformat()

    fingerprint = _compute_fingerprint(candidate.proposition, candidate.evidence)
    candidate.suppression_fingerprint = fingerprint

    suppression = SuppressionFingerprint(
        fingerprint=fingerprint,
        candidate_type=candidate.domain.value,
        declined_at=now,
        reason=reason,
    )
    save_suppression_fingerprints([suppression])

    _persist_candidates(cands, base_path)

    return {
        "status": "ok",
        "candidate_id": candidate_id,
        "action": "suppressed",
        "fingerprint": fingerprint[:16] + "...",
        "domain": candidate.domain.value,
    }


# ── Persistence helpers ──────────────────────────────────────────────


def _persist_candidates(
    candidates: List[MemoryCandidate],
    base_path: Optional[Any] = None,
) -> None:
    """Rewrite the full candidates file."""
    from pathlib import Path as _Path
    path = _Path(str(base_path)) if base_path else _candidates_path()
    with path.open("w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(_candidate_to_dict(c)) + "\n")


import json  # noqa: E402 (already imported at top; here for clarity)
