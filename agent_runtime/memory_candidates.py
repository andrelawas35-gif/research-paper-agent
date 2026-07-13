"""Memory Candidate extraction — A1 from implementation-plan-regulation-pkm.md.

ADR 0094: Historical Conversations Feed a Reviewed Candidate Queue.
ADR 0076: Core Values Require Explicit Confirmation.
ADR 0129: Memory Candidates Expire and Declines Are Suppressed.
ADR 0033: Conservative Note Card Extraction.

Extracts provenance-linked Memory Candidates from interaction logs and
conversation artifacts. Candidates separate explicit facts from model
inference and never become authoritative without required confirmation.
Conflicts become review items rather than silently resolved preferences.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .paths import CANDIDATE_SIGNALS_PATH, INTERACTION_LOG_PATH, ensure_dirs, now_iso


# ── Domain types ─────────────────────────────────────────────────────


class CandidateDomain(str, Enum):
    """The domain a memory candidate belongs to."""
    PREFERENCE = "preference"
    INTEREST = "interest"
    VALUE = "value"
    PRINCIPLE = "principle"
    GOAL = "goal"
    PATTERN = "pattern"
    RELATIONSHIP = "relationship"
    COGNITIVE = "cognitive"


class CandidateSensitivity(str, Enum):
    """Sensitivity classification for a memory candidate."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    IDENTITY_SHAPING = "identity_shaping"


class CandidateSource(str, Enum):
    """How the candidate was derived."""
    EXPLICIT_STATEMENT = "explicit_statement"
    MODEL_INFERENCE = "model_inference"
    REPEATED_PATTERN = "repeated_pattern"
    HISTORICAL_BACKFILL = "historical_backfill"


class CandidateStatus(str, Enum):
    """Current review status of a memory candidate."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    DEFERRED = "deferred"
    DECLINED = "declined"
    SUPPRESSED = "suppressed"
    EXPIRED = "expired"


# ── Schemas ──────────────────────────────────────────────────────────


@dataclass
class SuppressionFingerprint:
    """Minimal non-semantic identifier for a declined candidate.

    ADR 0129: Retained after decline so the same unsupported proposal
    is not repeatedly generated. Cannot be retrieved as personal context.
    May be bypassed only by materially new, displayed evidence.
    """

    fingerprint: str  # SHA-256 of (candidate_type, source_excerpt[:200])
    candidate_type: str
    declined_at: str
    reason: str = ""


@dataclass
class MemoryCandidate:
    """A provenance-linked proposition that may become a durable record.

    ADR 0094, ADR 0076: Never authoritative without required confirmation.
    Conflicts become review items, not silently resolved preferences.
    """

    candidate_id: str
    domain: CandidateDomain
    sensitivity: CandidateSensitivity
    source: CandidateSource
    provenance: Dict[str, Any]  # source conversation IDs, timestamps, excerpts
    proposition: str  # what is being proposed as durable memory
    evidence: str  # the excerpt or summary that supports the proposition
    confidence: float  # 0.0–1.0
    created_at: str
    expires_at: str
    requires_confirmation: bool  # True for sensitive, identity-shaping, or conflicting
    conflicts_with: List[str] = field(default_factory=list)  # IDs of conflicting candidates
    status: CandidateStatus = CandidateStatus.PENDING
    suppression_fingerprint: Optional[str] = None
    deferred_until: Optional[str] = None
    edited_proposition: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Extraction ───────────────────────────────────────────────────────


def _compute_fingerprint(proposition: str, evidence: str) -> str:
    """Compute a suppression fingerprint from proposition and evidence."""
    material = f"{proposition[:200]}|{evidence[:200]}"
    return hashlib.sha256(material.encode()).hexdigest()


def _default_expiry(sensitivity: CandidateSensitivity, source: CandidateSource) -> str:
    """Compute default expiry based on sensitivity and source.

    ADR 0129:
    - Weak inferred candidates: 30 days
    - Explicit Owner statements: 90 days
    - Sensitive/identity-shaping: 30 days unless deferred
    """
    now = datetime.now(timezone.utc)
    if sensitivity in (CandidateSensitivity.HIGH, CandidateSensitivity.IDENTITY_SHAPING):
        days = 30
    elif source == CandidateSource.MODEL_INFERENCE:
        days = 30
    else:
        days = 90
    return (now + timedelta(days=days)).isoformat()


def _classify_sensitivity(
    domain: CandidateDomain,
    source: CandidateSource,
    proposition: str,
) -> CandidateSensitivity:
    """Classify a candidate's sensitivity based on domain, source, and content.

    Identity-shaping: values, principles, goals from any source.
    High: relationship content, cognitive patterns.
    Medium: preference and interest from explicit statement.
    Low: preference and interest from model inference.
    """
    if domain in (CandidateDomain.VALUE, CandidateDomain.PRINCIPLE, CandidateDomain.GOAL):
        return CandidateSensitivity.IDENTITY_SHAPING
    if domain == CandidateDomain.RELATIONSHIP:
        return CandidateSensitivity.HIGH
    if domain == CandidateDomain.COGNITIVE:
        return CandidateSensitivity.HIGH
    if source == CandidateSource.MODEL_INFERENCE:
        return CandidateSensitivity.LOW
    if source == CandidateSource.EXPLICIT_STATEMENT:
        return CandidateSensitivity.MEDIUM
    return CandidateSensitivity.MEDIUM


def _requires_confirmation(sensitivity: CandidateSensitivity, has_conflicts: bool) -> bool:
    """Determine if a candidate requires explicit Owner confirmation.

    ADR 0076: Core values, identity-shaping, and conflicting candidates
    always require confirmation. Low-sensitivity inference without
    conflicts can be auto-accepted.
    """
    if has_conflicts:
        return True
    if sensitivity in (CandidateSensitivity.HIGH, CandidateSensitivity.IDENTITY_SHAPING):
        return True
    if sensitivity == CandidateSensitivity.MEDIUM:
        return True  # explicit statements still need confirmation
    return False  # low-sensitivity inference can auto-accept


def _detect_conflicts(
    new_candidate: MemoryCandidate,
    existing_candidates: List[MemoryCandidate],
) -> List[str]:
    """Detect conflicting candidates.

    A conflict exists when two candidates in the same domain make
    contradictory propositions. Returns IDs of conflicting candidates.
    """
    conflicts: List[str] = []
    for existing in existing_candidates:
        if existing.candidate_id == new_candidate.candidate_id:
            continue
        if existing.domain != new_candidate.domain:
            continue
        if existing.status in (CandidateStatus.DECLINED, CandidateStatus.SUPPRESSED, CandidateStatus.EXPIRED):
            continue
        # Simple conflict detection: same domain, both have medium+ confidence
        if existing.confidence >= 0.5 and new_candidate.confidence >= 0.5:
            conflicts.append(existing.candidate_id)
    return conflicts


def _is_suppressed(fingerprint: str, suppression_list: List[SuppressionFingerprint]) -> bool:
    """Check if a fingerprint is in the suppression list."""
    return any(s.fingerprint == fingerprint for s in suppression_list)


def _extract_explicit_facts(interaction: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract explicit facts from user statements in an interaction.

    Returns a list of candidate proposals based on explicit language.
    Does NOT use model inference — this is deterministic extraction.
    """
    candidates: List[Dict[str, Any]] = []
    message = interaction.get("user_message", "")

    # Preference statements
    preference_markers = [
        "i prefer", "i like", "i want", "i need",
        "i don't like", "i dislike", "i hate",
        "my preference", "i'd rather",
    ]
    for marker in preference_markers:
        idx = message.lower().find(marker)
        if idx >= 0:
            excerpt = message[idx:idx + 300].strip()
            candidates.append({
                "domain": CandidateDomain.PREFERENCE,
                "source": CandidateSource.EXPLICIT_STATEMENT,
                "proposition": excerpt,
                "evidence": excerpt,
                "confidence": 0.85,
            })
            break  # one preference per interaction

    # Interest statements
    interest_markers = [
        "i'm interested in", "i am interested in",
        "i'm curious about", "i study", "i research",
        "i'm learning", "i am learning",
    ]
    for marker in interest_markers:
        idx = message.lower().find(marker)
        if idx >= 0:
            excerpt = message[idx:idx + 300].strip()
            candidates.append({
                "domain": CandidateDomain.INTEREST,
                "source": CandidateSource.EXPLICIT_STATEMENT,
                "proposition": excerpt,
                "evidence": excerpt,
                "confidence": 0.8,
            })
            break

    # Value statements
    value_markers = [
        "i value", "i believe in", "what matters to me",
        "my core value", "important to me is",
    ]
    for marker in value_markers:
        idx = message.lower().find(marker)
        if idx >= 0:
            excerpt = message[idx:idx + 300].strip()
            candidates.append({
                "domain": CandidateDomain.VALUE,
                "source": CandidateSource.EXPLICIT_STATEMENT,
                "proposition": excerpt,
                "evidence": excerpt,
                "confidence": 0.7,
            })
            break

    return candidates


def extract_candidates(
    interaction_log_path: Optional[Path] = None,
    existing_candidates: Optional[List[MemoryCandidate]] = None,
    suppression_list: Optional[List[SuppressionFingerprint]] = None,
    *,
    max_new: int = 10,
) -> List[MemoryCandidate]:
    """Extract memory candidates from the interaction log.

    Args:
        interaction_log_path: Path to interaction log. Defaults to standard path.
        existing_candidates: Already-extracted candidates for conflict detection.
        suppression_list: Fingerprints of previously declined candidates.
        max_new: Maximum number of new candidates to extract.

    Returns:
        List of new MemoryCandidate objects (not yet persisted).

    Candidates never become authoritative without required confirmation.
    Conflicts become review items with conflicts_with populated.
    Previously-suppressed candidates are not re-generated.
    """
    log_path = interaction_log_path or INTERACTION_LOG_PATH
    existing = existing_candidates or []
    suppressed = suppression_list or []

    if not log_path.exists():
        return []

    # Load recent interactions (last 500 lines)
    interactions: List[Dict[str, Any]] = []
    try:
        with log_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-500:]:
                if line.strip():
                    try:
                        interactions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return []

    new_candidates: List[MemoryCandidate] = []
    seen_fingerprints: Set[str] = set()

    for interaction in interactions:
        if len(new_candidates) >= max_new:
            break

        facts = _extract_explicit_facts(interaction)
        for fact in facts:
            if len(new_candidates) >= max_new:
                break

            proposition = fact["proposition"]
            evidence = fact["evidence"]
            fingerprint = _compute_fingerprint(proposition, evidence)

            # Skip if already suppressed
            if _is_suppressed(fingerprint, suppressed):
                continue
            # Skip if fingerprint already seen in this batch
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)

            domain = fact["domain"]
            source = fact["source"]
            sensitivity = _classify_sensitivity(domain, source, proposition)
            expires_at = _default_expiry(sensitivity, source)

            candidate = MemoryCandidate(
                candidate_id=f"cand_{uuid.uuid4().hex[:12]}",
                domain=domain,
                sensitivity=sensitivity,
                source=source,
                provenance={
                    "interaction_timestamp": interaction.get("timestamp", ""),
                    "source_type": "interaction_log",
                },
                proposition=proposition,
                evidence=evidence,
                confidence=fact["confidence"],
                created_at=now_iso(),
                expires_at=expires_at,
                requires_confirmation=False,  # computed below
            )

            conflicts = _detect_conflicts(candidate, existing + new_candidates)
            candidate.conflicts_with = conflicts
            candidate.requires_confirmation = _requires_confirmation(sensitivity, len(conflicts) > 0)

            new_candidates.append(candidate)

    return new_candidates


# ── Persistence ──────────────────────────────────────────────────────


def _candidates_path() -> Path:
    """Path to the persisted candidates file."""
    return Path(str(CANDIDATE_SIGNALS_PATH).replace("candidate_signals", "memory_candidates"))


def _suppression_path() -> Path:
    """Path to the suppression fingerprint file."""
    return Path(str(CANDIDATE_SIGNALS_PATH).replace("candidate_signals", "suppression_fingerprints"))


def save_candidates(candidates: List[MemoryCandidate], base_path: Optional[Path] = None) -> None:
    """Persist memory candidates to JSONL file."""
    ensure_dirs()
    path = base_path or _candidates_path()
    with path.open("a", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(_candidate_to_dict(c)) + "\n")


def load_candidates(base_path: Optional[Path] = None) -> List[MemoryCandidate]:
    """Load all persisted memory candidates."""
    path = base_path or _candidates_path()
    if not path.exists():
        return []
    candidates: List[MemoryCandidate] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    candidates.append(_dict_to_candidate(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
    return candidates


def save_suppression_fingerprints(
    fingerprints: List[SuppressionFingerprint],
    base_path: Optional[Path] = None,
) -> None:
    """Persist suppression fingerprints."""
    ensure_dirs()
    path = base_path or _suppression_path()
    with path.open("a", encoding="utf-8") as f:
        for fp in fingerprints:
            f.write(json.dumps({
                "fingerprint": fp.fingerprint,
                "candidate_type": fp.candidate_type,
                "declined_at": fp.declined_at,
                "reason": fp.reason,
            }) + "\n")


def load_suppression_fingerprints(base_path: Optional[Path] = None) -> List[SuppressionFingerprint]:
    """Load all suppression fingerprints."""
    path = base_path or _suppression_path()
    if not path.exists():
        return []
    fingerprints: List[SuppressionFingerprint] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    fingerprints.append(SuppressionFingerprint(
                        fingerprint=data["fingerprint"],
                        candidate_type=data.get("candidate_type", ""),
                        declined_at=data.get("declined_at", ""),
                        reason=data.get("reason", ""),
                    ))
                except (json.JSONDecodeError, KeyError):
                    continue
    return fingerprints


# ── Serialization helpers ────────────────────────────────────────────


def _candidate_to_dict(c: MemoryCandidate) -> Dict[str, Any]:
    """Serialize a MemoryCandidate to a plain dict for JSON storage."""
    return {
        "candidate_id": c.candidate_id,
        "domain": c.domain.value,
        "sensitivity": c.sensitivity.value,
        "source": c.source.value,
        "provenance": c.provenance,
        "proposition": c.proposition,
        "evidence": c.evidence,
        "confidence": c.confidence,
        "created_at": c.created_at,
        "expires_at": c.expires_at,
        "requires_confirmation": c.requires_confirmation,
        "conflicts_with": c.conflicts_with,
        "status": c.status.value,
        "suppression_fingerprint": c.suppression_fingerprint,
        "deferred_until": c.deferred_until,
        "edited_proposition": c.edited_proposition,
        "metadata": c.metadata,
    }


def _dict_to_candidate(d: Dict[str, Any]) -> MemoryCandidate:
    """Deserialize a dict to a MemoryCandidate."""
    return MemoryCandidate(
        candidate_id=d["candidate_id"],
        domain=CandidateDomain(d["domain"]),
        sensitivity=CandidateSensitivity(d["sensitivity"]),
        source=CandidateSource(d["source"]),
        provenance=d.get("provenance", {}),
        proposition=d.get("proposition", ""),
        evidence=d.get("evidence", ""),
        confidence=float(d.get("confidence", 0.0)),
        created_at=d.get("created_at", ""),
        expires_at=d.get("expires_at", ""),
        requires_confirmation=bool(d.get("requires_confirmation", True)),
        conflicts_with=d.get("conflicts_with", []),
        status=CandidateStatus(d.get("status", "pending")),
        suppression_fingerprint=d.get("suppression_fingerprint"),
        deferred_until=d.get("deferred_until"),
        edited_proposition=d.get("edited_proposition"),
        metadata=d.get("metadata", {}),
    )


# ── Expiry ───────────────────────────────────────────────────────────


def expire_stale_candidates(
    candidates: Optional[List[MemoryCandidate]] = None,
    base_path: Optional[Path] = None,
) -> List[MemoryCandidate]:
    """Mark expired candidates as expired. Returns updated list.

    ADR 0129: Expired candidates leave active review and retrieval
    without affecting accepted durable records.
    """
    cands = candidates if candidates is not None else load_candidates(base_path)
    now = datetime.now(timezone.utc)
    updated: List[MemoryCandidate] = []
    changed = False

    for c in cands:
        if c.status == CandidateStatus.PENDING:
            try:
                expires = datetime.fromisoformat(c.expires_at)
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if now > expires:
                    c.status = CandidateStatus.EXPIRED
                    changed = True
            except (ValueError, TypeError):
                pass
        updated.append(c)

    if changed and base_path is None:
        # Rewrite file with updated statuses
        path = _candidates_path()
        with path.open("w", encoding="utf-8") as f:
            for c in updated:
                f.write(json.dumps(_candidate_to_dict(c)) + "\n")

    return updated
