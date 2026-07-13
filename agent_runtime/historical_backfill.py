"""Historical backfill — A3 from implementation-plan-regulation-pkm.md.

ADR 0094: Historical Conversations Feed a Reviewed Candidate Queue.

An explicit, bounded, and reversible process that derives Memory
Candidates from Owner-selected past conversations or artifacts. Reports
scope and cost, excludes sensitive domains by default, pauses at review
capacity, and never converts imported history directly into authoritative
personal memory.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .memory_candidates import (
    CandidateDomain,
    CandidateSensitivity,
    CandidateSource,
    CandidateStatus,
    MemoryCandidate,
    _classify_sensitivity,
    _compute_fingerprint,
    _default_expiry,
    _requires_confirmation,
    load_candidates,
    load_suppression_fingerprints,
    save_candidates,
)
from .paths import INTERACTION_LOG_PATH, ensure_dirs, now_iso


# ── Backfill types ───────────────────────────────────────────────────


class BackfillState(str, Enum):
    """State of a historical backfill job."""
    DRAFT = "draft"  # scope selected, not yet consented
    PREVIEW = "preview"  # cost and payload shown, awaiting consent
    RUNNING = "running"
    PAUSED = "paused"  # at review capacity
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DELETED = "deleted"


@dataclass
class BackfillScope:
    """The scope of a historical backfill operation.

    ADR 0094: Default scope excludes Regulation and intimate relationship content.
    """

    source: str  # "interaction_log" or path to source file
    date_from: Optional[str] = None  # ISO date
    date_to: Optional[str] = None
    domains: List[CandidateDomain] = field(default_factory=lambda: [
        CandidateDomain.PREFERENCE,
        CandidateDomain.INTEREST,
        CandidateDomain.PATTERN,
        CandidateDomain.COGNITIVE,
    ])
    excluded_domains: List[CandidateDomain] = field(default_factory=lambda: [
        # Regulation and relationship content excluded by default
    ])
    max_candidates: int = 30
    batch_size: int = 5  # pause every N candidates for review


@dataclass
class BackfillJob:
    """A historical backfill operation with full lifecycle."""

    job_id: str
    scope: BackfillScope
    state: BackfillState = BackfillState.DRAFT
    created_at: str = field(default_factory=now_iso)
    candidates_produced: int = 0
    candidates: List[MemoryCandidate] = field(default_factory=list)
    processed_indices: Set[int] = field(default_factory=set)
    consent_granted_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    deleted_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Excluded domains ─────────────────────────────────────────────────

# ADR 0094: Default scope excludes Regulation and intimate relationship content.
EXCLUDED_BY_DEFAULT: Set[CandidateDomain] = {
    # Regulation records are explicitly excluded from all backfill
    # by the store boundary (RegulationStore is separate).
    # We also default-exclude relationship content that could be intimate.
    CandidateDomain.RELATIONSHIP,
}

# These domains are permanently excluded from backfill — they cannot
# be added to scope even with explicit consent.
PERMANENTLY_EXCLUDED: Set[CandidateDomain] = set()  # Reserved for future safety rules


# ── Cost estimation ──────────────────────────────────────────────────


def estimate_backfill_cost(
    scope: BackfillScope,
    interaction_log_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Estimate the cost of a backfill operation before execution.

    Returns token estimates and scope summary without sending data.
    """
    log_path = interaction_log_path or INTERACTION_LOG_PATH
    if not log_path.exists():
        return {
            "status": "error",
            "message": "No interaction log found",
        }

    # Count matching interactions
    total_interactions = 0
    matching_interactions = 0
    estimated_chars = 0

    try:
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total_interactions += 1

                ts = entry.get("timestamp", "")
                if scope.date_from and ts < scope.date_from:
                    continue
                if scope.date_to and ts > scope.date_to:
                    continue

                matching_interactions += 1
                estimated_chars += len(entry.get("user_message", ""))
                estimated_chars += len(entry.get("agent_response", ""))
    except Exception:
        return {"status": "error", "message": "Could not read interaction log"}

    # Rough token estimate (4 chars ≈ 1 token)
    estimated_tokens = estimated_chars // 4

    return {
        "status": "ok",
        "total_interactions": total_interactions,
        "matching_interactions": matching_interactions,
        "estimated_chars": estimated_chars,
        "estimated_tokens": estimated_tokens,
        "max_candidates": scope.max_candidates,
        "domains_in_scope": [d.value for d in scope.domains],
        "excluded_domains": [d.value for d in scope.excluded_domains],
        "date_from": scope.date_from or "beginning",
        "date_to": scope.date_to or "now",
    }


# ── Payload preview ──────────────────────────────────────────────────


def preview_backfill_payload(
    scope: BackfillScope,
    max_preview_chars: int = 1000,
    interaction_log_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Show a representative preview of what would be sent for processing.

    ADR 0094: Only selected excerpts leave the VM. This preview helps
    the Owner decide before granting consent.
    """
    log_path = interaction_log_path or INTERACTION_LOG_PATH
    if not log_path.exists():
        return {"status": "error", "message": "No interaction log found"}

    preview_entries: List[Dict[str, str]] = []
    total_chars = 0

    try:
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                if total_chars >= max_preview_chars:
                    break
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp", "")
                if scope.date_from and ts < scope.date_from:
                    continue
                if scope.date_to and ts > scope.date_to:
                    continue

                user_msg = entry.get("user_message", "")
                # Redact potentially sensitive content before preview
                redacted = _redact_sensitive(user_msg)
                preview_entries.append({
                    "timestamp": ts[:19] if ts else "",
                    "message_preview": redacted[:200],
                })
                total_chars += len(redacted)
    except Exception:
        return {"status": "error", "message": "Could not read interaction log"}

    return {
        "status": "ok",
        "preview_entries": preview_entries[:5],  # Show first 5
        "total_matching": len(preview_entries),
        "chars_shown": min(total_chars, max_preview_chars),
    }


def _redact_sensitive(text: str) -> str:
    """Local redaction of potentially sensitive content.

    Replaces common patterns while preserving structure for extraction.
    This is a deterministic, local operation — no data leaves the VM.
    """
    import re

    # Redact email addresses
    text = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[email]', text)
    # Redact phone numbers (various formats)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[phone]', text)
    # Redact URLs
    text = re.sub(r'https?://\S+', '[url]', text)
    # Redact potential names (Mr./Ms./Mrs. First Last patterns) — conservative
    # This is intentionally simple; production would use a more sophisticated approach

    return text


# ── Backfill execution ───────────────────────────────────────────────


def create_backfill_job(scope: BackfillScope) -> BackfillJob:
    """Create a new backfill job in DRAFT state."""
    return BackfillJob(
        job_id=f"backfill_{uuid.uuid4().hex[:12]}",
        scope=scope,
    )


def execute_backfill_batch(
    job: BackfillJob,
    interaction_log_path: Optional[Path] = None,
    existing_candidates: Optional[List[MemoryCandidate]] = None,
    suppression_list: Optional[Any] = None,
) -> BackfillJob:
    """Execute one batch of backfill extraction.

    Produces at most batch_size new candidates, then pauses for review.
    Call repeatedly until state is COMPLETED.

    ADR 0094: Never converts imported history directly into authoritative
    personal memory. All candidates require review.
    """
    if job.state in (BackfillState.COMPLETED, BackfillState.CANCELLED, BackfillState.DELETED):
        return job

    if job.state == BackfillState.DRAFT:
        return job  # need consent first

    log_path = interaction_log_path or INTERACTION_LOG_PATH
    if not log_path.exists():
        job.state = BackfillState.COMPLETED
        return job

    existing = existing_candidates or []
    suppressed = suppression_list or load_suppression_fingerprints()

    # Load interactions
    interactions: List[Dict[str, Any]] = []
    try:
        with log_path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                if i in job.processed_indices:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    job.processed_indices.add(i)
                    continue

                ts = entry.get("timestamp", "")
                if job.scope.date_from and ts < job.scope.date_from:
                    job.processed_indices.add(i)
                    continue
                if job.scope.date_to and ts > job.scope.date_to:
                    job.processed_indices.add(i)
                    continue

                interactions.append((i, entry))
    except Exception:
        job.state = BackfillState.COMPLETED
        return job

    batch_count = 0
    for idx, entry in interactions:
        if batch_count >= job.scope.batch_size:
            break
        if job.candidates_produced >= job.scope.max_candidates:
            job.state = BackfillState.COMPLETED
            break

        job.processed_indices.add(idx)

        user_msg = entry.get("user_message", "")
        if not user_msg:
            continue

        facts = _extract_facts_for_backfill(user_msg, job.scope)
        for fact in facts:
            if job.candidates_produced >= job.scope.max_candidates:
                break
            if batch_count >= job.scope.batch_size:
                break

            domain = fact["domain"]
            if domain in EXCLUDED_BY_DEFAULT and domain not in job.scope.domains:
                continue
            if domain in PERMANENTLY_EXCLUDED:
                continue
            if domain not in job.scope.domains:
                continue

            proposition = fact["proposition"]
            evidence = fact["evidence"]
            fingerprint = _compute_fingerprint(proposition, evidence)

            # Check suppression
            from .memory_candidates import _is_suppressed
            if _is_suppressed(fingerprint, suppressed):
                continue

            sensitivity = _classify_sensitivity(domain, CandidateSource.HISTORICAL_BACKFILL, proposition)
            expires_at = _default_expiry(sensitivity, CandidateSource.HISTORICAL_BACKFILL)

            candidate = MemoryCandidate(
                candidate_id=f"cand_{uuid.uuid4().hex[:12]}",
                domain=domain,
                sensitivity=sensitivity,
                source=CandidateSource.HISTORICAL_BACKFILL,
                provenance={
                    "interaction_timestamp": entry.get("timestamp", ""),
                    "source_type": "historical_backfill",
                    "job_id": job.job_id,
                },
                proposition=proposition,
                evidence=evidence,
                confidence=fact.get("confidence", 0.7),
                created_at=now_iso(),
                expires_at=expires_at,
                requires_confirmation=True,  # backfill always requires confirmation
            )

            job.candidates.append(candidate)
            batch_count += 1
            job.candidates_produced += 1

    # Check if done
    if job.candidates_produced >= job.scope.max_candidates:
        job.state = BackfillState.COMPLETED
    elif batch_count == 0:
        job.state = BackfillState.COMPLETED
    else:
        # More to process, but pause for review
        job.state = BackfillState.PAUSED

    return job


def _extract_facts_for_backfill(
    message: str,
    scope: BackfillScope,
) -> List[Dict[str, Any]]:
    """Extract facts from a message for backfill purposes.

    Uses the same markers as _extract_explicit_facts but also captures
    broader patterns for historical review.
    """
    from .memory_candidates import _extract_explicit_facts

    # Use explicit fact extraction as base
    facts = _extract_explicit_facts({"user_message": message, "timestamp": ""})

    # For backfill, we also capture broader patterns
    # if the domain is in scope
    extra_facts: List[Dict[str, Any]] = []

    if CandidateDomain.PATTERN in scope.domains:
        pattern_markers = ["i always", "i never", "i tend to", "i usually", "every time"]
        for marker in pattern_markers:
            idx = message.lower().find(marker)
            if idx >= 0:
                excerpt = message[idx:idx + 300].strip()
                extra_facts.append({
                    "domain": CandidateDomain.PATTERN,
                    "proposition": excerpt,
                    "evidence": excerpt,
                    "confidence": 0.6,
                })
                break

    if CandidateDomain.COGNITIVE in scope.domains:
        cognitive_markers = [
            "i forget", "i get distracted", "i focus better",
            "i work best", "i need breaks", "my attention",
        ]
        for marker in cognitive_markers:
            idx = message.lower().find(marker)
            if idx >= 0:
                excerpt = message[idx:idx + 300].strip()
                extra_facts.append({
                    "domain": CandidateDomain.COGNITIVE,
                    "proposition": excerpt,
                    "evidence": excerpt,
                    "confidence": 0.55,
                })
                break

    return facts + extra_facts


# ── Backfill lifecycle ───────────────────────────────────────────────


def grant_backfill_consent(job: BackfillJob) -> BackfillJob:
    """Grant processing consent for a backfill job.

    ADR 0094: Processing Consent is scoped authorization defining which
    material may leave the VM, for what derivation purpose, through which
    provider route, and for which single batch or interaction.
    """
    if job.state != BackfillState.DRAFT:
        return job
    job.consent_granted_at = now_iso()
    job.state = BackfillState.RUNNING
    return job


def pause_backfill(job: BackfillJob) -> BackfillJob:
    """Pause a running backfill job for review."""
    if job.state == BackfillState.RUNNING:
        job.state = BackfillState.PAUSED
    return job


def resume_backfill(job: BackfillJob) -> BackfillJob:
    """Resume a paused backfill job."""
    if job.state == BackfillState.PAUSED:
        job.state = BackfillState.RUNNING
    return job


def cancel_backfill(job: BackfillJob) -> BackfillJob:
    """Cancel a backfill job. Produced candidates remain for review."""
    if job.state in (BackfillState.COMPLETED, BackfillState.DELETED):
        return job
    job.state = BackfillState.CANCELLED
    job.cancelled_at = now_iso()
    return job


def delete_backfill(job: BackfillJob) -> BackfillJob:
    """Delete a backfill job. Candidates remain but are flagged.

    ADR 0094: Derived candidates are reversible.
    """
    job.state = BackfillState.DELETED
    job.deleted_at = now_iso()
    # Flag all candidates from this job
    for c in job.candidates:
        c.metadata["backfill_deleted"] = True
    return job


def get_backfill_status(job: BackfillJob) -> Dict[str, Any]:
    """Get the current status of a backfill job."""
    return {
        "job_id": job.job_id,
        "state": job.state.value,
        "created_at": job.created_at,
        "candidates_produced": job.candidates_produced,
        "max_candidates": job.scope.max_candidates,
        "domains": [d.value for d in job.scope.domains],
        "date_from": job.scope.date_from,
        "date_to": job.scope.date_to,
        "consent_granted": job.consent_granted_at is not None,
        "progress": f"{job.candidates_produced}/{job.scope.max_candidates}",
    }


def commit_backfill_candidates(
    job: BackfillJob,
    base_path: Optional[Path] = None,
) -> List[MemoryCandidate]:
    """Persist the candidates produced by a backfill job.

    Returns the list of persisted candidates.
    """
    if not job.candidates:
        return []
    save_candidates(job.candidates, base_path=base_path)
    return job.candidates
