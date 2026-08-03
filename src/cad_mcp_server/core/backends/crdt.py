"""Lightweight LWW-Map CRDT for collaborative CAD documents.

Spike 3 prototype (M2 pre-research): validates CRDT convergence for
concurrent document edits (geometry / layers / assembly tree) using a
pure-Python **Last-Writer-Wins (LWW) Map** with per-key registers plus
an **Observed-Remove Set (OR-Set)** for tombstones.

Why LWW-Map: a CAD document is a collection of keyed registers —
``entities`` (entity_id → record), ``layers`` (name → definition),
``variables``, ``constraints``, ``styles``. Each register holds a
JSON-serialisable value; the winner of a concurrent write is decided by
a total order on ``(timestamp, replica_id, op_sequence)``. This is the
simplest CRDT that converges deterministically for register semantics,
which is exactly what CAD edits need (no merge conflicts on disjoint
keys; the same key written concurrently resolves by recency).

OR-set tombstone tracking lets a delete on one replica suppress an
add/update of an older operation without needing central coordination.

Convergence guarantee (the Spike 3 acceptance): after an arbitrary
sequence of concurrent operations applied in different orders on two or
more replicas, merging every replica pairwise yields the identical final
state (merge is commutative, associative and idempotent). Consistency is
checked under randomized concurrent edits in the tests.

This is the **interim self-built** option. The Phase 9 fallback is
WebSocket full-sync + server-side lock if CRDT convergence proves
insufficient. If the production phase adopts a mature library
(pycrdt/Yjs), this module stays as the zero-dependency reference.
"""

from __future__ import annotations

import builtins
import json
import uuid
from datetime import UTC, datetime
from typing import Any

#: Reserved marker key used by OR-set tombstones.
_TOMBSTONE = "__crdt_tombstone__"


def _now() -> str:
    """Return a sortable UTC timestamp (microsecond precision)."""
    return datetime.now(UTC).isoformat()


class LWWElement:
    """A single register entry: ``(value, timestamp, replica, seq)``."""

    __slots__ = ("replica", "seq", "timestamp", "value")

    def __init__(
        self,
        value: Any,
        timestamp: str,
        replica: str,
        seq: int,
    ) -> None:
        """Initialize a register element."""
        self.value = value
        self.timestamp = timestamp
        self.replica = replica
        self.seq = seq

    def dominates(self, other: LWWElement) -> bool:
        """Return True if this element is newer in the total order."""
        if self.timestamp != other.timestamp:
            return self.timestamp > other.timestamp
        if self.replica != other.replica:
            return self.replica > other.replica
        return self.seq > other.seq

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "value": self.value,
            "ts": self.timestamp,
            "replica": self.replica,
            "seq": self.seq,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LWWElement:
        """Reconstruct an element from a serialized dict."""
        return cls(
            value=data["value"],
            timestamp=str(data["ts"]),
            replica=str(data["replica"]),
            seq=int(data["seq"]),
        )


class LWWMap:
    """Last-Writer-Wins Map CRDT with OR-set tombstone semantics.

    Each key holds a single :class:`LWWElement` register. ``set`` records
    the operation metadata; ``delete`` writes a tombstone. Merging keeps,
    per key, the element that dominates (or a delete tombstone). Because
    the dominance order is a total order, concurrent replicas converge.
    """

    def __init__(self, replica_id: str | None = None) -> None:
        """Initialize a replica-local map."""
        self.replica = replica_id or f"replica_{uuid.uuid4().hex[:8]}"
        self._registers: dict[str, LWWElement] = {}
        self._tombstones: dict[str, LWWElement] = {}
        self._seq = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    # ------------------------------------------------------------------
    # Local operations
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any) -> LWWElement:
        """Write ``value`` for ``key`` (LWW register)."""
        element = LWWElement(value, _now(), self.replica, self._next_seq())
        self._registers[key] = element
        return element

    def delete(self, key: str) -> bool:
        """Delete ``key`` (records a tombstone). Return False if absent."""
        if key not in self._registers:
            return False
        tombstone = LWWElement(_TOMBSTONE, _now(), self.replica, self._next_seq())
        self._tombstones[key] = tombstone
        self._registers.pop(key, None)
        return True

    def get(self, key: str) -> Any:
        """Return the value for ``key`` or ``None`` if deleted/absent."""
        element = self._registers.get(key)
        return None if element is None else element.value

    def keys(self) -> builtins.set[str]:
        """Return the live (non-deleted) keys."""
        return builtins.set(self._registers)

    def items(self) -> dict[str, Any]:
        """Return a shallow copy of the live key → value mapping."""
        return {key: element.value for key, element in self._registers.items()}

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def merge(self, other: LWWMap) -> None:
        """Merge another replica's state into this one (convergent)."""
        # Incorporate tombstones first so a newer delete suppresses older
        # registers and vice versa.
        for key, tombstone in other._tombstones.items():
            existing = self._tombstones.get(key)
            if existing is None or tombstone.dominates(existing):
                self._tombstones[key] = tombstone
            if key in self._registers:
                register = self._registers[key]
                if tombstone.dominates(register):
                    del self._registers[key]
        for key, element in other._registers.items():
            existing_tombstone = self._tombstones.get(key)
            if existing_tombstone is not None and existing_tombstone.dominates(element):
                continue  # a newer delete wins over this older register
            existing = self._registers.get(key)
            if existing is None or element.dominates(existing):
                self._registers[key] = element

    def snapshot(self) -> dict[str, Any]:
        """Serialize the full state for replication/durability."""
        return {
            "registers": {key: element.to_dict() for key, element in self._registers.items()},
            "tombstones": {key: element.to_dict() for key, element in self._tombstones.items()},
        }

    def load(self, snapshot: dict[str, Any]) -> None:
        """Restore state from a :meth:`snapshot` dict."""
        self._registers = {
            key: LWWElement.from_dict(data) for key, data in snapshot.get("registers", {}).items()
        }
        self._tombstones = {
            key: LWWElement.from_dict(data) for key, data in snapshot.get("tombstones", {}).items()
        }

    # ------------------------------------------------------------------
    # Convenience for CAD document collection
    # ------------------------------------------------------------------

    @classmethod
    def from_items(cls, mapping: dict[str, Any], replica_id: str | None = None) -> LWWMap:
        """Build a map seeded with ``mapping`` (same timestamp per key)."""
        crdt = cls(replica_id)
        for key, value in mapping.items():
            crdt.set(key, value)
        return crdt


def replicas_converge(replicas: list[LWWMap]) -> bool:
    """Return True if all replicas hold identical live state.

    Used by the Spike 3 acceptance check: after arbitrary concurrent
    edits and a full pairwise merge, every replica's live map must match.
    """
    if not replicas:
        return True
    reference = replicas[0].snapshot()
    return all(replica.snapshot() == reference for replica in replicas[1:])


def replicate_via_json(source: LWWMap) -> LWWMap:
    """Round-trip a map through JSON to simulate a network transport."""
    data = source.snapshot()
    text = json.dumps(data)
    replica = LWWMap()
    replica.load(json.loads(text))
    return replica
