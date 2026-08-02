"""Geometric constraint tools: add, remove, list and solve constraints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cad_mcp_server.core.constraint import ConstraintManager
from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.core.solver import apply_solution, solve_2d
from cad_mcp_server.utils.errors import CADError


class ConstraintAddInput(BaseModel):
    """Input for adding a geometric constraint."""

    type: str = Field(..., description="Constraint type (parallel, tangent, ...)")
    entities: list[str] = Field(..., description="Entity ids referenced by the constraint")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Type-specific params (distance, angle, point_a, point_b)"
    )


class ConstraintAddOutput(BaseModel):
    """Output for adding a constraint."""

    constraint_id: str = Field(..., description="Constraint unique identifier")
    type: str = Field(..., description="Constraint type")
    entities: list[str] = Field(default_factory=list, description="Referenced entity ids")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class ConstraintRemoveInput(BaseModel):
    """Input for removing a constraint."""

    constraint_id: str = Field(..., description="Constraint id to remove")


class ConstraintRemoveOutput(BaseModel):
    """Output for removing a constraint."""

    constraint_id: str = Field(..., description="Removed constraint id")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class ConstraintListInput(BaseModel):
    """Input for listing constraints."""


class ConstraintListOutput(BaseModel):
    """Output for listing constraints."""

    constraints: list[dict[str, Any]] = Field(
        default_factory=list, description="Constraint records"
    )
    count: int = Field(0, description="Number of constraints")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class ConstraintSolveInput(BaseModel):
    """Input for solving the constraint system."""

    max_iterations: int = Field(100, description="Solver iteration cap", ge=1, le=10000)
    tolerance: float = Field(1e-8, description="Convergence tolerance", gt=0)


class ConstraintSolveOutput(BaseModel):
    """Output for solving the constraint system."""

    converged: bool = Field(..., description="Whether the solver converged")
    iterations: int = Field(0, description="Solver iterations used")
    residual: float = Field(0.0, description="Final residual norm")
    moved_entities: list[str] = Field(default_factory=list, description="Entities the solver moved")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


def _require_constraints() -> ConstraintManager:
    return DocumentManager().get_current().constraints


def cad_constraint_add(input: ConstraintAddInput) -> ConstraintAddOutput:
    """Add a geometric constraint between entities.

    Creates a constraint of the given type over the referenced entities.
    Constraints are solved by ``cad_constraint_solve``, which moves geometry
    to satisfy them. Supported types: fixed, coincident, parallel,
    perpendicular, tangent, on_line, midpoint, distance, angle.
    """
    try:
        manager = _require_constraints()
        record = manager.add(input.type, input.entities, input.params)
        return ConstraintAddOutput(
            constraint_id=record.id,
            type=record.type.value,
            entities=record.entities,
            status="success",
            message=f"Added {record.type.value} constraint {record.id}",
        )
    except CADError as exc:
        return ConstraintAddOutput(
            constraint_id="",
            type=input.type,
            entities=list(input.entities),
            status="error",
            message=str(exc),
        )


def cad_constraint_remove(input: ConstraintRemoveInput) -> ConstraintRemoveOutput:
    """Remove a geometric constraint from the document."""
    try:
        _require_constraints().remove(input.constraint_id)
        return ConstraintRemoveOutput(
            constraint_id=input.constraint_id, status="success", message="Constraint removed"
        )
    except CADError as exc:
        return ConstraintRemoveOutput(
            constraint_id=input.constraint_id, status="error", message=str(exc)
        )


def cad_constraint_list(input: ConstraintListInput) -> ConstraintListOutput:
    """List the geometric constraints of the current document."""
    try:
        records = _require_constraints().list()
        return ConstraintListOutput(
            constraints=[record.to_dict() for record in records],
            count=len(records),
            status="success",
        )
    except CADError as exc:
        return ConstraintListOutput(status="error", message=str(exc))


def cad_constraint_solve(input: ConstraintSolveInput) -> ConstraintSolveOutput:
    """Solve the document's constraint system.

    Runs the damped Gauss-Newton solver over the constrained line/circle
    entities. Entities referenced by a ``fixed`` constraint stay anchored;
    all other constrained entities are moved to satisfy the constraints.
    Solved geometry is written back to the document.
    """
    try:
        doc = DocumentManager().get_current()
        constraints = doc.constraints.list()
        if not constraints:
            return ConstraintSolveOutput(
                converged=True,
                iterations=0,
                residual=0.0,
                moved_entities=[],
                status="success",
                message="No constraints to solve",
            )
        records = {
            entity_id: doc.entities.get(entity_id)
            for constraint in constraints
            for entity_id in constraint.entities
        }
        result = solve_2d(
            records,
            constraints,
            max_iterations=input.max_iterations,
            tolerance=input.tolerance,
        )
        if result.converged:
            apply_solution(doc.entities, result)
            doc.touch()
        return ConstraintSolveOutput(
            converged=result.converged,
            iterations=result.iterations,
            residual=result.residual_norm,
            moved_entities=sorted(result.updates),
            status="success" if result.converged else "error",
            message=result.message,
        )
    except CADError as exc:
        return ConstraintSolveOutput(
            converged=False, iterations=0, residual=0.0, moved_entities=[],
            status="error", message=str(exc),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_constraint_add", cad_constraint_add),
    ("cad_constraint_remove", cad_constraint_remove),
    ("cad_constraint_list", cad_constraint_list),
    ("cad_constraint_solve", cad_constraint_solve),
]
