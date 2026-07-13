"""Store boundaries — F2 from implementation-plan-regulation-pkm.md.

ADR 0091: New Personal Stores Share an Event Envelope.
ADR 0092: Encrypt Regulation Data at Rest from the First Slice.
ADR 0093: Regulation Retention Is Tiered and Deletion Is Cryptographic.
ADR 0100: Model Proposes; Code Authorizes and Persists.

Three explicit repositories with typed interfaces:
- OperationalStore: runtime config, session metadata, audit logs
- GeneralPKMStore: papers, notes, concepts, user profile, relationships
- RegulationStore: regulation sessions, rules, safety events, patterns

Cross-store access requires an explicit authorized seam. Regulation
records MUST NOT enter general retrieval.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set

from .event_envelope import Domain, EventEnvelope, EventStore, Sensitivity

# ── Repository interface ─────────────────────────────────────────────


class Repository(ABC):
    """Abstract typed repository backed by an EventStore.

    Each repository owns one domain. Cross-domain access must go
    through an explicit authorized seam.
    """

    domain: Domain  # set by subclass

    @abstractmethod
    def append(self, envelope: EventEnvelope) -> None:
        """Append a validated event to this store."""
        ...

    @abstractmethod
    def replay(self) -> List[EventEnvelope]:
        """Replay all events in this store."""
        ...

    @abstractmethod
    def event_ids(self) -> Set[str]:
        """Return all known event IDs in this store."""
        ...


# ── Concrete stores ──────────────────────────────────────────────────


@dataclass
class OperationalStore(Repository):
    """Operational data: runtime config, session metadata, audit logs.

    Domain: Domain.OPERATIONAL
    Sensitivity: typically INTERNAL or CONFIDENTIAL
    """

    domain: Domain = field(default=Domain.OPERATIONAL, init=False)
    _store: EventStore = field(init=False)

    def __post_init__(self) -> None:
        self._store = EventStore(Path("data/operational/events.jsonl"))

    def set_path(self, path: Path) -> None:
        """Override the store path (for testing)."""
        self._store = EventStore(path)

    def append(self, envelope: EventEnvelope) -> None:
        if envelope.domain != Domain.OPERATIONAL:
            raise StoreBoundaryError(
                f"Cannot append {envelope.domain.value} event to OperationalStore"
            )
        self._store.append(envelope)

    def replay(self) -> List[EventEnvelope]:
        return self._store.replay()

    def event_ids(self) -> Set[str]:
        return self._store.event_ids()


@dataclass
class GeneralPKMStore(Repository):
    """General PKM data: papers, notes, concepts, user profile, relationships.

    Domain: Domain.GENERAL_PKM
    Sensitivity: typically INTERNAL or CONFIDENTIAL

    MUST NOT import or reference the RegulationStore.
    """

    domain: Domain = field(default=Domain.GENERAL_PKM, init=False)
    _store: EventStore = field(init=False)

    def __post_init__(self) -> None:
        self._store = EventStore(Path("data/general_pkm/events.jsonl"))

    def set_path(self, path: Path) -> None:
        self._store = EventStore(path)

    def append(self, envelope: EventEnvelope) -> None:
        if envelope.domain == Domain.REGULATION:
            raise StoreBoundaryError(
                "Regulation events cannot enter GeneralPKMStore"
            )
        if envelope.domain != Domain.GENERAL_PKM:
            raise StoreBoundaryError(
                f"Cannot append {envelope.domain.value} event to GeneralPKMStore"
            )
        self._store.append(envelope)

    def replay(self) -> List[EventEnvelope]:
        return self._store.replay()

    def event_ids(self) -> Set[str]:
        return self._store.event_ids()


@dataclass
class RegulationStore(Repository):
    """Regulation data: trigger sessions, rules, safety events, patterns.

    Domain: Domain.REGULATION
    Sensitivity: RESTRICTED

    Encrypted at rest (F3). Contents MUST NOT be accessible from
    GeneralPKMStore or general retrieval.
    """

    domain: Domain = field(default=Domain.REGULATION, init=False)
    _store: EventStore = field(init=False)

    def __post_init__(self) -> None:
        self._store = EventStore(Path("data/regulation/events.jsonl"))

    def set_path(self, path: Path) -> None:
        self._store = EventStore(path)

    def append(self, envelope: EventEnvelope) -> None:
        if envelope.domain != Domain.REGULATION:
            raise StoreBoundaryError(
                f"Cannot append {envelope.domain.value} event to RegulationStore"
            )
        self._store.append(envelope)

    def replay(self) -> List[EventEnvelope]:
        return self._store.replay()

    def event_ids(self) -> Set[str]:
        return self._store.event_ids()


# ── Authorized cross-store seam ──────────────────────────────────────


class StoreBoundaryError(ValueError):
    """Raised when a store boundary is violated."""


@dataclass
class StoreRegistry:
    """Central registry of all stores with authorized cross-store access.

    Any cross-store read or write must go through an explicit method
    on this registry, which enforces authorization rules.
    """

    operational: OperationalStore = field(default_factory=OperationalStore)
    general_pkm: GeneralPKMStore = field(default_factory=GeneralPKMStore)
    regulation: RegulationStore = field(default_factory=RegulationStore)

    def append(self, envelope: EventEnvelope) -> None:
        """Route an envelope to the correct store by domain."""
        store = self._store_for(envelope.domain)
        store.append(envelope)

    def _store_for(self, domain: Domain) -> Repository:
        if domain == Domain.OPERATIONAL:
            return self.operational
        elif domain == Domain.GENERAL_PKM:
            return self.general_pkm
        elif domain == Domain.REGULATION:
            return self.regulation
        elif domain == Domain.VALUES:
            # Values write to general_pkm for now; may split later
            return self.general_pkm
        else:
            raise StoreBoundaryError(f"Unknown domain: {domain}")

    # ── Authorized cross-store reads ──────────────────────────────────

    def read_general_for_regulation_context(
        self, confirmed_rule_ids: List[str]
    ) -> List[dict[str, Any]]:
        """Authorized seam: Regulation may read confirmed personal rules
        from GeneralPKM for context assembly. Returns only rule payloads
        with confirmed state — no raw history.
        """
        results: List[dict[str, Any]] = []
        for event in self.general_pkm.replay():
            if event.event_type == "personal_rule_confirmed":
                rule = event.payload
                if rule.get("rule_id") in confirmed_rule_ids:
                    # Strip provenance and internal fields for Regulation context
                    results.append({
                        "rule_id": rule.get("rule_id"),
                        "label": rule.get("label"),
                        "strength": rule.get("strength"),
                        "text": rule.get("text"),
                    })
        return results

    def regulation_store_is_empty(self) -> bool:
        """Check if regulation store has any events (for health checks)."""
        return len(self.regulation.replay()) == 0


# ── Retrieval guard ──────────────────────────────────────────────────


class RetrievalGuard:
    """Ensures Regulation records cannot enter general retrieval.

    This is a code-enforced boundary, not a model-enforced one.
    Before any retrieval query assembles results, it must pass
    through this guard.
    """

    @staticmethod
    def filter_regulation(
        candidates: List[dict[str, Any]],
    ) -> List[dict[str, Any]]:
        """Remove any candidate with domain=regulation or sensitivity=restricted."""
        return [
            c for c in candidates
            if c.get("domain") != "regulation"
            and c.get("sensitivity") != "restricted"
        ]

    @staticmethod
    def assert_no_regulation(candidates: List[dict[str, Any]]) -> None:
        """Raise if any candidate is from the regulation domain."""
        for c in candidates:
            if c.get("domain") == "regulation":
                raise StoreBoundaryError(
                    "Regulation record attempted to enter general retrieval"
                )
