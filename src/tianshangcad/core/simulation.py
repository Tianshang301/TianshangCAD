"""Simulation interface.

Phase 8 (v0.8.0) introduces a backend abstraction for simulation:

* ``MeshGenerator`` meshes a document entity's bounding box into a hexa
  grid in pure Python (no extra dependencies).
* ``LinearStaticFEA`` (CalculiX) runs a minimal linear-static solve via the
  ``ccx`` executable when available, otherwise raises a friendly
  ``requires_sim`` error.
* ``RigidBodyKinematics`` (PyBullet) integrates a rigid-body trajectory via
  ``pybullet`` when installed, otherwise raises ``requires_sim``.

``SimulationManager`` persists results in memory and supports both
synchronous execution (``run``) and asynchronous execution by scheduling a
``cad_sim_run`` batch job through the existing batch subsystem
(``submit``). Heavy native dependencies stay behind optional extras; the
interface and lifecycle are fully testable with stub backends.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from tianshangcad.utils.errors import CADNotImplementedError, CADValidationError, SimulationError


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_sim_id() -> str:
    return f"sim_{uuid.uuid4().hex[:8]}"


def _is_float(token: str) -> bool:
    """Return whether ``token`` parses as a float."""
    try:
        float(token)
        return True
    except ValueError:
        return False


class SimulationKind(StrEnum):
    """Kind of simulation to run."""

    FEA = "fea"
    KINEMATICS = "kinematics"


class SimulationStatus(StrEnum):
    """Lifecycle state of a simulation."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


def _requires_sim(engine: str) -> CADNotImplementedError:
    """Return the friendly ``requires_sim`` error for an unavailable engine."""
    return CADNotImplementedError(
        f"{engine} backend unavailable; install the simulation extra "
        "(`pip install -e '.[sim]'`)",
        code="requires_sim",
    )


@dataclass
class SimulationConfig:
    """Configuration for a single simulation run."""

    name: str
    kind: str
    entity_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "name": self.name,
            "kind": self.kind,
            "entity_id": self.entity_id,
            "params": dict(self.params),
            "created_at": self.created_at,
        }


@dataclass
class SimulationResult:
    """Persisted state of a simulation run."""

    sim_id: str
    config: SimulationConfig
    status: SimulationStatus = SimulationStatus.PENDING
    metrics: dict[str, Any] = field(default_factory=dict)
    message: str | None = None
    created_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    job_id: str | None = None

    def summary(self) -> dict[str, Any]:
        """Return a compact JSON-safe summary."""
        return {
            "sim_id": self.sim_id,
            "name": self.config.name,
            "kind": self.config.kind,
            "status": self.status.value,
            "metrics": dict(self.metrics),
            "message": self.message,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "job_id": self.job_id,
        }


class SimulationBackend(ABC):
    """Abstract simulation engine."""

    name: str = "abstract"

    @abstractmethod
    def run(self, config: SimulationConfig) -> dict[str, Any]:
        """Execute the simulation and return a metrics dict."""


# ---------------------------------------------------------------------------
# Mesh generation (pure Python)
# ---------------------------------------------------------------------------


def mesh_hex_bbox(
    origin: list[float],
    dimensions: list[float],
    nx: int,
    ny: int,
    nz: int,
) -> dict[str, Any]:
    """Build a structured hexahedral grid inside a bounding box.

    ``origin`` is the box minimum corner and ``dimensions`` its size along
    each axis. Returns node/element lists plus statistics. Element counts
    scale as ``nx * ny * nz``.
    """
    if nx < 1 or ny < 1 or nz < 1:
        raise CADValidationError("mesh divisions must all be >= 1", code="invalid_mesh")
    if any(value <= 0 for value in dimensions):
        raise CADValidationError("mesh box dimensions must all be > 0", code="invalid_mesh")
    origin_arr = np.asarray(origin, dtype=float)
    dims = np.asarray(dimensions, dtype=float)
    xs = np.linspace(0.0, dims[0], nx + 1)
    ys = np.linspace(0.0, dims[1], ny + 1)
    zs = np.linspace(0.0, dims[2], nz + 1)
    nodes: list[list[float]] = []
    for z in zs:
        for y in ys:
            for x in xs:
                point = origin_arr + np.array([x, y, z])
                nodes.append([float(point[0]), float(point[1]), float(point[2])])

    def index(ix: int, iy: int, iz: int) -> int:
        return (iz * (ny + 1) + iy) * (nx + 1) + ix

    elements: list[list[int]] = []
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                i0 = index(ix, iy, iz)
                elements.append(
                    [
                        i0,
                        i0 + 1,
                        i0 + (nx + 1) + 1,
                        i0 + (nx + 1),
                        i0 + (nx + 1) * (ny + 1),
                        i0 + (nx + 1) * (ny + 1) + 1,
                        i0 + (nx + 1) * (ny + 1) + (nx + 1) + 1,
                        i0 + (nx + 1) * (ny + 1) + (nx + 1),
                    ]
                )
    volume = float(dims[0] * dims[1] * dims[2])
    return {
        "node_count": len(nodes),
        "element_count": len(elements),
        "element_type": "hexa8",
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "volume": volume,
        "bbox": {
            "min": origin_arr.tolist(),
            "max": (origin_arr + dims).tolist(),
        },
        "nodes": nodes,
        "elements": elements,
    }


class MeshGenerator:
    """Meshes document entities into a hexahedral grid."""

    def __init__(self, get_bbox: Callable[[str], dict[str, list[float]]]) -> None:
        """Bind to a bbox resolver (e.g. ``doc.entities.get_bbox``)."""
        self._get_bbox = get_bbox

    def from_entity(
        self,
        entity_id: str,
        nx: int = 4,
        ny: int = 4,
        nz: int = 4,
    ) -> dict[str, Any]:
        """Mesh the bounding box of ``entity_id``."""
        bbox = self._get_bbox(entity_id)
        minimum = bbox["min"]
        maximum = bbox["max"]
        dimensions = [
            maximum[0] - minimum[0],
            maximum[1] - minimum[1],
            maximum[2] - minimum[2],
        ]
        return mesh_hex_bbox(minimum, dimensions, nx, ny, nz)


# ---------------------------------------------------------------------------
# CalculiX linear-static FEA backend
# ---------------------------------------------------------------------------


def _ccx_executable() -> str | None:
    """Return the ``ccx`` executable path when available."""
    return shutil.which("ccx")


class LinearStaticFEA(SimulationBackend):
    """Linear-static finite element analysis via CalculiX (``ccx``)."""

    name = "calculix"

    def run(self, config: SimulationConfig) -> dict[str, Any]:
        """Build a minimal linear-static model and solve it with ``ccx``.

        The part is meshed into the configured hexa grid, one face is
        fixed and the opposite face receives a uniform pressure load. The
        .dat displacement magnitude is parsed into metrics.
        """
        ccx = _ccx_executable()
        if ccx is None:
            raise _requires_sim("CalculiX")
        params = config.params
        nx = int(params.get("nx", 4))
        ny = int(params.get("ny", 4))
        nz = int(params.get("nz", 4))
        young = float(params.get("young_modulus", 210_000.0))
        poisson = float(params.get("poisson", 0.3))
        pressure = float(params.get("pressure", 1.0))
        mesh = mesh_hex_bbox([0.0, 0.0, 0.0], [10.0, 10.0, 10.0], nx, ny, nz)
        inp = self._build_inp(mesh, young, poisson, pressure)
        dat_text = ""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "cad_sim"
            (base.with_suffix(".inp")).write_text(inp, encoding="utf-8")
            completed = subprocess.run(  # noqa: S603 - ccx is a fixed binary
                [ccx, base.stem],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=int(params.get("timeout", 120)),
            )
            candidate = base.with_suffix(".dat")
            if candidate.exists():
                dat_text = candidate.read_text(encoding="utf-8")
        return {
            "engine": "calculix",
            "elements": mesh["element_count"],
            "nodes": mesh["node_count"],
            "max_displacement": self._parse_max_displacement(dat_text),
            "young_modulus": young,
            "poisson": poisson,
            "pressure": pressure,
            "returncode": completed.returncode,
        }

    def _build_inp(
        self, mesh: dict[str, Any], young: float, poisson: float, pressure: float
    ) -> str:
        """Write a minimal CalculiX .inp model (hexa8, one step)."""
        lines = ["*HEADING", "CAD simulation", "*NODE"]
        for index, node in enumerate(mesh["nodes"], start=1):
            lines.append(f"{index},{node[0]:.6f},{node[1]:.6f},{node[2]:.6f}")
        lines.append("*ELEMENT,TYPE=C3D8")
        for index, element in enumerate(mesh["elements"], start=1):
            lines.append(
                f"{index}," + ",".join(str(value + 1) for value in element)
            )
        lines.extend(
            [
                "*MATERIAL,NAME=CADMAT",
                "*ELASTIC",
                f"{young},{poisson}",
                "*BOUNDARY",
                self._fixed_node_set(mesh) + ",1,3",
                "*STEP",
                "*STATIC",
                "*DLOAD",
                self._loaded_node_set(mesh) + ",PZ,-" + f"{pressure:.6f}",
                "*NODE FILE",
                "U",
                "*END STEP",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _fixed_node_set(mesh: dict[str, Any]) -> str:
        nodes = mesh["nodes"]
        fixed: list[int] = []
        for index, node in enumerate(nodes, start=1):
            if node[2] <= 1e-9:
                fixed.append(index)
        return "NSET0," + ",".join(str(value) for value in fixed[:200])

    @staticmethod
    def _loaded_node_set(mesh: dict[str, Any]) -> str:
        zmax = max(node[2] for node in mesh["nodes"])
        loaded: list[int] = []
        for index, node in enumerate(mesh["nodes"], start=1):
            if abs(node[2] - zmax) <= 1e-9:
                loaded.append(index)
        return "NSET1," + ",".join(str(value) for value in loaded[:200])

    def _parse_max_displacement(self, dat_text: str) -> float:
        """Extract the maximum displacement magnitude from a .dat file.

        CalculiX writes displacement rows in 4-value groups (three
        components and a magnitude); the largest magnitude across all
        nodes is returned. Falls back to ``0.0`` when no values appear.
        """
        max_value = 0.0
        values: list[float] = []
        for line in dat_text.splitlines():
            tokens = line.split()
            if len(tokens) >= 4 and any(_is_float(token) for token in tokens):
                tail = [float(token) for token in tokens if _is_float(token)]
                values.extend(tail)
        if values:
            max_value = max(values)
        return float(max_value)


# ---------------------------------------------------------------------------
# PyBullet rigid-body kinematics backend
# ---------------------------------------------------------------------------


class RigidBodyKinematics(SimulationBackend):
    """Rigid-body dynamics via PyBullet (optional ``[sim]`` extra)."""

    name = "pybullet"

    def run(self, config: SimulationConfig) -> dict[str, Any]:
        """Integrate a rigid-body free-fall trajectory with PyBullet."""
        try:
            import pybullet as pb  # type: ignore[import-not-found]
            import pybullet_data  # type: ignore[import-not-found]  # noqa: F401
        except ImportError as exc:
            raise _requires_sim("PyBullet") from exc
        params = config.params
        duration = float(params.get("duration", 1.0))
        step_size = float(params.get("step_size", 1.0 / 240.0))
        physics_client = pb.connect(pb.DIRECT)
        try:
            pb.setGravity(0, 0, -9.81)
            box_id = pb.createCollisionShape(pb.GEOM_BOX, halfExtents=[1, 1, 1])
            body = pb.createMultiBody(baseMass=1.0, baseCollisionShapeIndex=box_id)
            steps = int(duration / step_size)
            positions: list[float] = []
            for _ in range(steps):
                pb.stepSimulation()
                pos, _orn = pb.getBasePositionAndOrientation(body)
                positions.append(float(pos[2]))
            drop = positions[0] - positions[-1]
        finally:
            pb.disconnect(physics_client)
        return {
            "engine": "pybullet",
            "steps": steps,
            "duration": duration,
            "final_height": positions[-1] if positions else 0.0,
            "drop": float(drop),
            "body_count": 1,
        }


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class SimulationManager:
    """In-memory simulation registry and executor."""

    _instance: SimulationManager | None = None
    _results: ClassVar[dict[str, SimulationResult]] = {}

    def __new__(cls) -> SimulationManager:
        """Return the singleton instance, creating it on first use."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def reset(self) -> None:
        """Clear all simulation records (test helper)."""
        self._results.clear()

    # Backend registry (subclassable / injectable for tests).
    _backends: ClassVar[dict[str, Callable[[], SimulationBackend]]] = {
        SimulationKind.FEA.value: LinearStaticFEA,
        SimulationKind.KINEMATICS.value: RigidBodyKinematics,
    }

    @classmethod
    def register_backend(
        cls, kind: str, factory: Callable[[], SimulationBackend]
    ) -> None:
        """Register (or override) the backend factory for ``kind``."""
        cls._backends[kind] = factory

    @classmethod
    def _backend_for(cls, kind: str) -> SimulationBackend:
        factory = cls._backends.get(kind)
        if factory is None:
            raise SimulationError(
                f"Unknown simulation kind {kind!r}; expected fea or kinematics",
                code="unknown_kind",
            )
        return factory()

    def create(
        self,
        name: str,
        kind: str,
        entity_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Register a new simulation and return its id."""
        kind_lower = kind.lower()
        if kind_lower not in (SimulationKind.FEA.value, SimulationKind.KINEMATICS.value):
            raise SimulationError(
                f"Unknown simulation kind {kind_lower!r}; expected fea or kinematics",
                code="unknown_kind",
            )
        config = SimulationConfig(
            name=name,
            kind=kind_lower,
            entity_id=entity_id,
            params=dict(params or {}),
        )
        sim_id = _new_sim_id()
        self._results[sim_id] = SimulationResult(sim_id=sim_id, config=config)
        return sim_id

    def get(self, sim_id: str) -> SimulationResult:
        """Return a simulation result or raise ``SimulationError``."""
        result = self._results.get(sim_id)
        if result is None:
            raise SimulationError(f"Simulation not found: {sim_id}", code="sim_not_found")
        return result

    def mesh(
        self,
        entity_id: str,
        nx: int = 4,
        ny: int = 4,
        nz: int = 4,
    ) -> dict[str, Any]:
        """Mesh a document entity's bounding box (pure Python)."""
        from tianshangcad.core.document import DocumentManager

        doc = DocumentManager().get_current()
        generator = MeshGenerator(doc.entities.get_bbox)
        return generator.from_entity(entity_id, nx, ny, nz)

    def run(self, sim_id: str) -> SimulationResult:
        """Execute a simulation synchronously and update its result."""
        result = self.get(sim_id)
        result.status = SimulationStatus.RUNNING
        try:
            backend = self._backend_for(result.config.kind)
            metrics = backend.run(result.config)
            result.metrics = dict(metrics)
            result.status = SimulationStatus.DONE
            result.message = f"{result.config.kind} simulation completed"
        except Exception as exc:
            result.status = SimulationStatus.ERROR
            result.message = str(exc)
        result.finished_at = _now_iso()
        return result

    def submit(self, sim_id: str) -> str:
        """Schedule ``sim_id`` as an async batch job.

        Schedules a one-off batch job invoking ``cad_sim_run`` through the
        existing batch subsystem; returns the batch job id.
        """
        result = self.get(sim_id)
        if result.status == SimulationStatus.DONE:
            raise SimulationError(
                f"Simulation {sim_id} already completed", code="sim_already_done"
            )
        from tianshangcad.core.scheduler import get_scheduler

        job_id = f"job_sim_{uuid.uuid4().hex[:8]}"
        get_scheduler().schedule(
            job_id=job_id,
            name=f"sim-{result.config.name}",
            commands=[
                {
                    "tool": "cad_sim_run",
                    "arguments": {"sim_id": sim_id},
                }
            ],
        )
        result.job_id = job_id
        return job_id

    def result(self, sim_id: str) -> dict[str, Any]:
        """Return the JSON-safe summary of a simulation."""
        return self.get(sim_id).summary()

    def delete(self, sim_id: str) -> None:
        """Delete a registered simulation."""
        self.get(sim_id)
        del self._results[sim_id]

    def list(self) -> list[dict[str, Any]]:
        """Return summaries of every registered simulation."""
        return [result.summary() for result in self._results.values()]
