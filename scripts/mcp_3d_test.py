"""Drive the real tianshangcad-server over stdio to build a simple 3D scene and save it.

Usage: python scripts/mcp_3d_test.py [output.json]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def call(session: ClientSession, name: str, arguments: dict) -> dict:
    """Call an MCP tool, print its raw output and return the parsed JSON."""
    result = await session.call_tool(name, arguments)
    text = result.content[0].text
    print(f"[{name}] {text}")
    return json.loads(text)


async def main() -> None:
    """Create a 3D scene via MCP and save it to a JSON file."""
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/demo/3d_test_scene.json")
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tianshangcad", "--transport", "stdio"],
    )
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        print(f"[tools] {len(tools.tools)} registered")

        await call(
            session,
            "cad_file",
            {"file": {"action": "create", "filename": "3d_test.json", "unit": "mm"}},
        )
        await call(
            session,
            "cad_object",
            {
                "object": {
                    "action": "create",
                    "type": "box",
                    "params": {"origin": [0, 0, 0], "dimensions": [100, 60, 20]},
                    "layer": "Body",
                    "properties": {"color": "#FF6600"},
                }
            },
        )
        await call(
            session,
            "cad_object",
            {
                "object": {
                    "action": "create",
                    "type": "cylinder",
                    "params": {"origin": [50, 30, 20], "radius": 25, "height": 40},
                    "layer": "Shaft",
                }
            },
        )
        await call(
            session,
            "cad_object",
            {
                "object": {
                    "action": "create",
                    "type": "sphere",
                    "params": {"center": [0, 0, 0], "radius": 15},
                    "layer": "Decor",
                }
            },
        )

        exported = await call(session, "cad_json", {"params": {"action": "export_scene"}})
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(exported["content"], encoding="utf-8")
        print(f"[saved] {output} ({output.stat().st_size} bytes)")

        await call(session, "cad_file", {"file": {"action": "save", "path": str(output)}})


if __name__ == "__main__":
    asyncio.run(main())
