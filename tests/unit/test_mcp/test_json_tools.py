"""JSON tool unit tests."""

from __future__ import annotations

import json

from cad_mcp_server.mcp.tools.crud import FileCreateInput, cad_file_create
from cad_mcp_server.mcp.tools.json_ops import (
    JsonExportGeometryInput,
    JsonExportSceneInput,
    JsonImportGeometryInput,
    JsonImportSceneInput,
    JsonLoadInput,
    JsonParseInput,
    JsonSaveInput,
    JsonValidateInput,
    cad_json_export_geometry,
    cad_json_export_scene,
    cad_json_import_geometry,
    cad_json_import_scene,
    cad_json_load,
    cad_json_parse,
    cad_json_save,
    cad_json_validate,
)

SCENE_JSON = json.dumps(
    {
        "scene_id": "scene_test",
        "name": "Test Scene",
        "unit": "mm",
        "layers": [
            {"name": "Outline", "color": "#FF0000"},
            {"name": "Annotation", "color": "#00FF00"},
        ],
        "objects": [
            {
                "id": "line_1",
                "type": "line",
                "layer": "Outline",
                "geometry": {"type": "line", "start": [0, 0, 0], "end": [100, 0, 0]},
            },
            {
                "id": "circle_1",
                "type": "circle",
                "layer": "Outline",
                "geometry": {"type": "circle", "center": [50, 50, 0], "radius": 25},
            },
        ],
    }
)

GEOMETRY_JSON = json.dumps(
    [
        {
            "id": "line_1",
            "type": "line",
            "layer": "0",
            "geometry": {"type": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
        },
        {
            "id": "circle_1",
            "type": "circle",
            "layer": "0",
            "geometry": {"type": "circle", "center": [5, 5, 0], "radius": 2},
        },
    ]
)


class TestJsonParseTools:
    """Parse / validate / load tools."""

    def test_parse_valid_object(self) -> None:
        result = cad_json_parse(JsonParseInput(json_string='{"a": 1}'))
        assert result.is_valid is True
        assert result.root_type == "object"

    def test_parse_valid_array(self) -> None:
        result = cad_json_parse(JsonParseInput(json_string="[1, 2, 3]"))
        assert result.is_valid is True
        assert result.root_type == "array"
        assert result.object_count == 3

    def test_parse_invalid(self) -> None:
        result = cad_json_parse(JsonParseInput(json_string="{not json"))
        assert result.is_valid is False
        assert "Invalid JSON" in result.message

    def test_validate_scene_ok(self) -> None:
        result = cad_json_validate(
            JsonValidateInput(json_string=SCENE_JSON, schema_name="scene")
        )
        assert result.is_valid is True

    def test_validate_geometry_ok(self) -> None:
        result = cad_json_validate(
            JsonValidateInput(json_string=GEOMETRY_JSON, schema_name="geometry")
        )
        assert result.is_valid is True

    def test_validate_bad_geometry(self) -> None:
        bad = json.dumps(
            [
                {
                    "id": "bad",
                    "type": "line",
                    "geometry": {"type": "circle", "radius": -5},
                }
            ]
        )
        result = cad_json_validate(
            JsonValidateInput(json_string=bad, schema_name="geometry")
        )
        assert result.is_valid is False

    def test_load_missing_file(self) -> None:
        result = cad_json_load(JsonLoadInput(path="/nope/missing.json"))
        assert result.status == "error"


class TestJsonImportExport:
    """JSON import/export tools."""

    def test_import_geometry(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        result = cad_json_import_geometry(
            JsonImportGeometryInput(json_data=GEOMETRY_JSON)
        )
        assert result.status == "success"
        assert len(result.imported_objects) == 2
        assert result.imported_objects[0]["object_id"] == "line_1"

    def test_import_geometry_no_document(self) -> None:
        result = cad_json_import_geometry(
            JsonImportGeometryInput(json_data=GEOMETRY_JSON)
        )
        assert result.status == "error"

    def test_export_geometry_roundtrip(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        imported = cad_json_import_geometry(
            JsonImportGeometryInput(json_data=GEOMETRY_JSON)
        )
        exported = cad_json_export_geometry(
            JsonExportGeometryInput(
                object_ids=[obj["object_id"] for obj in imported.imported_objects]
            )
        )
        assert exported.status == "success"
        assert exported.count == 2
        data = json.loads(exported.json_string)
        assert data[0]["id"] == "line_1"
        assert data[1]["type"] == "circle"

    def test_export_scene(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_json_import_geometry(JsonImportGeometryInput(json_data=GEOMETRY_JSON))
        exported = cad_json_export_scene(JsonExportSceneInput())
        assert exported.status == "success"
        data = json.loads(exported.json_string)
        assert data["name"] == "draw.json"
        assert len(data["objects"]) == 2

    def test_import_scene(self) -> None:
        result = cad_json_import_scene(JsonImportSceneInput(json_data=SCENE_JSON))
        assert result.status == "success"
        assert result.name == "Test Scene"
        assert result.object_count == 2

    def test_import_scene_invalid(self) -> None:
        result = cad_json_import_scene(
            JsonImportSceneInput(json_data=json.dumps({"bad": True}))
        )
        assert result.status == "error"

    def test_import_scene_creates_layers(self) -> None:
        cad_json_import_scene(JsonImportSceneInput(json_data=SCENE_JSON))
        result = cad_json_export_scene(JsonExportSceneInput())
        data = json.loads(result.json_string)
        layer_names = {layer["name"] for layer in data["layers"]}
        assert {"Outline", "Annotation"} <= layer_names


class TestJsonSave:
    """JSON save tool."""

    def test_save(self, tmp_path) -> None:
        target = tmp_path / "out.json"
        result = cad_json_save(
            JsonSaveInput(json_string='{"a": 1}', path=str(target))
        )
        assert result.status == "success"
        assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
