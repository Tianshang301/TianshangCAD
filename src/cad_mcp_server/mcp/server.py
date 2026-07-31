"""CAD MCP server main class."""

from __future__ import annotations

from mcp.server import MCPServer

from cad_mcp_server.mcp.tools._registry import get_registry

SERVER_NAME = "cad-mcp-server"
SERVER_TITLE = "CAD MCP Server"
SERVER_DESCRIPTION = (
    "JSON-driven CAD operations: files, geometry, layers, batch jobs, "
    "validation and metrics."
)


def build_server(version: str = "0.1.0") -> MCPServer:
    """Create an :class:`MCPServer` with every registered CAD tool."""
    server = MCPServer(
        name=SERVER_NAME,
        title=SERVER_TITLE,
        description=SERVER_DESCRIPTION,
        version=version,
    )
    for name, fn in get_registry().items():
        server.add_tool(fn, name=name)
    return server
