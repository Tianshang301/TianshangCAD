"""JSON scene / geometry exporter."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from cad_mcp_server.core.document import DocumentState
from cad_mcp_server.core.entity import EntityRecord
from cad_mcp_server.io.serializers import record_to_geometry_object
from cad_mcp_server.schemas.geometry import GeometryObject
from cad_mcp_server.schemas.scene import LayerDefinition, SceneDefinition, StyleDefinition
from cad_mcp_server.utils.errors import CADExportError


class JSONExporter:
    """Export documents and geometry as JSON."""

    def to_scene(self, doc: DocumentState) -> SceneDefinition:
        """Build a validated scene definition from a document."""
        return SceneDefinition(
            scene_id=doc.file_id,
            name=doc.filename,
            unit=doc.unit,
            layers=[LayerDefinition(**layer.to_dict()) for layer in doc.layers.list()],
            styles=[StyleDefinition(**style.to_dict()) for style in doc.styles.list()],
            objects=[record_to_geometry_object(record) for record in doc.entities.list()],
        )

    def export_scene(self, scene: SceneDefinition, pretty: bool = True) -> str:
        """Serialize a scene definition to a JSON string."""
        return scene.model_dump_json(indent=2 if pretty else None)

    def export_document(self, doc: DocumentState, pretty: bool = True) -> str:
        """Serialize a document as a JSON scene string."""
        return self.export_scene(self.to_scene(doc), pretty)

    def export_geometry(
        self, objects: Iterable[EntityRecord | GeometryObject], pretty: bool = True
    ) -> str:
        """Serialize entity records or geometry objects to a JSON string."""
        geometry_objects = [
            record_to_geometry_object(record) if isinstance(record, EntityRecord) else record
            for record in objects
        ]
        data = [obj.model_dump() for obj in geometry_objects]
        return json.dumps(data, indent=2 if pretty else None, ensure_ascii=False)

    def export_to_file(self, doc: DocumentState, filepath: str, pretty: bool = True) -> None:
        """Write a document to a JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(self.export_document(doc, pretty), encoding="utf-8")
        except OSError as exc:
            raise CADExportError(f"Failed to write {filepath}: {exc}", code="write_failed") from exc
