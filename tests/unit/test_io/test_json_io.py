"""JSON schema / importer / exporter tests."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.io.exporters.json_io import JSONExporter
from cad_mcp_server.io.importers.json_io import JSONImporter
from cad_mcp_server.schemas.geometry import GeometryObject
from cad_mcp_server.schemas.scene import SceneDefinition
from cad_mcp_server.utils.errors import CADImportError


class TestSchemas:
    """Pydantic schema tests."""

    def test_line_geometry(self) -> None:
        obj = GeometryObject.model_validate(
            {
                "id": "l1",
                "type": "line",
                "geometry": {"type": "line", "start": [0, 0], "end": [1, 1]},
            }
        )
        assert obj.geometry.type == "line"

    def test_invalid_radius(self) -> None:
        with pytest.raises(ValidationError):
            GeometryObject.model_validate(
                {
                    "id": "c1",
                    "type": "circle",
                    "geometry": {"type": "circle", "center": [0, 0], "radius": -1},
                }
            )

    def test_invalid_layer_color(self) -> None:
        with pytest.raises(ValidationError):
            SceneDefinition.model_validate(
                {"scene_id": "s1", "name": "s", "layers": [{"name": "A", "color": "red"}]}
            )

    def test_discriminator_error(self) -> None:
        with pytest.raises(ValidationError):
            GeometryObject.model_validate(
                {"id": "x", "type": "line", "geometry": {"type": "torus"}}
            )


class TestJSONImporterExporter:
    """JSON document round-trip tests."""

    def _make_doc(self, document_manager: DocumentManager):
        doc_mgr = document_manager
        doc_mgr.create("scene.json", unit="mm")
        doc = doc_mgr.get_current()
        doc.layers.create("Outline", color="#FF0000")
        doc.entities.create("line", {"start": [0, 0, 0], "end": [100, 0, 0]}, layer="Outline")
        doc.entities.create("circle", {"center": [50, 50, 0], "radius": 25}, layer="Outline")
        return doc

    def test_document_to_scene_and_back(self, document_manager: DocumentManager) -> None:
        doc = self._make_doc(document_manager)
        exporter = JSONExporter()
        scene = exporter.to_scene(doc)
        assert scene.scene_id == doc.file_id
        assert len(scene.objects) == 2
        assert scene.objects[0].geometry.type == "line"

        json_string = exporter.export_document(doc)
        data = json.loads(json_string)
        assert data["name"] == "scene.json"
        assert len(data["objects"]) == 2

        importer = JSONImporter()
        parsed = importer.parse(json_string)
        rebuilt = importer.scene_to_document(parsed)
        assert rebuilt.entities.count() == 2
        assert rebuilt.layers.read("Outline").color == "#FF0000"
        bbox = rebuilt.entities.get_bbox(rebuilt.entities.list()[1].id)
        assert bbox["min"] == [25.0, 25.0, 0.0]

    def test_export_to_file_and_import(self, document_manager: DocumentManager, tmp_path) -> None:
        doc = self._make_doc(document_manager)
        target = tmp_path / "scene.json"
        JSONExporter().export_to_file(doc, str(target))
        scene = JSONImporter().import_from_file(str(target))
        assert len(scene.objects) == 2
        assert scene.unit == "mm"

    def test_import_geometry(self) -> None:
        importer = JSONImporter()
        geometry = importer.import_geometry(
            json.dumps(
                [
                    {
                        "id": "a",
                        "type": "line",
                        "geometry": {"type": "line", "start": [0, 0], "end": [1, 0]},
                    },
                    {
                        "id": "b",
                        "type": "circle",
                        "geometry": {"type": "circle", "center": [0, 0], "radius": 5},
                    },
                ]
            )
        )
        assert len(geometry) == 2

    def test_export_geometry(self, document_manager: DocumentManager) -> None:
        doc = self._make_doc(document_manager)
        out = JSONExporter().export_geometry(doc.entities.list())
        data = json.loads(out)
        assert len(data) == 2
        assert data[0]["type"] == "line"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(CADImportError):
            JSONImporter().parse("{oops")

    def test_import_missing_file(self) -> None:
        with pytest.raises(CADImportError):
            JSONImporter().import_from_file("/nope.json")

    def test_import_geometry_single_object(self) -> None:
        geometry = JSONImporter().import_geometry(
            json.dumps(
                {
                    "id": "a",
                    "type": "line",
                    "geometry": {"type": "line", "start": [0, 0], "end": [1, 0]},
                }
            )
        )
        assert len(geometry) == 1
