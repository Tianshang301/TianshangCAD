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
    LogsClearParams,
    LogsGetInput,
    LogsGetParams,
    LogsInput,
    StatusCheckInput,
    StatusCheckParams,
    StatusFileInput,
    StatusFileParams,
    StatusHealthInput,
    StatusHealthParams,
    StatusInput,
    StatusLayerInput,
    StatusLayerParams,
    StatusObjectInput,
    StatusObjectParams,
    cad_logs,
    cad_logs_clear,
    cad_logs_get,
    cad_status,
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
        assert result.tool_count >= 19
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


class TestStatusAggregate:
    """Aggregate cad_status tool (discriminated target)."""

    def test_target_check_empty(self) -> None:
        result = cad_status(StatusInput(status=StatusCheckParams()))
        assert result.status == "ok"
        assert result.summary["files_open"] == 0

    def test_target_check_with_document(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_object_create(
            ObjectCreateInput(
                type="box",
                params={"origin": [0, 0, 0], "dimensions": [1, 2, 3]},
                layer="0",
            )
        )
        result = cad_status(StatusInput(status=StatusCheckParams()))
        assert result.summary["files_open"] == 1
        assert result.summary["objects"] == 1

    def test_target_file_success_and_missing(self) -> None:
        file_id = cad_file_create(FileCreateInput(filename="part.dwg")).file_id
        ok = cad_status(StatusInput(status=StatusFileParams(file_id=file_id)))
        assert ok.status == "success"
        assert ok.summary["filename"] == "part.dwg"
        missing = cad_status(StatusInput(status=StatusFileParams(file_id="nope")))
        assert missing.status == "error"

    def test_target_object_success_and_missing(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        object_id = cad_object_create(
            ObjectCreateInput(
                type="sphere",
                params={"center": [0, 0, 0], "radius": 5},
                layer="0",
            )
        ).object_id
        ok = cad_status(StatusInput(status=StatusObjectParams(object_id=object_id)))
        assert ok.status == "success"
        assert ok.summary["bbox"]["max"] == [5.0, 5.0, 5.0]
        missing = cad_status(StatusInput(status=StatusObjectParams(object_id="nope")))
        assert missing.status == "error"

    def test_target_layer_success_and_missing(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_layer_create(LayerCreateInput(name="Outline"))
        cad_object_create(
            ObjectCreateInput(
                type="line",
                params={"start": [0, 0, 0], "end": [1, 1, 0]},
                layer="Outline",
            )
        )
        ok = cad_status(StatusInput(status=StatusLayerParams(name="Outline")))
        assert ok.status == "success"
        assert ok.summary["object_count"] == 1
        missing = cad_status(StatusInput(status=StatusLayerParams(name="Nope")))
        assert missing.status == "error"

    def test_target_health(self) -> None:
        result = cad_status(StatusInput(status=StatusHealthParams()))
        assert result.status == "success"
        assert result.summary["ok"] is True
        assert result.summary["version"]
        assert result.summary["tool_count"] >= 19


class TestLogsAggregate:
    """Aggregate cad_logs tool (discriminated action)."""

    def test_action_get_empty(self) -> None:
        result = cad_logs(LogsInput(logs=LogsGetParams()))
        assert result.status == "success"
        assert result.action == "get"
        assert result.total == 0

    def test_action_get_filters(self) -> None:
        from tianshangcad.mcp.tools.status import _log_buffer

        _log_buffer.clear()
        from tianshangcad.mcp.tools.status import log_event

        log_event("INFO", "test_source", "hello", job_id="j1")
        log_event("ERROR", "other", "boom", job_id="j1")
        result = cad_logs(
            LogsInput(logs=LogsGetParams(source="test_source", level="INFO", job_id="j1"))
        )
        assert result.total == 1
        assert result.logs[0]["message"] == "hello"

    def test_action_clear(self) -> None:
        from tianshangcad.mcp.tools.status import _log_buffer

        _log_buffer.clear()
        from tianshangcad.mcp.tools.status import log_event

        log_event("INFO", "test_source", "hello")
        result = cad_logs(LogsInput(logs=LogsClearParams()))
        assert result.status == "success"
        assert result.cleared == 1
        assert len(_log_buffer) == 0
