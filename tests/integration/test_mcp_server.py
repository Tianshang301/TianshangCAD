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
        expected = {
            "cad_file",
            "cad_object",
            "cad_layer",
            "cad_json",
            "cad_measure",
            "cad_validate",
            "cad_nlp",
            "cad_view",
            "cad_render",
            "cad_assembly",
            "cad_drawing",
            "cad_feature",
            "cad_sim",
            "cad_collab",
            "cad_status",
            "cad_batch",
            "cad_constraint",
            "cad_variable",
            "cad_version",
        }
        assert set(names) == expected
        assert len(names) == 19

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
        for name in ("cad_file", "cad_object", "cad_batch"):
            props = schemas[name]["properties"]
            assert "input" not in props
        assert "file" in schemas["cad_file"]["properties"]
        assert "object" in schemas["cad_object"]["properties"]
        assert "batch" in schemas["cad_batch"]["properties"]

        # Pydantic field descriptions must survive flattening so clients
        # (and registry scorecards like Glama) see parameter documentation.
        assert "description" in schemas["cad_file"]["properties"]["file"]
        assert "description" in schemas["cad_object"]["properties"]["object"]
        assert "description" in schemas["cad_layer"]["properties"]["layer"]
        assert "description" in schemas["cad_collab"]["properties"]["collab"]
        assert "description" in schemas["cad_variable"]["properties"]["variable"]
        assert "description" in schemas["cad_batch"]["properties"]["batch"]

    def test_create_object_roundtrip(self) -> None:
        outputs = _call_tools(
            [
                (
                    "cad_file",
                    {"file": {"action": "create", "filename": "e2e.json", "unit": "mm"}},
                ),
                (
                    "cad_object",
                    {
                        "object": {
                            "action": "create",
                            "type": "box",
                            "params": {"origin": [0, 0, 0], "dimensions": [2, 3, 4]},
                            "layer": "0",
                        }
                    },
                ),
                ("cad_validate", {"query": {"action": "metrics"}}),
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
                (
                    "cad_object",
                    {"object": {"action": "read", "object_id": "missing"}},
                ),
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
                                    "tool": "cad_file",
                                    "arguments": {
                                        "file": {
                                            "action": "create",
                                            "filename": "b.json",
                                            "unit": "mm",
                                        }
                                    },
                                },
                                {
                                    "tool": "cad_object",
                                    "arguments": {
                                        "object": {
                                            "action": "create",
                                            "type": "circle",
                                            "params": {"center": [0, 0, 0], "radius": 10},
                                            "layer": "0",
                                        }
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

    def test_tool_search_query_filter(self) -> None:
        """tools/list honors an optional query filter (SEP-1821)."""
        server = build_server()
        from tianshangcad.mcp.server import ListToolsSearchParams

        entry = server._lowlevel_server.get_request_handler("tools/list")
        assert entry is not None

        async def run() -> tuple[list[str], list[str], list[str], int]:
            no_query = await entry.handler(None, ListToolsSearchParams())
            measure = await entry.handler(None, ListToolsSearchParams(query="measure"))
            layer = await entry.handler(None, ListToolsSearchParams(query="layer"))
            none = await entry.handler(None, ListToolsSearchParams(query="zzz_nope"))
            return (
                [t.name for t in no_query.tools],
                [t.name for t in measure.tools],
                [t.name for t in layer.tools],
                len(none.tools),
            )

        all_names, measure_names, layer_names, none_count = asyncio.run(run())
        assert len(all_names) == 19
        assert measure_names[0] == "cad_measure"
        assert "cad_measure" in measure_names
        assert layer_names[0] == "cad_layer"
        assert "cad_layer" in layer_names
        assert none_count == 0
