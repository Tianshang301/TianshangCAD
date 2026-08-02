"""Document / file management.

A document aggregates entities, layers and styles and can be persisted
as a JSON scene file.
"""

from __future__ import annotations

import builtins
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cad_mcp_server.core.constraint import ConstraintManager
from cad_mcp_server.core.entity import EntityManager
from cad_mcp_server.core.layer_manager import LayerManager
from cad_mcp_server.core.session import SessionManager
from cad_mcp_server.core.style_manager import StyleManager
from cad_mcp_server.core.variables import VariableManager
from cad_mcp_server.core.view_manager import ViewManager
from cad_mcp_server.utils.errors import CADImportError, DocumentError
from cad_mcp_server.utils.units import validate_unit

_SCENE_FORMAT = "tianshang-cad-scene"
_SCENE_VERSION = 1


class DocumentState:
    """An open design document."""

    def __init__(
        self,
        file_id: str,
        filename: str,
        unit: str = "mm",
        path: Path | None = None,
    ) -> None:
        """Initialize an open document."""
        self.file_id = file_id
        self.filename = filename
        self.path = Path(path) if path else None
        self.unit = validate_unit(unit)
        self.entities = EntityManager()
        self.layers = LayerManager()
        self.styles = StyleManager()
        self.views = ViewManager()
        self.variables = VariableManager()
        self.constraints = ConstraintManager()
        self.created_at = datetime.now(UTC).isoformat()
        self.modified_at = self.created_at
        self.is_dirty = False
        self._closed = False

    def touch(self) -> None:
        """Mark the document modified."""
        self.modified_at = datetime.now(UTC).isoformat()
        self.is_dirty = True

    def close(self) -> None:
        """Release the document resources."""
        self._closed = True
        self.entities = EntityManager()
        self.layers = LayerManager()
        self.styles = StyleManager()
        self.views = ViewManager()
        self.variables = VariableManager()
        self.constraints = ConstraintManager()

    @property
    def closed(self) -> bool:
        """Whether the document has been closed."""
        return self._closed

    def to_dict(self) -> dict[str, Any]:
        """Serialize the document to a JSON-safe dict."""
        return {
            "format": _SCENE_FORMAT,
            "version": _SCENE_VERSION,
            "file_id": self.file_id,
            "filename": self.filename,
            "unit": self.unit,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "layers": [layer.to_dict() for layer in self.layers.list()],
            "styles": [style.to_dict() for style in self.styles.list()],
            "views": [view.to_dict() for view in self.views.list()],
            "current_layer": self.layers.get_current().name,
            "variables": [var.to_dict() for var in self.variables.list()],
            "constraints": [constraint.to_dict() for constraint in self.constraints.list()],
            "entities": [record.to_dict() for record in self.entities.list()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: Path | None = None) -> DocumentState:
        """Reconstruct a document from a serialized dict."""
        if data.get("format") != _SCENE_FORMAT:
            raise CADImportError("Unrecognized scene file format", code="bad_format")
        doc = cls(
            file_id=str(data.get("file_id", f"file_{uuid.uuid4().hex[:8]}")),
            filename=str(data.get("filename", path.name if path else "document.json")),
            unit=str(data.get("unit", "mm")),
            path=path,
        )
        doc.created_at = str(data.get("created_at", doc.created_at))
        doc.modified_at = str(data.get("modified_at", doc.modified_at))
        for layer_data in data.get("layers", []):
            name = str(layer_data["name"])
            if name in doc.layers.snapshot()["layers"]:
                continue
            doc.layers.create(**layer_data)
        for style_data in data.get("styles", []):
            doc.styles.create(style_data["name"], style_data["type"], style_data.get("properties"))
        for view_data in data.get("views", []):
            from cad_mcp_server.schemas.view3d import View3DDefinition

            view = View3DDefinition.model_validate(view_data)
            doc.views._views[view.view_id] = view
        current_layer = data.get("current_layer", "0")
        if current_layer in doc.layers.snapshot()["layers"]:
            doc.layers.set_current(current_layer)
        for var_data in data.get("variables", []):
            from cad_mcp_server.core.variables import VariableRecord

            var_record = VariableRecord.from_dict(var_data)
            doc.variables._variables[var_record.name] = var_record
        for constraint_data in data.get("constraints", []):
            from cad_mcp_server.core.constraint import ConstraintRecord

            constraint_record = ConstraintRecord.from_dict(constraint_data)
            doc.constraints._constraints[constraint_record.id] = constraint_record
        for entity_data in data.get("entities", []):
            from cad_mcp_server.core.entity import EntityRecord

            entity_record = EntityRecord.from_dict(entity_data)
            doc.entities._entities[entity_record.id] = entity_record
        doc.is_dirty = False
        return doc


class DocumentManager:
    """Facade over the active session's documents."""

    def __init__(self) -> None:
        """Initialize a document manager bound to the current session."""
        self._session = SessionManager().current_session

    def create(
        self,
        filename: str,
        template: str | None = None,
        unit: str = "mm",
    ) -> str:
        """Create a new document and return its file id."""
        validate_unit(unit)
        if not filename:
            raise DocumentError("Filename cannot be empty", code="invalid_filename")
        if template and not Path(template).expanduser().is_file():
            raise DocumentError(f"Template not found: {template}", code="template_not_found")
        file_id = f"file_{uuid.uuid4().hex[:8]}"
        doc = DocumentState(file_id=file_id, filename=filename, unit=unit)
        self._session.active_files[file_id] = doc
        self._session.current_file_id = file_id
        return file_id

    def open(self, path: str) -> str:
        """Open a JSON scene file and return its file id."""
        file_path = Path(path)
        if not file_path.is_file():
            raise DocumentError(f"File does not exist: {path}", code="file_not_found")
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise CADImportError(f"Failed to read {path}: {exc}", code="read_failed") from exc
        doc = DocumentState.from_dict(data, path=file_path)
        self._session.active_files[doc.file_id] = doc
        self._session.current_file_id = doc.file_id
        return doc.file_id

    def save(self, file_id: str | None = None, path: str | None = None) -> str:
        """Save a document to disk, returning the saved path."""
        doc = self._require(file_id)
        target = Path(path) if path else doc.path
        if target is None:
            raise DocumentError(
                f"No save path set for {doc.filename}; provide a path",
                code="no_save_path",
            )
        if not target.suffix:
            target = target.with_suffix(".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("w", encoding="utf-8") as handle:
                json.dump(doc.to_dict(), handle, indent=2, ensure_ascii=False)
        except OSError as exc:
            raise DocumentError(f"Failed to save {target}: {exc}", code="save_failed") from exc
        doc.path = target
        doc.is_dirty = False
        return str(target)

    def close(self, file_id: str | None = None) -> None:
        """Close a document."""
        doc = self._require(file_id)
        doc.close()
        del self._session.active_files[doc.file_id]
        if self._session.current_file_id == doc.file_id:
            self._session.current_file_id = None

    def list(self) -> builtins.list[dict[str, Any]]:
        """List open documents."""
        return [
            {
                "file_id": doc.file_id,
                "filename": doc.filename,
                "unit": doc.unit,
                "entity_count": doc.entities.count(),
                "dirty": doc.is_dirty,
            }
            for doc in self._session.active_files.values()
        ]

    def info(self, file_id: str | None = None) -> dict[str, Any]:
        """Return details about a document."""
        doc = self._require(file_id)
        bbox = self._compute_bbox(doc)
        return {
            "file_id": doc.file_id,
            "filename": doc.filename,
            "path": str(doc.path) if doc.path else None,
            "unit": doc.unit,
            "entity_count": doc.entities.count(),
            "layer_count": len(doc.layers.list()),
            "bbox": bbox,
            "dirty": doc.is_dirty,
            "created_at": doc.created_at,
            "modified_at": doc.modified_at,
        }

    def get_current(self) -> DocumentState:
        """Return the current document or raise ``DocumentError``."""
        doc = self._require(None)
        return doc

    def _require(self, file_id: str | None) -> DocumentState:
        session = self._session
        if file_id is not None:
            doc = session.active_files.get(file_id)
            if doc is None:
                raise DocumentError(f"File not open: {file_id}", code="file_not_open")
            return doc
        current_id = session.current_file_id
        if current_id is None or current_id not in session.active_files:
            raise DocumentError(
                "No active document; create or open one first",
                code="no_active_document",
            )
        return session.active_files[current_id]

    @staticmethod
    def _compute_bbox(doc: DocumentState) -> dict[str, builtins.list[float]]:
        records = doc.entities.list()
        if not records:
            return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}
        kernel = doc.entities.kernel
        minimum = [float("inf")] * 3
        maximum = [float("-inf")] * 3
        for record in records:
            bbox = kernel.get_bbox(record.shape)
            for i in range(3):
                minimum[i] = min(minimum[i], bbox["min"][i])
                maximum[i] = max(maximum[i], bbox["max"][i])
        return {"min": minimum, "max": maximum}
