"""Tests for Prometheus metrics instrumentation."""

from __future__ import annotations

import pytest

from cad_mcp_server.mcp.server import build_server
from cad_mcp_server.mcp.tools._registry import get_registry
from cad_mcp_server.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from cad_mcp_server.utils.metrics import (
    ENTITY_COUNT,
    OPERATION_COUNT,
    OPERATION_DURATION,
    metrics_endpoint,
    observe_entity,
    observe_error,
    observe_operation,
    track_operation,
)


def _sample_metrics(text: str) -> dict[str, int]:
    """Extract metric name -> sample count pairs from Prometheus output."""
    result: dict[str, int] = {}
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        name = line.split("{")[0].split(" ")[0]
        result[name] = result.get(name, 0) + 1
    return result


class TestMetricInstruments:
    """Unit behaviour of the metric instruments."""

    def test_observe_operation_counts(self) -> None:
        observe_operation("cad_test_tool")
        metric = OPERATION_COUNT.labels(tool_name="cad_test_tool", status="success")
        assert metric._value.get() >= 1  # type: ignore[attr-defined]

    def test_observe_error_counts(self) -> None:
        observe_error("cad_test_tool")
        metric = OPERATION_COUNT.labels(tool_name="cad_test_tool", status="error")
        assert metric._value.get() >= 1  # type: ignore[attr-defined]

    def test_observe_entity_counts(self) -> None:
        observe_entity("box")
        metric = ENTITY_COUNT.labels(entity_type="box")
        assert metric._value.get() >= 1  # type: ignore[attr-defined]

    def test_track_operation_measures_duration(self) -> None:
        with track_operation("cad_tracked"):
            pass
        samples = OPERATION_DURATION.collect()[0].samples
        names = [sample.labels.get("tool_name") for sample in samples]
        assert "cad_tracked" in names

    def test_track_operation_counts_error_on_raise(self) -> None:
        with pytest.raises(RuntimeError), track_operation("cad_tracked_fail"):
            raise RuntimeError("boom")
        metric = OPERATION_COUNT.labels(tool_name="cad_tracked_fail", status="error")
        assert metric._value.get() >= 1  # type: ignore[attr-defined]


class TestMetricsEndpoint:
    """/metrics endpoint payload."""

    def test_endpoint_returns_prometheus_format(self) -> None:
        from starlette.responses import Response

        response = metrics_endpoint(object())
        assert isinstance(response, Response)
        assert "text/plain" in response.media_type
        assert b"cad_operations_total" in response.body
        assert b"cad_operation_duration_seconds" in response.body
        assert b"cad_entities_total" in response.body


class TestServerInstrumentation:
    """Tool dispatch instrumentation through build_server."""

    def test_registry_has_all_tools(self) -> None:
        assert "cad_object_create" in get_registry()
        assert "cad_view_3d_create" in get_registry()

    def test_build_server_registers_tools(self) -> None:
        from cad_mcp_server.mcp.server import SERVER_NAME

        server = build_server()
        assert server.name == SERVER_NAME
        assert "cad_object_create" in get_registry()
        assert "cad_webgl_sync" in get_registry()

    def test_instrumented_tool_records_metrics(self) -> None:
        cad_file_create(FileCreateInput(filename="m.json"))
        cad_object_create(
            ObjectCreateInput(
                type="box",
                params={"origin": [0, 0, 0], "dimensions": [10, 5, 2]},
                layer="0",
            )
        )
        entity_samples = ENTITY_COUNT.collect()[0].samples
        box_samples = [s for s in entity_samples if s.labels.get("entity_type") == "box"]
        assert box_samples

    def test_instrumented_wrapper_records_operation(self) -> None:
        from cad_mcp_server.mcp.server import _instrumented

        def sample_tool(payload) -> dict[str, str]:
            return {"status": "ok"}

        wrapped = _instrumented(sample_tool, "cad_instrumented_tool")
        assert wrapped({"x": 1}) == {"status": "ok"}
        samples = OPERATION_COUNT.collect()[0].samples
        success = [
            s for s in samples if s.labels.get("tool_name") == "cad_instrumented_tool"
        ]
        assert success
