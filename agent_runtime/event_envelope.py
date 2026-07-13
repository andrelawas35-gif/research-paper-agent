"""Shared append-only event envelope — F1 from implementation-plan-regulation-pkm.md.

ADR 0091: New Personal Stores Share an Event Envelope.

Every personal-data module writes through this envelope. It provides:
- Unique event IDs (UUID7 for time-sortable uniqueness)
- Owner, domain, event type, schema version, timestamp
- Sensitivity classification, provenance metadata
- Payload checksum (SHA-256)
- Optional correlation ID for linked events
- Atomic JSONL append with deterministic replay

Domain modules own their payload schemas, transitions, reducers, and
corrections. This module only validates the envelope shape — never the
domain meaning of the payload.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

# ── Domain type ──────────────────────────────────────────────────────


class Domain(str, Enum):
    OPERATIONAL = "operational"
    GENERAL_PKM = "general_pkm"
    REGULATION = "regulation"
    VALUES = "values"


class Sensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# ── Envelope Dataclass ───────────────────────────────────────────────


@dataclass(frozen=True)
class EventEnvelope:
    """Immutable append-only event with checksum and provenance."""

    event_id: str
    owner_id: str
    domain: Domain
    event_type: str
    schema_version: int
    timestamp: str  # ISO 8601 UTC
    sensitivity: Sensitivity
    provenance: dict[str, Any]
    payload: dict[str, Any]
    payload_checksum: str  # SHA-256 hex digest of canonical JSON payload
    correlation_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        owner_id: str,
        domain: Domain,
        event_type: str,
        schema_version: int,
        sensitivity: Sensitivity,
        provenance: dict[str, Any],
        payload: dict[str, Any],
        correlation_id: str | None = None,
        event_id: str | None = None,
        timestamp: str | None = None,
    ) -> EventEnvelope:
        """Factory: build a validated envelope.

        event_id and timestamp default to UUID7 and now-UTC for
        determinism in tests when injected.
        """
        eid = event_id or _uuid7()
        ts = timestamp or _now_iso()
        payload_json = _canonical_json(payload)
        checksum = _sha256_hex(payload_json)

        return cls(
            event_id=eid,
            owner_id=owner_id,
            domain=domain,
            event_type=event_type,
            schema_version=schema_version,
            timestamp=ts,
            sensitivity=sensitivity,
            provenance=provenance,
            payload=payload,
            payload_checksum=checksum,
            correlation_id=correlation_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "owner_id": self.owner_id,
            "domain": self.domain.value,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "sensitivity": self.sensitivity.value,
            "provenance": self.provenance,
            "payload": self.payload,
            "payload_checksum": self.payload_checksum,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventEnvelope:
        """Deserialize and validate from JSONL row dict."""
        errors = _validate_envelope_shape(data)
        if errors:
            raise MalformedEnvelopeError(errors)

        # Recompute checksum from payload
        expected = _sha256_hex(_canonical_json(data["payload"]))
        if data.get("payload_checksum") != expected:
            raise MalformedEnvelopeError(
                [f"payload_checksum mismatch: expected {expected}, "
                 f"got {data.get('payload_checksum')}"]
            )

        return cls(
            event_id=data["event_id"],
            owner_id=data["owner_id"],
            domain=Domain(data["domain"]),
            event_type=data["event_type"],
            schema_version=data["schema_version"],
            timestamp=data["timestamp"],
            sensitivity=Sensitivity(data["sensitivity"]),
            provenance=data["provenance"],
            payload=data["payload"],
            payload_checksum=data["payload_checksum"],
            correlation_id=data.get("correlation_id"),
        )


# ── Errors ───────────────────────────────────────────────────────────


class MalformedEnvelopeError(ValueError):
    """Raised when an envelope fails shape validation or checksum."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


# ── Append & Replay ──────────────────────────────────────────────────


class EventStore:
    """Append-only JSONL event store with deterministic replay.

    Thread-safe for append; replay is a read-only snapshot.
    """

    def __init__(self, file_path: Path) -> None:
        self._path = file_path

    def append(self, envelope: EventEnvelope) -> None:
        """Atomically append one event.

        Uses os.fsync for durability on the current (single-VM) target.
        """
        line = json.dumps(envelope.to_dict(), ensure_ascii=False) + "\n"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def replay(self) -> list[EventEnvelope]:
        """Replay all events deterministically."""
        events: list[EventEnvelope] = []
        if not self._path.exists():
            return events
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                events.append(EventEnvelope.from_dict(json.loads(stripped)))
        return events

    def replay_by_domain(self, domain: Domain) -> list[EventEnvelope]:
        """Replay only events for a specific domain."""
        return [e for e in self.replay() if e.domain == domain]

    def event_ids(self) -> set[str]:
        """Return all known event IDs (for uniqueness checks)."""
        return {e.event_id for e in self.replay()}


# ── Validation ───────────────────────────────────────────────────────


def _validate_envelope_shape(data: dict[str, Any]) -> list[str]:
    """Return list of validation errors; empty list = valid."""
    errors: list[str] = []

    for required_field in (
        "event_id", "owner_id", "domain", "event_type",
        "schema_version", "timestamp", "sensitivity", "provenance",
        "payload", "payload_checksum",
    ):
        if required_field not in data:
            errors.append(f"missing required field: {required_field}")

    if errors:
        return errors

    # event_id must be a non-empty string
    if not isinstance(data["event_id"], str) or not data["event_id"]:
        errors.append("event_id must be a non-empty string")
    # uniqueness checked at store level, not here

    # owner_id
    if not isinstance(data["owner_id"], str) or not data["owner_id"]:
        errors.append("owner_id must be a non-empty string")

    # domain
    try:
        Domain(data["domain"])
    except ValueError:
        errors.append(
            f"domain must be one of {[d.value for d in Domain]}, "
            f"got: {data['domain']!r}"
        )

    # event_type
    if not isinstance(data["event_type"], str) or not data["event_type"]:
        errors.append("event_type must be a non-empty string")

    # schema_version
    if not isinstance(data["schema_version"], int) or data["schema_version"] < 1:
        errors.append("schema_version must be a positive integer")

    # timestamp
    ts = data["timestamp"]
    if not isinstance(ts, str):
        errors.append("timestamp must be a string")
    else:
        try:
            parsed = datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            errors.append("timestamp must be an ISO 8601 string")
        else:
            if parsed.tzinfo is None:
                errors.append("timestamp must include timezone")

    # sensitivity
    try:
        Sensitivity(data["sensitivity"])
    except ValueError:
        errors.append(
            f"sensitivity must be one of {[s.value for s in Sensitivity]}, "
            f"got: {data['sensitivity']!r}"
        )

    # provenance must be a dict
    if not isinstance(data["provenance"], dict):
        errors.append("provenance must be a dict")

    # payload must be a dict
    if not isinstance(data["payload"], dict):
        errors.append("payload must be a dict")

    # payload_checksum
    if not isinstance(data["payload_checksum"], str) or not data["payload_checksum"]:
        errors.append("payload_checksum must be a non-empty string")

    # correlation_id (optional)
    cid = data.get("correlation_id")
    if cid is not None and (not isinstance(cid, str) or not cid):
        errors.append("correlation_id must be a non-empty string or None")

    return errors


# ── Helpers ──────────────────────────────────────────────────────────


def _canonical_json(obj: Any) -> str:
    """Serialize to canonical JSON with sorted keys."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256_hex(data: str) -> str:
    """SHA-256 hex digest of a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _uuid7() -> str:
    """Generate a time-sortable UUID7 string."""
    # UUID7: Unix ms timestamp in first 48 bits, then version/variant/random
    ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rand = os.urandom(10)
    # Build UUID7 bytes: 6 bytes timestamp + 10 bytes random
    ts_bytes = ts_ms.to_bytes(6, "big")
    combined = ts_bytes + rand
    # Set version (7) in byte 6
    combined = combined[:6] + bytes([(combined[6] & 0x0F) | 0x70]) + combined[7:]
    # Set variant (10xx) in byte 8
    combined = combined[:8] + bytes([(combined[8] & 0x3F) | 0x80]) + combined[9:]
    return str(uuid.UUID(bytes=combined))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
