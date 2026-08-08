"""Boolean operation tools for combining geometry objects."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.utils.errors import CADError

_OPERATIONS: set[str] = {"union", "subtract", "intersect"}


class BooleanInput(BaseModel):
    """Input for a boolean operation."""

    operation: str = Field(
        ...,
        description="Operation: union, subtract, intersect",
        examples=["union"],
    )
    target_id: str = Field(..., description="Target object id (kept for subtract/union)")
    tool_id: str = Field(..., description="Tool object id (subtracted or combined)")
    new_id: str | None = Field(None, description="Optional id for the result object")
    layer: str = Field("0", description="Layer for the result object")


class ObjectBooleanInput(BaseModel):
    """Input for the aggregate object boolean tool."""

    operation: Literal["union", "subtract", "intersect"] = Field(
        ...,
        description="Boolean operation to perform",
        examples=["subtract"],
    )
    target_id: str = Field(..., description="Target object id")
    tool_ids: list[str] = Field(..., description="Tool object ids to combine")
    new_id: str | None = Field(None, description="Optional id for the result object")
    layer: str = Field("0", description="Layer for the result object")


class BooleanOutput(BaseModel):
    """Output of a two-object boolean operation."""

    result_id: str = Field(..., description="Id of the new mesh object")
    bbox: dict[str, list[float]] = Field(..., description="Bounding box of the result")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class ObjectBooleanOutput(BaseModel):
    """Output of the aggregate object boolean tool."""

    result_id: str = Field(..., description="Id of the resulting mesh object")
    bbox: dict[str, list[float]] = Field(..., description="Bounding box of the result")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


def _run_boolean(
    operation: str, target_id: str, tool_id: str, new_id: str, layer: str
) -> BooleanOutput:
    """Run a boolean operation against the current document."""
    if operation not in _OPERATIONS:
        return BooleanOutput(
            result_id="",
            bbox={"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
            status="error",
            message=f"Unknown boolean operation: {operation}",
        )
    doc = DocumentManager().get_current()
    result_id = doc.entities.boolean(
        operation=operation,
        target_id=target_id,
        tool_id=tool_id,
        object_id=new_id or None,
        layer=layer,
    )
    bbox = doc.entities.get_bbox(result_id)
    return BooleanOutput(result_id=result_id, bbox=bbox, status="success")


def _boolean_error(operation: str, target_id: str, tool_id: str, exc: CADError) -> BooleanOutput:
    """Build an error output."""
    return BooleanOutput(
        result_id="",
        bbox={"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
        status="error",
        message=str(exc),
    )


def cad_boolean_union(input: BooleanInput) -> BooleanOutput:
    """Union two objects into a single new mesh object.

    Combines ``target_id`` and ``tool_id`` into a new mesh entity while
    leaving the source objects unchanged. Requires the optional ``boolean``
    extra (``pip install -e '.[boolean]'``).
    """
    # Deprecated, merged into cad_object_boolean
    try:
        return _run_boolean(
            "union", input.target_id, input.tool_id, input.new_id or "", input.layer
        )
    except CADError as exc:
        return _boolean_error("union", input.target_id, input.tool_id, exc)


def cad_boolean_subtract(input: BooleanInput) -> BooleanOutput:
    """Subtract one object from another.

    Removes the material of ``tool_id`` from ``target_id`` and returns a new
    mesh object. The source objects are left untouched.
    """
    # Deprecated, merged into cad_object_boolean
    try:
        return _run_boolean(
            "subtract", input.target_id, input.tool_id, input.new_id or "", input.layer
        )
    except CADError as exc:
        return _boolean_error("subtract", input.target_id, input.tool_id, exc)


def cad_boolean_intersect(input: BooleanInput) -> BooleanOutput:
    """Intersect two objects.

    Returns the shared volume of ``target_id`` and ``tool_id`` as a new mesh
    object without modifying the sources.
    """
    # Deprecated, merged into cad_object_boolean
    try:
        return _run_boolean(
            "intersect", input.target_id, input.tool_id, input.new_id or "", input.layer
        )
    except CADError as exc:
        return _boolean_error("intersect", input.target_id, input.tool_id, exc)


def cad_object_boolean(input: ObjectBooleanInput) -> ObjectBooleanOutput:
    """Combine several objects with a boolean operation.

    Performs ``operation`` (union / subtract / intersect) of ``target_id`` with
    every id in ``tool_ids``. Subtract applies each tool in order; union and
    intersect combine them cumulatively. Requires the optional ``boolean``
    extra (``pip install -e '.[boolean]'``).
    """
    # Deprecated, merged into cad_object (action=boolean)
    try:
        if not input.tool_ids:
            return ObjectBooleanOutput(
                result_id="",
                bbox={"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
                status="error",
                message="At least one tool id is required",
            )
        if input.target_id in input.tool_ids:
            return ObjectBooleanOutput(
                result_id="",
                bbox={"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
                status="error",
                message="Target id must not also appear in tool_ids",
            )
        doc = DocumentManager().get_current()
        current_id = input.target_id
        for index, tool_id in enumerate(input.tool_ids):
            result_id = doc.entities.boolean(
                operation=input.operation,
                target_id=current_id,
                tool_id=tool_id,
                object_id=input.new_id if index == len(input.tool_ids) - 1 else None,
                layer=input.layer,
            )
            current_id = result_id
        bbox = doc.entities.get_bbox(current_id)
        return ObjectBooleanOutput(
            result_id=current_id,
            bbox=bbox,
            status="success",
            message=f"{input.operation} of {len(input.tool_ids)} tool(s) completed",
        )
    except CADError as exc:
        return ObjectBooleanOutput(
            result_id="",
            bbox={"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
            status="error",
            message=str(exc),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = []
