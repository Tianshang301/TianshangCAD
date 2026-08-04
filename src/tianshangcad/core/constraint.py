"""Geometric constraints between entities.

A document can hold a set of geometric constraints (parallel, perpendicular,
tangent, coincident, ...) over its line/circle entities. Constraints are
solved numerically against the current document geometry; the solver writes
updated geometry back through the entity manager.
"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from tianshangcad.utils.errors import ConstraintError


class ConstraintType(enum.StrEnum):
    """Supported geometric constraint kinds."""

    FIXED = "fixed"  # entity is anchored, not moved by the solver
    COINCIDENT = "coincident"  # reference points coincide
    PARALLEL = "parallel"  # two lines are parallel
    PERPENDICULAR = "perpendicular"  # two lines are perpendicular
    TANGENT = "tangent"  # line and circle are tangent
    ON_LINE = "on_line"  # point lies on a line
    MIDPOINT = "midpoint"  # point is the midpoint of a line segment
    DISTANCE = "distance"  # distance between points equals a value
    ANGLE = "angle"  # angle between lines equals a value


_ENTITY_COUNTS: dict[ConstraintType, tuple[int, int]] = {
    ConstraintType.FIXED: (1, 1),
    ConstraintType.COINCIDENT: (2, 2),
    ConstraintType.PARALLEL: (2, 2),
    ConstraintType.PERPENDICULAR: (2, 2),
    ConstraintType.TANGENT: (2, 2),
    ConstraintType.ON_LINE: (2, 2),
    ConstraintType.MIDPOINT: (2, 2),
    ConstraintType.DISTANCE: (2, 2),
    ConstraintType.ANGLE: (2, 2),
}


def new_constraint_id(prefix: str = "cst") -> str:
    """Generate a unique constraint id."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class ConstraintRecord:
    """A single geometric constraint between document entities."""

    def __init__(
        self,
        constraint_id: str,
        constraint_type: ConstraintType | str,
        entities: list[str],
        params: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> None:
        """Initialize a constraint record."""
        self.id = constraint_id
        try:
            self.type = ConstraintType(constraint_type)
        except ValueError as exc:
            supported = ", ".join(t.value for t in ConstraintType)
            raise ConstraintError(
                f"Unsupported constraint type {constraint_type!r}. "
                f"Supported: {supported}",
                code="unsupported_type",
            ) from exc
        minimum, maximum = _ENTITY_COUNTS[self.type]
        if not minimum <= len(entities) <= maximum:
            raise ConstraintError(
                f"Constraint {self.type.value} requires {minimum}..{maximum} "
                f"entities, got {len(entities)}",
                code="invalid_arity",
            )
        if len(set(entities)) != len(entities):
            raise ConstraintError(
                f"Constraint {self.type.value} entities must be distinct",
                code="duplicate_entity",
            )
        self.entities = list(entities)
        self.params: dict[str, Any] = dict(params or {})
        self.enabled = enabled

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "id": self.id,
            "type": self.type.value,
            "entities": list(self.entities),
            "params": dict(self.params),
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConstraintRecord:
        """Reconstruct a constraint from a serialized dict."""
        return cls(
            constraint_id=str(data["id"]),
            constraint_type=str(data["type"]),
            entities=[str(e) for e in data["entities"]],
            params=dict(data.get("params") or {}),
            enabled=bool(data.get("enabled", True)),
        )

    def __repr__(self) -> str:
        """Return a compact string representation."""
        return f"ConstraintRecord({self.id}, {self.type.value})"


class ConstraintManager:
    """Manages geometric constraints for a single document."""

    def __init__(self) -> None:
        """Initialize an empty constraint table."""
        self._constraints: dict[str, ConstraintRecord] = {}

    def add(
        self,
        constraint_type: ConstraintType | str,
        entities: list[str],
        params: dict[str, Any] | None = None,
        constraint_id: str | None = None,
    ) -> ConstraintRecord:
        """Create and register a constraint, returning its record."""
        constraint_id = constraint_id or new_constraint_id()
        record = ConstraintRecord(constraint_id, constraint_type, entities, params)
        self._constraints[record.id] = record
        return record

    def get(self, constraint_id: str) -> ConstraintRecord:
        """Return a constraint or raise ``ConstraintError``."""
        record = self._constraints.get(constraint_id)
        if record is None:
            raise ConstraintError(
                f"Constraint not found: {constraint_id}", code="not_found"
            )
        return record

    def remove(self, constraint_id: str) -> None:
        """Delete a constraint or raise ``ConstraintError``."""
        self.get(constraint_id)
        del self._constraints[constraint_id]

    def list(self, entity_id: str | None = None) -> list[ConstraintRecord]:
        """Return all constraints in insertion order, optionally filtered."""
        if entity_id is None:
            return list(self._constraints.values())
        return [
            record
            for record in self._constraints.values()
            if entity_id in record.entities
        ]

    def count(self) -> int:
        """Return the number of constraints."""
        return len(self._constraints)

    def clear(self) -> None:
        """Remove all constraints."""
        self._constraints.clear()

    def snapshot(self) -> dict[str, Any]:
        """Return a deep snapshot for undo/redo."""
        return {
            "constraints": [record.to_dict() for record in self._constraints.values()]
        }

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Restore from a snapshot produced by :meth:`snapshot`."""
        self._constraints = {
            data["id"]: ConstraintRecord.from_dict(data)
            for data in snapshot.get("constraints", [])
        }
