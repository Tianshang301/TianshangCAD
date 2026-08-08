"""Simulation tools: mesh, setup, run, result and list.

Simulations are managed by :class:`~tianshangcad.core.simulation.SimulationManager`.
FEA (CalculiX) and rigid-body kinematics (PyBullet) backends are optional
and report a friendly ``requires_sim`` error when their engines are absent;
meshing is pure Python and always available. ``cad_sim_run`` may also be
scheduled as an async batch job via ``cad_batch_schedule``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

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


class SimDeleteInput(BaseModel):
    """Input for deleting a simulation."""

    sim_id: str = Field(..., description="Simulation id to delete")


class SimDeleteOutput(BaseModel):
    """Output for deleting a simulation."""

    sim_id: str = Field(..., description="Deleted simulation id")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


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
    """Fetch the current state and metrics of a simulation.

    读取仿真结果。Returns the lifecycle state (pending/running/done/error)
    and the computed metrics (e.g. max displacement / stress for FEA).

    When not to use: to enumerate simulations use ``cad_sim_list``; to
    launch one use ``cad_sim_run``. A result for an unknown ``sim_id``
    errors — check the list first.
    """
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


def cad_sim_delete(input: SimDeleteInput) -> SimDeleteOutput:
    """Delete a registered simulation.

    删除已注册的仿真记录，不可撤销。不影响目标实体。
    """
    try:
        _manager().delete(input.sim_id)
        return SimDeleteOutput(
            sim_id=input.sim_id, status="success", message="Deleted simulation"
        )
    except CADError as exc:
        return SimDeleteOutput(sim_id="", status="error", message=str(exc))


# ---------------------------------------------------------------------------
# Aggregate cad_sim tool
# ---------------------------------------------------------------------------


class SimMeshParams(SimMeshInput):
    """Mesh an entity."""

    action: Literal["mesh"] = "mesh"


class SimSetupParams(SimSetupInput):
    """Register a simulation."""

    action: Literal["setup"] = "setup"


class SimRunParams(SimRunInput):
    """Run a simulation."""

    action: Literal["run"] = "run"


class SimResultParams(SimResultInput):
    """Fetch a simulation result."""

    action: Literal["result"] = "result"


class SimListParams(SimListInput):
    """List simulations."""

    action: Literal["list"] = "list"


class SimDeleteParams(SimDeleteInput):
    """Delete a simulation."""

    action: Literal["delete"] = "delete"


SimActionParams = Annotated[
    SimMeshParams
    | SimSetupParams
    | SimRunParams
    | SimResultParams
    | SimListParams
    | SimDeleteParams,
    Field(discriminator="action"),
]


class SimInput(BaseModel):
    """Input for the aggregate simulation tool.

    聚合仿真工具。``action`` 决定操作：mesh / setup / run / result / list / delete。
    """

    sim: SimActionParams = Field(
        ...,
        description=(
            "Simulation action to perform, discriminated by `action`: mesh, "
            "setup, run, result, list or delete."
        ),
    )


class SimOutput(BaseModel):
    """Output of the aggregate simulation tool."""

    action: str = Field(..., description="Simulation action executed")
    sim_id: str = Field("", description="Simulation identifier")
    name: str = Field("", description="Simulation name")
    kind: str = Field("", description="Simulation kind")
    state: str = Field("", description="Simulation state")
    node_count: int = Field(0, description="Mesh node count")
    element_count: int = Field(0, description="Mesh element count")
    element_type: str = Field("", description="Element type")
    bbox: dict[str, Any] = Field(default_factory=dict, description="Meshed bounding box")
    results: list[dict[str, Any]] = Field(default_factory=list, description="Simulation summaries")
    result: dict[str, Any] = Field(default_factory=dict, description="Simulation result payload")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _sim_result(action: str, result: BaseModel) -> SimOutput:
    data = result.model_dump()
    data["action"] = action
    return SimOutput(**data)


def cad_sim(input: SimInput) -> SimOutput:
    """Mesh, setup, run, inspect or delete a simulation.

    聚合仿真操作。按 ``action`` 派发：mesh / setup / run / result / list / delete。
    - ``mesh``: generate a hexa8 hex mesh of an entity's bounding box (pure
      Python, always available).
    - ``setup``: register a simulation (``kind`` = fea or kinematics).
    - ``run``: execute synchronously, or schedule an async batch job with
      ``async_run``. FEA (CalculiX) and kinematics (PyBullet) backends are
      optional — absent engines report ``requires_sim``.
    - ``result`` / ``list`` / ``delete``: inspect or remove simulations.

    When not to use: ``cad_sim`` analyzes physical behavior. For geometric
    *validity* checks use ``cad_validate`` (geometry/interference); for
    meshing previews that are pure geometry use ``cad_object`` (read).
    """
    params = input.sim
    if params.action == "mesh":
        return _sim_result("mesh", cad_sim_mesh(params))
    if params.action == "setup":
        return _sim_result("setup", cad_sim_setup(params))
    if params.action == "run":
        return _sim_result("run", cad_sim_run(params))
    if params.action == "result":
        return _sim_result("result", cad_sim_result(params))
    if params.action == "list":
        return _sim_result("list", cad_sim_list(params))
    if params.action == "delete":
        return _sim_result("delete", cad_sim_delete(params))
    return SimOutput(action=params.action, status="error", message="Unknown action")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_sim", cad_sim),
]
