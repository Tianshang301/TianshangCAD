"""MCP server end-to-end integration tests over in-memory stdio streams."""

from __future__ import annotations

import asyncio
import contextlib
import json

from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from cad_mcp_server.mcp.server import build_server


def _call_tools(tool_arguments: list[tuple[str, dict]]) -> list[str]:
    """Run a client session against an in-memory server and call tools."""
    server = build_server()

    async def run() -> list[str]:
        async with create_client_server_memory_streams() as (
            client_streams,
            server_streams,
        ):
            async def serve() -> None:
                read, write = server_streams
                await server._lowlevel_server.run(
                    read,
                    write,
                    server._lowlevel_server.create_initialization_options(),
                )

            task = asyncio.create_task(serve())
            outputs: list[str] = []
            try:
                async with ClientSession(*client_streams) as session:
                    await session.initialize()
                    for name, arguments in tool_arguments:
                        result = await session.call_tool(name, arguments)
                        text = result.content[0].text
                        outputs.append(text)
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, BaseExceptionGroup):
                    await task
            return outputs

    return asyncio.run(run())


class TestMCPServer:
    """End-to-end MCP server tests."""

    def test_tool_discovery(self) -> None:
        server = build_server()
        async def list_tools() -> list[str]:
            async with create_client_server_memory_streams() as (
                client_streams,
                server_streams,
            ):
                async def serve() -> None:
                    read, write = server_streams
                    await server._lowlevel_server.run(
                        read,
                        write,
                        server._lowlevel_server.create_initialization_options(),
                    )

                task = asyncio.create_task(serve())
                try:
                    async with ClientSession(*client_streams) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        return sorted(tool.name for tool in tools.tools)
                finally:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, BaseExceptionGroup):
                        await task

        names = asyncio.run(list_tools())
        assert "cad_file_create" in names
        assert "cad_object_create" in names
        assert "cad_batch_execute" in names
        assert "cad_metrics_get" in names
        assert "cad_status_health" in names
        assert "cad_render_view" in names
        assert "cad_version_save" in names
        assert "cad_version_restore" in names
        assert "cad_nlp_command" in names
        assert "cad_view_3d_create" in names
        assert "cad_webgl_sync" in names
        assert "cad_boolean_union" in names
        assert "cad_boolean_subtract" in names
        assert "cad_boolean_intersect" in names
        assert "cad_file_export" in names
        assert "cad_file_import" in names
        assert "cad_variable_set" in names
        assert "cad_variable_list" in names
        assert "cad_object_boolean" in names
        assert "cad_constraint_add" in names
        assert "cad_constraint_remove" in names
        assert "cad_constraint_list" in names
        assert "cad_constraint_solve" in names
        assert "cad_assembly_create" in names
        assert "cad_assembly_add_part" in names
        assert "cad_assembly_add_subasm" in names
        assert "cad_assembly_add_mate" in names
        assert "cad_assembly_solve" in names
        assert "cad_assembly_bom" in names
        assert "cad_assembly_explode" in names
        assert "cad_drawing_create" in names
        assert "cad_drawing_add_view" in names
        assert "cad_drawing_add_section" in names
        assert "cad_drawing_add_dimension" in names
        assert "cad_drawing_add_tolerance" in names
        assert "cad_drawing_export" in names
        assert "cad_nlp_chat" in names
        assert "cad_feature_sweep" in names
        assert "cad_feature_loft" in names
        assert "cad_feature_fillet" in names
        assert "cad_feature_chamfer" in names
        assert "cad_feature_pattern_linear" in names
        assert "cad_feature_pattern_circular" in names
        assert "cad_feature_pattern_mirror" in names
        assert "cad_sim_mesh" in names
        assert "cad_sim_setup" in names
        assert "cad_sim_run" in names
        assert "cad_sim_result" in names
        assert "cad_sim_list" in names
        assert len(names) == 95

    def test_create_object_roundtrip(self) -> None:
        outputs = _call_tools(
            [
                (
                    "cad_file_create",
                    {"input": {"filename": "e2e.json", "unit": "mm"}},
                ),
                (
                    "cad_object_create",
                    {
                        "input": {
                            "type": "box",
                            "params": {"origin": [0, 0, 0], "dimensions": [2, 3, 4]},
                            "layer": "0",
                        }
                    },
                ),
                ("cad_metrics_get", {"input": {}}),
            ]
        )
        create_result = json.loads(outputs[0])
        assert create_result["status"] == "success"
        object_result = json.loads(outputs[1])
        assert object_result["bbox"]["max"] == [2.0, 3.0, 4.0]
        metrics = json.loads(outputs[2])
        assert metrics["objects"] == 1
        assert metrics["kinds"] == {"box": 1}

    def test_error_result_serialized(self) -> None:
        outputs = _call_tools(
            [
                ("cad_object_read", {"input": {"object_id": "missing"}}),
            ]
        )
        result = json.loads(outputs[0])
        assert result["status"] == "error"
        assert result["message"]

    def test_batch_execution_over_mcp(self) -> None:
        outputs = _call_tools(
            [
                (
                    "cad_batch_execute",
                    {
                        "input": {
                            "commands": [
                                {
                                    "tool": "cad_file_create",
                                    "arguments": {"filename": "b.json", "unit": "mm"},
                                },
                                {
                                    "tool": "cad_object_create",
                                    "arguments": {
                                        "type": "circle",
                                        "params": {"center": [0, 0, 0], "radius": 10},
                                        "layer": "0",
                                    },
                                },
                            ]
                        }
                    },
                )
            ]
        )
        result = json.loads(outputs[0])
        assert result["status"] == "success"
        assert result["success_count"] == 2
