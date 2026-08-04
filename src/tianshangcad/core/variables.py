"""Parametric variables and expression interpolation.

A document can hold a symbol table of named variables. Each variable has a
numeric ``value``, an optional ``unit`` and an optional arithmetic ``expr``
that is evaluated lazily (and may reference other variables). CLI draw
arguments support ``{name}`` brace interpolation against this table.
"""

from __future__ import annotations

import ast
import operator
import re
from collections.abc import Callable
from typing import Any

from tianshangcad.utils.errors import VariableError

_VARIABLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BRACE_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

_BINARY_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(expr: str, lookup: Callable[[str], float]) -> float:
    """Evaluate an arithmetic expression against a name resolver.

    Only numbers, arithmetic operators and bracketed names are allowed;
    arbitrary code execution is prevented by walking the AST manually.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise VariableError(
            f"Invalid expression {expr!r}: {exc.msg}", code="invalid_expr"
        ) from exc
    return _eval_node(tree.body, lookup)


def _eval_node(node: ast.AST, lookup: Callable[[str], float]) -> float:
    """Evaluate a single AST node against the name resolver."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        return float(lookup(node.id))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        bin_op = _BINARY_OPS[type(node.op)]
        left = _eval_node(node.left, lookup)
        right = _eval_node(node.right, lookup)
        return float(bin_op(left, right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        unary_op = _UNARY_OPS[type(node.op)]
        operand = _eval_node(node.operand, lookup)
        return float(unary_op(operand))
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, lookup)
    raise VariableError(
        f"Unsupported expression element: {type(node).__name__}", code="unsupported_expr"
    )


def _format_number(value: float) -> str:
    """Format a float without a trailing ``.0`` when integral."""
    if value.is_integer():
        return str(int(value))
    return str(value)


class VariableRecord:
    """A single named variable."""

    def __init__(
        self,
        name: str,
        value: float = 0.0,
        unit: str = "",
        expr: str | None = None,
    ) -> None:
        """Initialize a variable record."""
        if not _VARIABLE_PATTERN.match(name):
            raise VariableError(
                f"Invalid variable name {name!r}; expected letters/digits/underscore",
                code="invalid_name",
            )
        self.name = name
        self.value = float(value)
        self.unit = unit
        self.expr = expr

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "expr": self.expr,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariableRecord:
        """Reconstruct from a serialized dict."""
        return cls(
            name=str(data["name"]),
            value=float(data.get("value", 0.0)),
            unit=str(data.get("unit", "")),
            expr=data.get("expr"),
        )

    def __repr__(self) -> str:
        """Return a compact string representation."""
        return f"VariableRecord({self.name}={self.value}{self.unit})"


class VariableManager:
    """Symbol table for a document's parametric variables."""

    def __init__(self) -> None:
        """Initialize an empty variable table."""
        self._variables: dict[str, VariableRecord] = {}

    def set(
        self,
        name: str,
        value: float | None = None,
        unit: str = "",
        expr: str | None = None,
    ) -> VariableRecord:
        """Create or update a variable.

        ``value`` may be omitted when ``expr`` is provided (the value is then
        derived by evaluating the expression). Exactly one of ``value`` /
        ``expr`` must be supplied.
        """
        if value is None and expr is None:
            raise VariableError(
                f"Variable {name} requires a value or an expression",
                code="no_value",
            )
        if value is None:
            value = self._resolve_expr(str(expr), stack=(name,))
        record = VariableRecord(name=name, value=float(value), unit=unit, expr=expr)
        self._variables[name] = record
        return record

    def get(self, name: str) -> VariableRecord:
        """Return a variable or raise ``VariableError``."""
        record = self._variables.get(name)
        if record is None:
            raise VariableError(f"Variable not found: {name}", code="not_found")
        return record

    def resolve(self, name: str) -> float:
        """Return the evaluated numeric value of a variable.

        Variables with an ``expr`` are evaluated lazily against the current
        table; the raw ``value`` is returned otherwise. Expressions may
        reference other variables recursively; cycles raise ``VariableError``.
        """
        record = self.get(name)
        if record.expr is None:
            return record.value
        return self._resolve_expr(record.expr, stack=(name,))

    def _resolve_expr(self, expr: str, stack: tuple[str, ...]) -> float:
        """Evaluate ``expr`` with recursive variable resolution and cycle detection."""

        def _lookup(name: str) -> float:
            if name in stack:
                cycle = " -> ".join((*stack, name))
                raise VariableError(
                    f"Circular variable reference: {cycle}", code="circular_ref"
                )
            record = self._variables.get(name)
            if record is None:
                raise VariableError(
                    f"Undefined variable in expression: {name}", code="undefined_variable"
                )
            if record.expr is None:
                return record.value
            return self._resolve_expr(record.expr, stack=(*stack, name))

        return _safe_eval(expr, _lookup)

    def delete(self, name: str) -> None:
        """Delete a variable or raise ``VariableError``."""
        self.get(name)
        del self._variables[name]

    def list(self) -> list[VariableRecord]:
        """Return all variables in insertion order."""
        return list(self._variables.values())

    def interpolate(self, text: str) -> str:
        r"""Replace ``{name}`` tokens with the resolved variable values.

        Undefined names raise ``VariableError``. Literal braces may be escaped
        with a backslash (``\{``, ``\}``).
        """

        def _replace(match: re.Match[str]) -> str:
            return _format_number(self.resolve(match.group(1)))

        return _BRACE_PATTERN.sub(_replace, text)

    def snapshot(self) -> dict[str, Any]:
        """Return a deep snapshot for undo/redo."""
        return {"variables": [record.to_dict() for record in self._variables.values()]}

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Restore from a snapshot produced by :meth:`snapshot`."""
        self._variables = {
            data["name"]: VariableRecord.from_dict(data)
            for data in snapshot.get("variables", [])
        }
