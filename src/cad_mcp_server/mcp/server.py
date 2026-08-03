"""CAD MCP server main class."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, cast, get_type_hints

from mcp.server import MCPServer
from pydantic import BaseModel

from cad_mcp_server.mcp.tools._registry import get_registry
from cad_mcp_server.utils.metrics import track_operation

SERVER_NAME = "cad-mcp-server"
SERVER_TITLE = "CAD MCP Server"
SERVER_DESCRIPTION = (
    "JSON-driven CAD operations: files, geometry, layers, batch jobs, "
    "validation and metrics."
)


def _flatten_tool(fn: Callable[..., Any], name: str) -> Callable[..., Any]:
    """Expose a single ``input`` model's fields as top-level tool parameters.

    The CAD tools are written as ``def tool(input: T) -> Out``. MCP clients
    (e.g. Claude) work better when the arguments are flat, so this wraps each
    tool in a function whose ``__signature__`` is built from ``T.model_fields``.
    ``func_metadata`` honors ``inspect.signature``, so the resulting
    inputSchema is flat (no nested ``input``) while the callable still receives
    a validated ``T`` instance.
    """
    params = list(inspect.signature(fn).parameters.values())
    if len(params) != 1 or params[0].kind not in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    ):
        return fn
    hints = get_type_hints(fn)
    raw_model = hints.get(params[0].name)
    if raw_model is None or not isinstance(raw_model, type):
        return fn
    input_model = cast("type[BaseModel]", raw_model)
    return_annotation = hints.get("return", inspect.Signature.empty)

    def wrapped(**kwargs: Any) -> Any:
        return fn(input_model(**kwargs))

    flat_params: list[inspect.Parameter] = []
    for field_name, field in input_model.model_fields.items():
        alias = field.alias or field_name
        annotation = field.annotation
        if field.is_required():
            default = inspect.Parameter.empty
        else:
            default = field.get_default(call_default_factory=True)
        flat_params.append(
            inspect.Parameter(
                name=alias,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotation,
            )
        )

    wrapped.__name__ = name
    wrapped.__doc__ = fn.__doc__
    wrapped.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        flat_params, return_annotation=return_annotation
    )
    wrapped.__annotations__ = {
        **{param.name: param.annotation for param in flat_params},
        "return": return_annotation,
    }
    return wrapped


def _instrumented(fn: Callable[..., Any], name: str) -> Callable[..., Any]:
    """Wrap a tool callable with operation duration/count metrics."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with track_operation(name):
            return fn(*args, **kwargs)

    return wrapper


def build_server(version: str = "0.9.0") -> MCPServer:
    """Create an :class:`MCPServer` with every registered CAD tool."""
    server = MCPServer(
        name=SERVER_NAME,
        title=SERVER_TITLE,
        description=SERVER_DESCRIPTION,
        version=version,
    )
    for name, fn in get_registry().items():
        server.add_tool(_instrumented(_flatten_tool(fn, name), name), name=name)
    return server
