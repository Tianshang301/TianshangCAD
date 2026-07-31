"""JSON-driven workflow integration tests."""

from __future__ import annotations

import json

from cad_mcp_server.mcp.tools.json_ops import (
    JsonExportSceneInput,
    JsonImportGeometryInput,
    JsonImportSceneInput,
    JsonValidateInput,
    cad_json_export_scene,
    cad_json_import_geometry,
    cad_json_import_scene,
    cad_json_validate,
)
from cad_mcp_server.mcp.tools.validate import (
    MetricsGetInput,
    ValidateInterferenceInput,
    cad_metrics_get,
    cad_validate_interference,
)

SCENE = {
    "scene_id": "scene_workflow",
    "name": "Workflow Scene",
    "unit": "mm",
    "layers": [
        {"name": "Part", "color": "#3366CC"},
        {"name": "Support", "color": "#66CC33"},
    ],
    "objects": [
        {
            "id": "part",
            "type": "box",
            "layer": "Part",
            "geometry": {
                "type": "box",
                "origin": [0, 0, 0],
                "dimensions": [50, 50, 10],
            },
        },
        {
            "id": "support",
            "type": "box",
            "layer": "Support",
            "geometry": {
                "type": "box",
                "origin": [25, 25, 5],
                "dimensions": [40, 40, 20],
            },
        },
    ],
}


class TestJSONWorkflow:
    """JSON import -> validate -> export -> interfere workflow."""

    def test_full_json_roundtrip(self) -> None:
        scene_json = json.dumps(SCENE)

        validation = cad_json_validate(
            JsonValidateInput(json_string=scene_json, schema_name="scene")
        )
        assert validation.is_valid is True

        imported = cad_json_import_scene(JsonImportSceneInput(json_data=scene_json))
        assert imported.status == "success"
        assert imported.object_count == 2

        exported = cad_json_export_scene(JsonExportSceneInput())
        data = json.loads(exported.json_string)
        assert data["name"] == "Workflow Scene"
        assert len(data["objects"]) == 2
        object_ids = {obj["id"] for obj in data["objects"]}
        assert object_ids == {"part", "support"}
        layer_names = {layer["name"] for layer in data["layers"]}
        assert {"Part", "Support"} <= layer_names

    def test_geometry_import_then_interference(self) -> None:
        boxes = json.dumps(
            [
                {
                    "id": "a",
                    "type": "box",
                    "layer": "0",
                    "geometry": {"type": "box", "origin": [0, 0, 0], "dimensions": [10, 10, 10]},
                },
                {
                    "id": "b",
                    "type": "box",
                    "layer": "0",
                    "geometry": {"type": "box", "origin": [8, 8, 8], "dimensions": [10, 10, 10]},
                },
            ]
        )
        cad_json_import_scene(
            JsonImportSceneInput(json_data=json.dumps({"scene_id": "s", "name": "s"}))
        )
        imported = cad_json_import_geometry(JsonImportGeometryInput(json_data=boxes))
        assert imported.status == "success"
        assert len(imported.imported_objects) == 2

        interference = cad_validate_interference(ValidateInterferenceInput())
        assert interference.interference_count == 1

        metrics = cad_metrics_get(MetricsGetInput())
        assert metrics.objects == 2
