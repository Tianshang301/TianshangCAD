"""Geometry entity management."""

from __future__ import annotations

import copy
import inspect
import uuid
from datetime import UTC, datetime
from typing import Any

from cad_mcp_server.core.kernel import CADKernel, Shape, get_kernel
from cad_mcp_server.utils.errors import EntityError

_TYPE_METHODS: dict[str, str] = {
    "line": "create_line",
    "circle": "create_circle",
    "arc": "create_arc",
    "rectangle": "create_rectangle",
    "rect": "create_rectangle",
    "polygon": "create_polygon",
    "polyline": "create_polyline",
    "box": "create_box",
    "cube": "create_box",
    "cylinder": "create_cylinder",
    "sphere": "create_sphere",
    "cone": "create_cone",
}


class EntityRecord:
    """An entity stored in a document."""

    def __init__(
        self,
        entity_id: str,
        type: str,  # noqa: A002 - matches serialized JSON field name
        shape: Shape,
        layer: str,
        properties: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: str | None = None,
        modified_at: str | None = None,
    ) -> None:
        """Initialize an entity record with its geometry and metadata."""
        self.id = entity_id
        self.type = type
        self.shape = shape
        self.layer = layer
        self.properties: dict[str, Any] = dict(properties or {})
        self.metadata: dict[str, Any] = dict(metadata or {})
        now = datetime.now(UTC).isoformat()
        self.created_at = created_at or now
        self.modified_at = modified_at or now

    def touch(self) -> None:
        """Update ``modified_at`` to the current time."""
        self.modified_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "id": self.id,
            "type": self.type,
            "shape": copy.deepcopy(self.shape),
            "layer": self.layer,
            "properties": copy.deepcopy(self.properties),
            "metadata": copy.deepcopy(self.metadata),
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityRecord:
        """Reconstruct an entity from a serialized dict."""
        return cls(
            entity_id=str(data["id"]),
            type=str(data["type"]),
            shape=copy.deepcopy(data["shape"]),
            layer=str(data.get("layer", "0")),
            properties=dict(data.get("properties") or {}),
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at")),
            modified_at=str(data.get("modified_at")),
        )

    def __repr__(self) -> str:
        """Return a compact string representation."""
        return f"EntityRecord({self.id}, {self.type})"


def new_entity_id(prefix: str = "obj") -> str:
    """Generate a unique entity id."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class EntityManager:
    """Manages geometry entities for a single document."""

    def __init__(self, kernel: CADKernel | None = None) -> None:
        """Initialize an entity manager with an optional kernel."""
        self._kernel = kernel or get_kernel()
        self._entities: dict[str, EntityRecord] = {}

    @property
    def kernel(self) -> CADKernel:
        """Return the underlying geometry kernel."""
        return self._kernel

    def create(
        self,
        obj_type: str,
        params: dict[str, Any],
        layer: str = "0",
        properties: dict[str, Any] | None = None,
        object_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create an entity and return its id."""
        shape = self._build_shape(obj_type, params)
        entity_id = object_id or new_entity_id()
        record = EntityRecord(
            entity_id, _canonical_type(obj_type), shape, layer, properties, metadata
        )
        self._entities[entity_id] = record
        return entity_id

    def _build_shape(self, obj_type: str, params: dict[str, Any]) -> Shape:
        method_name = _TYPE_METHODS.get(obj_type.lower())
        if method_name is None:
            supported = ", ".join(sorted(_TYPE_METHODS))
            raise EntityError(
                f"Unsupported object type {obj_type!r}. Supported: {supported}",
                code="unknown_type",
            )
        method = getattr(self._kernel, method_name)
        parameters = inspect.signature(method).parameters
        accepted = [name for name in parameters if name not in ("self", "target", "tool")]
        required = [
            name
            for name in accepted
            if parameters[name].default is inspect.Parameter.empty
        ]
        missing = [name for name in required if name not in params]
        if missing:
            raise EntityError(
                f"Object type {obj_type!r} requires parameters: {', '.join(missing)}",
                code="missing_params",
            )
        kwargs = {name: params[name] for name in accepted if name in params}
        try:
            return method(**kwargs)  # type: ignore[no-any-return]
        except (TypeError, ValueError) as exc:
            raise EntityError(
                f"Invalid parameters for {obj_type}: {exc}", code="invalid_params"
            ) from exc

    def get(self, entity_id: str) -> EntityRecord:
        """Return the entity with ``entity_id`` or raise ``EntityError``."""
        record = self._entities.get(entity_id)
        if record is None:
            raise EntityError(f"Object not found: {entity_id}", code="object_not_found")
        return record

    def read(self, entity_id: str) -> EntityRecord:
        """Alias of :meth:`get`."""
        return self.get(entity_id)

    def update(
        self,
        entity_id: str,
        params: dict[str, Any] | None = None,
        layer: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> EntityRecord:
        """Update geometry, layer and/or properties of an entity."""
        record = self.get(entity_id)
        if params is not None:
            record.shape = self._build_shape(record.type, params)
        if layer is not None:
            record.layer = layer
        if properties is not None:
            record.properties.update(properties)
        record.touch()
        return record

    def delete(self, entity_id: str) -> None:
        """Delete an entity or raise ``EntityError``."""
        self.get(entity_id)
        del self._entities[entity_id]

    def copy(self, entity_id: str, new_id: str | None = None) -> str:
        """Copy an entity, returning the new id."""
        record = self.get(entity_id)
        target_id = new_id or new_entity_id()
        copied = copy.deepcopy(record)
        copied.id = target_id
        copied.created_at = datetime.now(UTC).isoformat()
        copied.touch()
        name = str(copied.metadata.get("name") or entity_id)
        copied.metadata["name"] = f"{name}_copy"
        self._entities[target_id] = copied
        return target_id

    def transform(self, entity_id: str, matrix: Any) -> EntityRecord:
        """Apply a 4x4 matrix to an entity's shape."""
        record = self.get(entity_id)
        record.shape = self._kernel.transform(record.shape, matrix)
        record.touch()
        return record

    def get_bbox(self, entity_id: str) -> dict[str, list[float]]:
        """Return the bounding box of an entity."""
        record = self.get(entity_id)
        return self._kernel.get_bbox(record.shape)

    def list(self, layer: str | None = None) -> list[EntityRecord]:
        """List entities, optionally filtered by layer."""
        records = list(self._entities.values())
        if layer is not None:
            records = [record for record in records if record.layer == layer]
        return records

    def count(self) -> int:
        """Return the number of entities."""
        return len(self._entities)

    def snapshot(self) -> dict[str, Any]:
        """Return a deep snapshot for undo/redo."""
        return {entity_id: record.to_dict() for entity_id, record in self._entities.items()}

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Restore from a snapshot produced by :meth:`snapshot`."""
        self._entities = {
            entity_id: EntityRecord.from_dict(data)
            for entity_id, data in snapshot.items()
        }


def _canonical_type(obj_type: str) -> str:
    aliases = {"rect": "rectangle", "cube": "box"}
    return aliases.get(obj_type.lower(), obj_type.lower())
