"""Parametric variable tools: set and list document variables."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.utils.errors import CADError


class VariableSetInput(BaseModel):
    """Input for setting a parametric variable."""

    name: str = Field(..., description="Variable name (letters/digits/underscore)")
    value: float | None = Field(None, description="Numeric value (omit when using expr)")
    unit: str = Field("", description="Unit suffix, e.g. mm")
    expr: str | None = Field(None, description="Arithmetic expression using other variables")


class VariableSetOutput(BaseModel):
    """Output for setting a variable."""

    name: str = Field(..., description="Variable name")
    value: float = Field(..., description="Evaluated value")
    unit: str = Field("", description="Unit suffix")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class VariableListInput(BaseModel):
    """Input for listing parametric variables."""


class VariableListOutput(BaseModel):
    """Output for listing variables."""

    variables: list[dict[str, Any]] = Field(default_factory=list, description="Variable records")
    count: int = Field(0, description="Number of variables")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


def cad_variable_set(input: VariableSetInput) -> VariableSetOutput:
    """Set a parametric variable in the current document.

    Creates or updates a named symbol with an optional unit and an optional
    arithmetic expression. The expression is evaluated eagerly so invalid
    references fail fast; ``{name}`` tokens in CLI draw arguments then
    interpolate the resolved value.
    """
    try:
        doc = DocumentManager().get_current()
        record = doc.variables.set(input.name, value=input.value, unit=input.unit, expr=input.expr)
        doc.touch()
        return VariableSetOutput(
            name=record.name,
            value=record.value,
            unit=record.unit,
            status="success",
        )
    except CADError as exc:
        return VariableSetOutput(
            name=input.name,
            value=0.0,
            unit=input.unit,
            status="error",
            message=str(exc),
        )


def cad_variable_list(input: VariableListInput) -> VariableListOutput:
    """List the parametric variables of the current document.

    Returns each variable's name, evaluated value, unit and expression so a
    caller can inspect the parameter table before using interpolation.
    """
    try:
        doc = DocumentManager().get_current()
        records = [
            {
                "name": record.name,
                "value": record.value,
                "unit": record.unit,
                "expr": record.expr,
            }
            for record in doc.variables.list()
        ]
        return VariableListOutput(variables=records, count=len(records), status="success")
    except CADError as exc:
        return VariableListOutput(status="error", message=str(exc))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_variable_set", cad_variable_set),
    ("cad_variable_list", cad_variable_list),
]
