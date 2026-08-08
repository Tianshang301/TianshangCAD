"""CAD MCP server main class."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from functools import wraps
from typing import Annotated, Any, cast, get_type_hints

from mcp.server import MCPServer
from mcp.types import RequestParams, ToolAnnotations
from pydantic import BaseModel, Field

from tianshangcad.mcp.security import is_destructive, is_read_only
from tianshangcad.mcp.tools._registry import get_registry
from tianshangcad.utils.metrics import track_operation

SERVER_NAME = "tianshangcad-server"
SERVER_TITLE = "TianshangCAD"
SERVER_DESCRIPTION = (
    "JSON-driven CAD operations: files, geometry, layers, batch jobs, "
    "validation and metrics."
)


def _annotate_field(annotation: Any, field_kwargs: dict[str, Any]) -> Any:
    """Wrap ``annotation`` in ``Annotated[...]`` with the given Field kwargs.

    Kept as a separate function so mypy sees a plain ``Any`` return instead
    of fighting the ``Annotated`` special form in the loop body.
    """
    return Annotated[annotation, Field(**field_kwargs)]


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
        # Carry Pydantic field metadata (description / examples / extra
        # schema keywords) into the flat signature. ``func_metadata`` turns
        # each annotated parameter into a Field, so without this every tool
        # argument loses its description in ``tools/list``.
        field_kwargs: dict[str, Any] = {}
        if field.description:
            field_kwargs["description"] = field.description
        if field.examples:
            field_kwargs["examples"] = list(field.examples)
        if field.json_schema_extra:
            field_kwargs["json_schema_extra"] = field.json_schema_extra
        if field_kwargs:
            annotation = _annotate_field(annotation, field_kwargs)
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


#: Tools that create fresh identifiers on every call and therefore are NOT
#: idempotent even though they are write operations. With the aggregate
#: surface this is expressed per tool name: a tool is flagged non-idempotent
#: when any of its sub-actions creates fresh identifiers (create / open /
#: schedule / sync / copy / boolean). Read-only aggregates stay idempotent.
_NON_IDEMPOTENT = frozenset(
    {
        "cad_file",
        "cad_object",
        "cad_layer",
        "cad_view",
        "cad_assembly",
        "cad_drawing",
        "cad_feature",
        "cad_sim",
        "cad_collab",
        "cad_batch",
        "cad_variable",
        "cad_version",
        "cad_constraint",
        "cad_nlp",
    }
)


def _tool_annotations(name: str) -> ToolAnnotations:
    """Derive MCP tool hints from the permission table and operation kind.

    Hints let clients (and registry scorecards) classify a tool without
    reading its full description: read_only_hint for queries, destructive_hint
    for deletions, and idempotent_hint for calls safe to retry.
    """
    read_only = is_read_only(name)
    destructive = is_destructive(name)
    if name == "cad_batch":
        # ADMIN aggregate covering schedule/cancel in addition to read-only
        # sub-actions; it can mutate the job store.
        destructive = True
    if read_only:
        idempotent = True
    elif name in _NON_IDEMPOTENT:
        idempotent = False
    else:
        # set-like updates (update/save/close/transform/delete) are safe to
        # retry; create/schedule style operations are handled above.
        idempotent = True
    return ToolAnnotations(
        read_only_hint=read_only,
        destructive_hint=destructive,
        idempotent_hint=idempotent,
    )


def build_server(version: str = "0.9.0") -> MCPServer:
    """Create an :class:`MCPServer` with every registered CAD tool."""
    server = MCPServer(
        name=SERVER_NAME,
        title=SERVER_TITLE,
        description=SERVER_DESCRIPTION,
        version=version,
    )
    for name, fn in get_registry().items():
        server.add_tool(
            _instrumented(_flatten_tool(fn, name), name),
            name=name,
            annotations=_tool_annotations(name),
        )
    _install_tool_search(server)
    return server


# ---------------------------------------------------------------------------
# Tool Search (tools/list query filtering, SEP-1821)
# ---------------------------------------------------------------------------

#: Tokens ignored when ranking results so ``measure`` matches ``cad_measure``
#: rather than every tool mentioning the word in its description.
_STOPWORDS = frozenset({"tool", "tools", "cad", "the", "a", "an", "and"})


class ListToolsSearchParams(RequestParams):
    """Params for ``tools/list`` with an optional ``query`` filter."""

    query: str | None = Field(
        None, description="Return only tools whose name or description match"
    )
    cursor: str | None = Field(None, description="Pagination cursor (unsupported)")


def _query_tokens(query: str) -> list[str]:
    """Lower-cased, whitespace-split query tokens minus stopwords."""
    tokens = [token.lower() for token in re.split(r"[\s_,./-]+", query)]
    return [token for token in tokens if token and token not in _STOPWORDS]


def _score_tool(name: str, description: str, tokens: list[str]) -> int:
    """Rank a tool against the query tokens.

    Name substring matches score highest (whole-word prefix first), then
    description substring matches. ``0`` means no match.
    """
    if not tokens:
        return 1
    name_lower = name.lower()
    desc_lower = description.lower()
    score = 0
    for token in tokens:
        if name_lower == token:
            score += 100
        elif name_lower.startswith(token):
            score += 60
        elif token in name_lower:
            score += 40
        elif token in desc_lower:
            score += 10
        else:
            return 0
    return score


def _list_tools_result(tools: list[Any]) -> Any:
    """Build the ``ListToolsResult`` for the given tools."""
    from mcp.types import ListToolsResult

    return ListToolsResult(tools=tools)


def _install_tool_search(server: MCPServer) -> None:
    """Replace the default ``tools/list`` handler with a query-filtering one.

    The MCP SDK validates request params against a model before invoking a
    handler, and its built-in ``PaginatedRequestParams`` drops unknown fields
    such as ``query``. We therefore register a handler whose params model
    carries ``query``; the handler closes over ``server`` to list + filter.
    """

    async def handler(ctx: Any, params: ListToolsSearchParams) -> Any:
        del ctx
        tools = await server.list_tools()
        query = (params.query or "").strip()
        if not query:
            return _list_tools_result(tools)
        tokens = _query_tokens(query)
        if not tokens:
            # A query made only of stopwords matches nothing.
            return _list_tools_result([])
        scored = sorted(
            ((_score_tool(tool.name, tool.description or "", tokens), tool) for tool in tools),
            key=lambda pair: (-pair[0], pair[1].name),
        )
        matched = [tool for score, tool in scored if score > 0]
        return _list_tools_result(matched)

    server._lowlevel_server.add_request_handler(
        "tools/list", ListToolsSearchParams, handler
    )
