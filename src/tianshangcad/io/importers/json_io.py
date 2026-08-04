"""JSON scene / geometry importer."""

from __future__ import annotations

import json
from pathlib import Path

from tianshangcad.core.document import DocumentState
from tianshangcad.io.serializers import geometry_object_to_record
from tianshangcad.schemas.geometry import GeometryObject
from tianshangcad.schemas.scene import SceneDefinition
from tianshangcad.utils.errors import CADImportError


class JSONImporter:
    """Import scenes and geometry from JSON."""

    def parse(self, json_data: str) -> SceneDefinition:
        """Parse a JSON string into a validated scene definition."""
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as exc:
            raise CADImportError(f"Invalid JSON: {exc}", code="invalid_json") from exc
        return SceneDefinition.model_validate(data)

    def import_scene(self, json_data: str) -> SceneDefinition:
        """Alias of :meth:`parse`."""
        return self.parse(json_data)

    def import_geometry(self, json_data: str) -> list[GeometryObject]:
        """Parse a JSON list of geometry objects."""
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as exc:
            raise CADImportError(f"Invalid JSON: {exc}", code="invalid_json") from exc
        if isinstance(data, dict):
            data = [data]
        return [GeometryObject.model_validate(obj) for obj in data]

    def scene_to_document(self, scene: SceneDefinition, path: Path | None = None) -> DocumentState:
        """Build an in-memory document from a scene definition."""
        doc = DocumentState(
            file_id=scene.scene_id,
            filename=scene.name,
            unit=scene.unit,
            path=path,
        )
        for layer in scene.layers:
            if layer.name in doc.layers.snapshot()["layers"]:
                continue
            doc.layers.create(
                name=layer.name,
                color=layer.color,
                linetype=layer.linetype,
                linewidth=layer.linewidth,
                visible=layer.visible,
                locked=layer.locked,
            )
        for style in scene.styles:
            doc.styles.create(style.name, style.type, dict(style.properties))
        for obj in scene.objects:
            record = geometry_object_to_record(obj)
            doc.entities._entities[record.id] = record
        doc.is_dirty = False
        return doc

    def import_from_file(self, filepath: str) -> SceneDefinition:
        """Import a scene from a JSON file."""
        path = Path(filepath)
        if not path.is_file():
            raise CADImportError(f"File does not exist: {filepath}", code="file_not_found")
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CADImportError(f"Failed to read {filepath}: {exc}", code="read_failed") from exc
        return self.parse(content)
