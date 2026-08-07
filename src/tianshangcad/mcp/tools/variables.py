"""Parametric variable tools: set and list document variables.

The public surface is the single aggregate ``cad_variable`` tool. The
legacy ``cad_variable_set`` / ``cad_variable_list`` functions remain
importable but are no longer registered.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

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
    """Set a parametric variable in the current document."""
    # Deprecated, merged into cad_variable (action=set)
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
    """List the parametric variables of the current document."""
    # Deprecated, merged into cad_variable (action=list)
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
# Aggregate cad_variable tool
# ---------------------------------------------------------------------------


class VariableSetParams(BaseModel):
    """Set a parametric variable."""

    action: Literal["set"] = "set"
    name: str = Field(..., description="Variable name (letters/digits/underscore)")
    value: float | None = Field(None, description="Numeric value (omit when using expr)")
    unit: str = Field("", description="Unit suffix, e.g. mm")
    expr: str | None = Field(None, description="Arithmetic expression using other variables")


class VariableListParams(BaseModel):
    """List parametric variables."""

    action: Literal["list"] = "list"


VariableActionParams = Annotated[
    VariableSetParams | VariableListParams, Field(discriminator="action")
]


class VariableInput(BaseModel):
    """Input for the aggregate variable tool.

    聚合参数变量工具。``action`` 为 ``set``（设置/更新变量，支持 value/unit/
    expr）或 ``list``（列出全部变量）。
    """

    variable: VariableActionParams = Field(default_factory=VariableListParams)


class VariableOutput(BaseModel):
    """Output of the aggregate variable tool."""

    action: str = Field(..., description="Variable action")
    variables: list[dict[str, Any]] = Field(default_factory=list, description="Variable records")
    count: int = Field(0, description="Number of variables")
    name: str | None = Field(None, description="Variable name")
    value: float | None = Field(None, description="Evaluated value")
    unit: str = Field("", description="Unit suffix")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


def cad_variable(input: VariableInput) -> VariableOutput:
    """Set or list parametric variables in the current document.

    按 ``action`` 设置（set）或列出（list）当前文档的参数变量。
    """
    params = input.variable
    try:
        doc = DocumentManager().get_current()
        if params.action == "set":
            record = doc.variables.set(
                params.name, value=params.value, unit=params.unit, expr=params.expr
            )
            doc.touch()
            return VariableOutput(
                action="set",
                name=record.name,
                value=record.value,
                unit=record.unit,
                status="success",
            )
        records = [
            {
                "name": record.name,
                "value": record.value,
                "unit": record.unit,
                "expr": record.expr,
            }
            for record in doc.variables.list()
        ]
        return VariableOutput(
            action="list", variables=records, count=len(records), status="success"
        )
    except CADError as exc:
        return VariableOutput(action=params.action, status="error", message=str(exc))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_variable", cad_variable),
]
