"""Simulation tools: mesh, setup, run, result and list.

Simulations are managed by :class:`~tianshangcad.core.simulation.SimulationManager`.
FEA (CalculiX) and rigid-body kinematics (PyBullet) backends are optional
and report a friendly ``requires_sim`` error when their engines are absent;
meshing is pure Python and always available. ``cad_sim_run`` may also be
scheduled as an async batch job via ``cad_batch_schedule``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tianshangcad.core.simulation import SimulationManager
from tianshangcad.utils.errors import CADError


class SimMeshInput(BaseModel):
    """Input for meshing an entity."""

    entity_id: str = Field(..., description="Entity id to mesh")
    nx: int = Field(4, description="Divisions along X", ge=1, le=100)
    ny: int = Field(4, description="Divisions along Y", ge=1, le=100)
    nz: int = Field(4, description="Divisions along Z", ge=1, le=100)


class SimMeshOutput(BaseModel):
    """Output for a mesh operation."""

    node_count: int = Field(0, description="Number of mesh nodes")
    element_count: int = Field(0, description="Number of elements")
    element_type: str = Field("", description="Element type (hexa8)")
    bbox: dict[str, list[float]] = Field(default_factory=dict, description="Meshed bounding box")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class SimSetupInput(BaseModel):
    """Input for registering a simulation."""

    name: str = Field(..., description="Simulation name")
    kind: str = Field(..., description="Simulation kind: fea or kinematics")
    entity_id: str | None = Field(None, description="Target entity id")
    params: dict[str, Any] = Field(default_factory=dict, description="Backend parameters")


class SimSetupOutput(BaseModel):
    """Output for registering a simulation."""

    sim_id: str = Field(..., description="Simulation id")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class SimRunInput(BaseModel):
    """Input for running a simulation."""

    sim_id: str = Field(..., description="Simulation id")
    async_run: bool = Field(False, description="Schedule as an async batch job")


class SimRunOutput(BaseModel):
    """Output for running a simulation."""

    sim_id: str = Field(..., description="Simulation id")
    status: str = Field(..., description="Operation status")
    sim_state: str = Field(..., description="Simulation state: running/done/error")
    job_id: str | None = Field(None, description="Batch job id when scheduled async")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Result metrics")
    message: str | None = Field(None, description="Status description")


class SimResultInput(BaseModel):
    """Input for fetching a simulation result."""

    sim_id: str = Field(..., description="Simulation id")


class SimResultOutput(BaseModel):
    """Output for fetching a simulation result."""

    sim_id: str = Field(..., description="Simulation id")
    name: str = Field("", description="Simulation name")
    kind: str = Field("", description="Simulation kind")
    state: str = Field(..., description="Simulation state")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Result metrics")
    message: str | None = Field(None, description="Status description")
    status: str = Field(..., description="Operation status")


class SimListInput(BaseModel):
    """Input for listing simulations."""


class SimListOutput(BaseModel):
    """Output for listing simulations."""

    simulations: list[dict[str, Any]] = Field(
        default_factory=list, description="Simulation summaries"
    )
    status: str = Field(..., description="Operation status")


def _manager() -> SimulationManager:
    return SimulationManager()


def cad_sim_mesh(input: SimMeshInput) -> SimMeshOutput:
    """Mesh an entity's bounding box into a hexahedral grid.

    Pure-Python meshing of the target entity's bounding box. Returns node
    and element counts plus the meshed volume.
    """
    try:
        mesh = _manager().mesh(input.entity_id, input.nx, input.ny, input.nz)
        return SimMeshOutput(
            node_count=mesh["node_count"],
            element_count=mesh["element_count"],
            element_type=mesh["element_type"],
            bbox=mesh["bbox"],
            status="success",
            message=f"Meshed {mesh['element_count']} hexa8 elements",
        )
    except CADError as exc:
        return SimMeshOutput(status="error", message=str(exc))


def cad_sim_setup(input: SimSetupInput) -> SimSetupOutput:
    """Register a simulation for later execution.

    Creates a simulation record with the given kind and parameters. No
    solver runs at this stage; use ``cad_sim_run`` to execute it.
    """
    try:
        sim_id = _manager().create(
            name=input.name,
            kind=input.kind,
            entity_id=input.entity_id,
            params=input.params,
        )
        return SimSetupOutput(
            sim_id=sim_id,
            status="success",
            message=f"Simulation {input.name} registered as {sim_id}",
        )
    except CADError as exc:
        return SimSetupOutput(sim_id="", status="error", message=str(exc))


def cad_sim_run(input: SimRunInput) -> SimRunOutput:
    """Run a registered simulation.

    Executes synchronously by default. Set ``async_run`` to schedule the
    run through the batch subsystem and receive a batch ``job_id``. FEA
    requires the CalculiX ``ccx`` executable; kinematics requires
    PyBullet; otherwise a friendly ``requires_sim`` error is reported.
    """
    try:
        if input.async_run:
            job_id = _manager().submit(input.sim_id)
            return SimRunOutput(
                sim_id=input.sim_id,
                status="success",
                sim_state="running",
                job_id=job_id,
                message=f"Scheduled async run as batch job {job_id}",
            )
        result = _manager().run(input.sim_id)
        return SimRunOutput(
            sim_id=input.sim_id,
            status="success" if result.status.value == "done" else "error",
            sim_state=result.status.value,
            metrics=result.metrics,
            message=result.message,
        )
    except CADError as exc:
        return SimRunOutput(
            sim_id=input.sim_id,
            status="error",
            sim_state="error",
            message=str(exc),
        )


def cad_sim_result(input: SimResultInput) -> SimResultOutput:
    """Fetch the current state and metrics of a simulation."""
    try:
        summary = _manager().result(input.sim_id)
        return SimResultOutput(
            sim_id=summary["sim_id"],
            name=summary["name"],
            kind=summary["kind"],
            state=summary["status"],
            metrics=summary["metrics"],
            message=summary["message"],
            status="success",
        )
    except CADError as exc:
        return SimResultOutput(sim_id=input.sim_id, state="error", status="error", message=str(exc))


def cad_sim_list(input: SimListInput) -> SimListOutput:
    """List all registered simulations."""
    del input
    return SimListOutput(simulations=_manager().list(), status="success")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_sim_mesh", cad_sim_mesh),
    ("cad_sim_setup", cad_sim_setup),
    ("cad_sim_run", cad_sim_run),
    ("cad_sim_result", cad_sim_result),
    ("cad_sim_list", cad_sim_list),
]
