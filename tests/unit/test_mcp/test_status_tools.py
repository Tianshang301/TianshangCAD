"""Status and log tool unit tests."""

from __future__ import annotations

from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    LayerCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_layer_create,
    cad_object_create,
)
from tianshangcad.mcp.tools.status import (
    LogsClearInput,
    LogsGetInput,
    StatusCheckInput,
    StatusFileInput,
    StatusHealthInput,
    StatusLayerInput,
    StatusObjectInput,
    cad_logs_clear,
    cad_logs_get,
    cad_status_check,
    cad_status_file,
    cad_status_health,
    cad_status_layer,
    cad_status_object,
)


class TestStatusTools:
    """Status tools."""

    def test_status_check_empty(self) -> None:
        result = cad_status_check(StatusCheckInput())
        assert result.status == "ok"
        assert result.files_open == 0
        assert result.current_file is None

    def test_status_check_with_document(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_object_create(
            ObjectCreateInput(
                type="box",
                params={"origin": [0, 0, 0], "dimensions": [1, 2, 3]},
                layer="0",
            )
        )
        result = cad_status_check(StatusCheckInput())
        assert result.files_open == 1
        assert result.objects == 1
        assert result.layers >= 1

    def test_status_file(self) -> None:
        file_id = cad_file_create(FileCreateInput(filename="part.dwg")).file_id
        result = cad_status_file(StatusFileInput(file_id=file_id))
        assert result.status == "success"
        assert result.filename == "part.dwg"
        assert result.dirty is False

    def test_status_file_missing(self) -> None:
        result = cad_status_file(StatusFileInput(file_id="nope"))
        assert result.status == "error"

    def test_status_object(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        object_id = cad_object_create(
            ObjectCreateInput(
                type="sphere",
                params={"center": [0, 0, 0], "radius": 5},
                layer="0",
            )
        ).object_id
        result = cad_status_object(StatusObjectInput(object_id=object_id))
        assert result.status == "success"
        assert result.type == "sphere"
        assert result.bbox["max"] == [5.0, 5.0, 5.0]

    def test_status_object_missing(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        result = cad_status_object(StatusObjectInput(object_id="nope"))
        assert result.status == "error"

    def test_status_layer(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_layer_create(LayerCreateInput(name="Outline"))
        cad_object_create(
            ObjectCreateInput(
                type="line",
                params={"start": [0, 0, 0], "end": [1, 1, 0]},
                layer="Outline",
            )
        )
        result = cad_status_layer(StatusLayerInput(name="Outline"))
        assert result.status == "success"
        assert result.object_count == 1

    def test_status_layer_missing(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        result = cad_status_layer(StatusLayerInput(name="Nope"))
        assert result.status == "error"

    def test_status_health(self) -> None:
        result = cad_status_health(StatusHealthInput())
        assert result.ok is True
        assert result.tool_count >= 30
        assert result.version


class TestLogTools:
    """Log tools."""

    def test_logs_get_empty(self) -> None:
        result = cad_logs_get(LogsGetInput())
        assert result.total == 0

    def test_logs_clear(self) -> None:
        cad_logs_get(LogsGetInput())  # ensure tools are importable
        result = cad_logs_clear(LogsClearInput())
        assert result.status == "success"
        assert result.cleared >= 0
