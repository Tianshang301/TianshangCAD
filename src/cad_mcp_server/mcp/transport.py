"""Transport layer: stdio and streamable HTTP."""

from __future__ import annotations

import asyncio

from mcp.server import MCPServer


def run_stdio(server: MCPServer) -> None:
    """Run the server over stdio (default for local AI agents)."""
    asyncio.run(server.run_stdio_async())


def run_http(
    server: MCPServer,
    host: str = "127.0.0.1",
    port: int = 8081,
    streamable_http_path: str = "/mcp",
) -> None:
    """Run the server over streamable HTTP."""
    asyncio.run(
        server.run_streamable_http_async(
            host=host,
            port=port,
            streamable_http_path=streamable_http_path,
        )
    )
