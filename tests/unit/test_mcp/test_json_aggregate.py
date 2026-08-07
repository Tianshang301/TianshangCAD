"""Tests for the aggregate cad_json MCP tool."""

from __future__ import annotations

import json

from tianshangcad.mcp.tools.crud import FileCreateInput, cad_file_create
from tianshangcad.mcp.tools.json_ops import (
    JsonExportGeometryParams,
    JsonExportSceneParams,
    JsonImportGeometryParams,
    JsonImportSceneParams,
    JsonInput,
    JsonLoadParams,
    JsonParseParams,
    JsonSaveParams,
    JsonValidateParams,
    cad_json,
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

SCENE_JSON = json.dumps(
    {
        "scene_id": "scene_test",
        "name": "Test Scene",
        "unit": "mm",
        "layers": [{"name": "Outline", "color": "#FF0000"}],
        "objects": [
            {
                "id": "line_1",
                "type": "line",
                "layer": "Outline",
                "geometry": {"type": "line", "start": [0, 0, 0], "end": [100, 0, 0]},
            }
        ],
    }
)


class TestJsonLoad:
    """cad_json action=load."""

    def test_load(self, tmp_path) -> None:
        target = tmp_path / "data.json"
        target.write_text('{"a": 1}', encoding="utf-8")
        result = cad_json(JsonInput(params=JsonLoadParams(action="load", path=str(target))))
        assert result.status == "success"
        assert result.content == '{"a": 1}'

    def test_load_missing(self) -> None:
        result = cad_json(JsonInput(params=JsonLoadParams(action="load", path="nope.json")))
        assert result.status == "error"


class TestJsonParse:
    """cad_json action=parse."""

    def test_parse_object(self) -> None:
        result = cad_json(JsonInput(params=JsonParseParams(action="parse", json_string='{"a": 1}')))
        assert result.status == "success"
        assert result.is_valid is True
        assert result.content == "object"

    def test_parse_array(self) -> None:
        result = cad_json(JsonInput(params=JsonParseParams(action="parse", json_string="[1, 2]")))
        assert result.status == "success"
        assert result.object_count == 2

    def test_parse_invalid(self) -> None:
        result = cad_json(JsonInput(params=JsonParseParams(action="parse", json_string="not json")))
        assert result.status == "error"
        assert result.is_valid is False


class TestJsonValidate:
    """cad_json action=validate."""

    def test_validate_scene_valid(self) -> None:
        result = cad_json(
            JsonInput(params=JsonValidateParams(action="validate", json_string=SCENE_JSON))
        )
        assert result.status == "success"
        assert result.is_valid is True

    def test_validate_geometry_valid(self) -> None:
        result = cad_json(
            JsonInput(
                params=JsonValidateParams(
                    action="validate", json_string=GEOMETRY_JSON, schema_name="geometry"
                )
            )
        )
        assert result.status == "success"
        assert result.is_valid is True

    def test_validate_invalid(self) -> None:
        result = cad_json(
            JsonInput(
                params=JsonValidateParams(
                    action="validate", json_string='{"not": "a scene"}'
                )
            )
        )
        assert result.status == "error"
        assert len(result.errors) > 0


class TestJsonImportExportGeometry:
    """cad_json import_geometry / export_geometry."""

    def test_import_geometry(self) -> None:
        cad_file_create(FileCreateInput(filename="g.json"))
        result = cad_json(
            JsonInput(
                params=JsonImportGeometryParams(
                    action="import_geometry", json_data=GEOMETRY_JSON
                )
            )
        )
        assert result.status == "success"
        assert result.object_count == 2
        assert len(result.imported_objects) == 2

    def test_export_geometry_roundtrip(self) -> None:
        cad_file_create(FileCreateInput(filename="g.json"))
        cad_json(
            JsonInput(
                params=JsonImportGeometryParams(
                    action="import_geometry", json_data=GEOMETRY_JSON
                )
            )
        )
        result = cad_json(
            JsonInput(params=JsonExportGeometryParams(action="export_geometry"))
        )
        assert result.status == "success"
        exported = json.loads(result.content)
        assert len(exported) == 2


class TestJsonImportExportScene:
    """cad_json import_scene / export_scene."""

    def test_import_scene(self) -> None:
        result = cad_json(
            JsonInput(params=JsonImportSceneParams(action="import_scene", json_data=SCENE_JSON))
        )
        assert result.status == "success"
        assert result.object_count == 1

    def test_export_scene(self) -> None:
        cad_file_create(FileCreateInput(filename="s.json"))
        result = cad_json(JsonInput(params=JsonExportSceneParams(action="export_scene")))
        assert result.status == "success"
        data = json.loads(result.content)
        assert "objects" in data


class TestJsonSave:
    """cad_json action=save."""

    def test_save(self, tmp_path) -> None:
        target = tmp_path / "out.json"
        result = cad_json(
            JsonInput(
                params=JsonSaveParams(
                    action="save", json_string='{"x": 1}', path=str(target)
                )
            )
        )
        assert result.status == "success"
        assert target.exists()
