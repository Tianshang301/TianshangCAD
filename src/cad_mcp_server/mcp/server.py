"""CAD MCP server main class."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from mcp.server import MCPServer

from cad_mcp_server.mcp.tools._registry import get_registry
from cad_mcp_server.utils.metrics import track_operation

SERVER_NAME = "cad-mcp-server"
SERVER_TITLE = "CAD MCP Server"
SERVER_DESCRIPTION = (
    "JSON-driven CAD operations: files, geometry, layers, batch jobs, "
    "validation and metrics."
)


def _instrumented(fn: Callable[..., Any], name: str) -> Callable[..., Any]:
    """Wrap a tool callable with operation duration/count metrics."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with track_operation(name):
            return fn(*args, **kwargs)

    return wrapper


def build_server(version: str = "0.5.0") -> MCPServer:
    """Create an :class:`MCPServer` with every registered CAD tool."""
    server = MCPServer(
        name=SERVER_NAME,
        title=SERVER_TITLE,
        description=SERVER_DESCRIPTION,
        version=version,
    )
    for name, fn in get_registry().items():
        server.add_tool(_instrumented(fn, name), name=name)
    return server
