"""CAD MCP server main class."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Annotated, Any, cast, get_type_hints

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from tianshangcad.mcp.security import TOOL_PERMISSIONS, PermissionLevel
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
#: idempotent even though they are write operations. Tools not listed here
#: that are non-read-only default to idempotent when they perform set-like
#: updates (update/save/delete/transform) and to non-idempotent when they
#: are create/schedule/sync operations. Read-only tools are always
#: idempotent.
_NON_IDEMPOTENT = frozenset(
    {
        "cad_file_create",
        "cad_file_open",
        "cad_object_create",
        "cad_object_copy",
        "cad_object_boolean",
        "cad_layer_create",
        "cad_assembly_create",
        "cad_assembly_add_part",
        "cad_assembly_add_subasm",
        "cad_assembly_add_mate",
        "cad_drawing_create",
        "cad_drawing_add_view",
        "cad_drawing_add_section",
        "cad_drawing_add_dimension",
        "cad_drawing_add_tolerance",
        "cad_feature_sweep",
        "cad_feature_loft",
        "cad_feature_fillet",
        "cad_feature_chamfer",
        "cad_feature_pattern_linear",
        "cad_feature_pattern_circular",
        "cad_feature_pattern_mirror",
        "cad_view_3d_create",
        "cad_sim_setup",
        "cad_sim_mesh",
        "cad_collab_session",
        "cad_collab_branch",
        "cad_collab_annotation",
        "cad_collab_sync",
        "cad_variable",
        "cad_version",
        "cad_constraint",
    }
)


def _tool_annotations(name: str) -> ToolAnnotations:
    """Derive MCP tool hints from the permission table and operation kind.

    Hints let clients (and registry scorecards) classify a tool without
    reading its full description: read_only_hint for queries, destructive_hint
    for deletions, and idempotent_hint for calls safe to retry.
    """
    level = TOOL_PERMISSIONS.get(name, PermissionLevel.STANDARD)
    read_only = level == PermissionLevel.READ_ONLY
    destructive = level == PermissionLevel.DESTRUCTIVE
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
    return server
