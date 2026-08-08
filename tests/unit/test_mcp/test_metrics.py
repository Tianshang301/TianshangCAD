"""Tests for Prometheus metrics instrumentation."""

from __future__ import annotations

import pytest

from tianshangcad.mcp.server import build_server
from tianshangcad.mcp.tools._registry import get_registry
from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from tianshangcad.utils.metrics import (
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
        assert "cad_object" in get_registry()
        assert "cad_view" in get_registry()

    def test_build_server_registers_tools(self) -> None:
        from tianshangcad.mcp.server import SERVER_NAME

        server = build_server()
        assert server.name == SERVER_NAME
        assert "cad_object" in get_registry()
        assert "cad_render" in get_registry()

    def test_flattened_schema_keeps_field_descriptions(self) -> None:
        """Flattened tool input schemas must preserve Pydantic field docs.

        `_flatten_tool` builds a flat signature from the input model; without
        carrying the field descriptions across, `tools/list` publishes bare
        type-only schemas and registry scorecards cannot see any parameter
        documentation.
        """
        from mcp.server.mcpserver.utilities.func_metadata import func_metadata

        from tianshangcad.mcp.server import _flatten_tool
        from tianshangcad.mcp.tools.collab import cad_collab_history
        from tianshangcad.mcp.tools.crud import cad_layer_update

        flattened = _flatten_tool(cad_layer_update, "cad_layer_update")
        schema = func_metadata(flattened).arg_model.model_json_schema()
        props = schema["properties"]
        assert "description" in props["name"]
        assert "description" in props["locked"]

        collab_flattened = _flatten_tool(cad_collab_history, "cad_collab_history")
        collab_schema = func_metadata(collab_flattened).arg_model.model_json_schema()
        assert "description" in collab_schema["properties"]["session_id"]

    def test_tool_annotations_hints_published(self) -> None:
        """Every tool publishes read_only/destructive/idempotent hints.

        Behavior-transparency hints let clients and registry scorecards
        classify tools without parsing the free-text description.
        """
        import asyncio

        from tianshangcad.mcp.server import build_server

        async def collect() -> dict[str, tuple[bool | None, bool | None, bool | None]]:
            server = build_server()
            result = await server.list_tools()
            tools = result if isinstance(result, list) else result.tools
            out: dict[str, tuple[bool | None, bool | None, bool | None]] = {}
            for t in tools:
                a = t.annotations
                out[t.name] = (a.read_only_hint, a.destructive_hint, a.idempotent_hint)
            return out

        hints = asyncio.run(collect())
        assert len(hints) >= 19
        # read-only aggregates
        assert hints["cad_validate"][0] is True
        assert hints["cad_validate"][2] is True
        assert hints["cad_measure"][0] is True
        assert hints["cad_json"][0] is True
        # aggregates containing destructive sub-actions
        assert hints["cad_object"][1] is True
        assert hints["cad_layer"][1] is True
        assert hints["cad_file"][1] is True
        assert hints["cad_status"][1] is True  # logs_clear is destructive
        # non-idempotent aggregates (create/copy/boolean sub-actions)
        assert hints["cad_object"][2] is False
        assert hints["cad_file"][2] is False
        assert hints["cad_assembly"][2] is False

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
        from tianshangcad.mcp.server import _instrumented

        def sample_tool(payload) -> dict[str, str]:
            return {"status": "ok"}

        wrapped = _instrumented(sample_tool, "cad_instrumented_tool")
        assert wrapped({"x": 1}) == {"status": "ok"}
        samples = OPERATION_COUNT.collect()[0].samples
        success = [
            s for s in samples if s.labels.get("tool_name") == "cad_instrumented_tool"
        ]
        assert success
