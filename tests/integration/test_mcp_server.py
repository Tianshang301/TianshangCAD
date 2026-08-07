"""MCP server end-to-end integration tests over in-memory stdio streams."""

from __future__ import annotations

import asyncio
import contextlib
import json

from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from tianshangcad.mcp.server import build_server


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
        assert "cad_batch" in names
        assert "cad_metrics_get" in names
        assert "cad_status" in names
        assert "cad_logs" in names
        assert "cad_render" in names
        assert "cad_version" in names
        assert "cad_nlp_command" in names
        assert "cad_view_3d_create" in names
        assert "cad_object_boolean" in names
        assert "cad_file_io" in names
        assert "cad_variable" in names
        assert "cad_constraint" in names
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
        assert "cad_collab_session" in names
        assert "cad_collab_branch" in names
        assert "cad_collab_annotation" in names
        assert "cad_collab_presence" in names
        assert "cad_collab_history" in names
        assert "cad_collab_resolve" in names
        assert "cad_collab_permission" in names
        assert "cad_collab_sync" in names
        assert "cad_measure_distance" in names
        assert "cad_measure_area" in names
        assert "cad_object_copy" in names
        assert "cad_object_transform" in names
        assert "cad_file_delete" in names
        assert "cad_assembly_remove_part" in names
        assert "cad_drawing_delete" in names
        assert "cad_sim_delete" in names
        assert len(names) == 77

    def test_flat_tool_schemas(self) -> None:
        """Tools expose flat input schemas (no nested ``input`` wrapper)."""
        server = build_server()

        async def list_schemas() -> dict[str, dict]:
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
                        return {tool.name: tool.input_schema for tool in tools.tools}
                finally:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, BaseExceptionGroup):
                        await task

        schemas = asyncio.run(list_schemas())
        for name in ("cad_file_create", "cad_object_create", "cad_batch"):
            props = schemas[name]["properties"]
            assert "input" not in props
        assert "filename" in schemas["cad_file_create"]["properties"]
        assert "type" in schemas["cad_object_create"]["properties"]
        assert "batch" in schemas["cad_batch"]["properties"]

    def test_create_object_roundtrip(self) -> None:
        outputs = _call_tools(
            [
                (
                    "cad_file_create",
                    {"filename": "e2e.json", "unit": "mm"},
                ),
                (
                    "cad_object_create",
                    {
                        "type": "box",
                        "params": {"origin": [0, 0, 0], "dimensions": [2, 3, 4]},
                        "layer": "0",
                    },
                ),
                ("cad_metrics_get", {}),
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
                ("cad_object_read", {"object_id": "missing"}),
            ]
        )
        result = json.loads(outputs[0])
        assert result["status"] == "error"
        assert result["message"]

    def test_batch_execution_over_mcp(self) -> None:
        outputs = _call_tools(
            [
                (
                    "cad_batch",
                    {
                        "batch": {
                            "action": "execute",
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
                            ],
                        }
                    },
                )
            ]
        )
        result = json.loads(outputs[0])
        assert result["status"] == "success"
        assert result["success_count"] == 2
