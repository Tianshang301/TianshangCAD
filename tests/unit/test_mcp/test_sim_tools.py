"""MCP simulation tool tests."""

from __future__ import annotations

import time

from cad_mcp_server.core.simulation import SimulationManager
from cad_mcp_server.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from cad_mcp_server.mcp.tools.simulation import (
    SimListInput,
    SimMeshInput,
    SimResultInput,
    SimRunInput,
    SimSetupInput,
    cad_sim_list,
    cad_sim_mesh,
    cad_sim_result,
    cad_sim_run,
    cad_sim_setup,
)


def _doc() -> str:
    cad_file_create(FileCreateInput(filename="sim.json"))
    return cad_object_create(
        ObjectCreateInput(type="box", params={"origin": [0, 0, 0], "dimensions": [10, 10, 10]})
    ).object_id


def _wait_for_scheduler(scheduler, job_id: str, timeout: float = 5.0) -> str:
    """Poll until a scheduler job reaches a terminal state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = scheduler.get_job(job_id)
        state = record.get("state") if record else "gone"
        if state in ("done", "error", "cancelled", "gone"):
            return state
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish in time")


class TestSimMesh:
    """`cad_sim_mesh` tests."""

    def test_mesh_box(self) -> None:
        box = _doc()
        result = cad_sim_mesh(SimMeshInput(entity_id=box, nx=2, ny=2, nz=2))
        assert result.status == "success"
        assert result.node_count == 27
        assert result.element_count == 8

    def test_mesh_unknown_entity(self) -> None:
        _doc()
        result = cad_sim_mesh(SimMeshInput(entity_id="nope"))
        assert result.status == "error"


class TestSimSetup:
    """`cad_sim_setup` tests."""

    def test_setup_fea(self) -> None:
        _doc()
        result = cad_sim_setup(SimSetupInput(name="beam", kind="fea"))
        assert result.status == "success"
        assert result.sim_id.startswith("sim_")

    def test_setup_unknown_kind(self) -> None:
        _doc()
        result = cad_sim_setup(SimSetupInput(name="x", kind="boom"))
        assert result.status == "error"


class TestSimRun:
    """`cad_sim_run` tests."""

    def _stub(self) -> None:
        class StubBackend:
            name = "stub"

            def run(self, config):
                return {"engine": "stub", "solved": True}

        SimulationManager.register_backend("fea", lambda: StubBackend())

    def test_run_success(self) -> None:
        self._stub()
        _doc()
        sim_id = cad_sim_setup(SimSetupInput(name="b", kind="fea")).sim_id
        result = cad_sim_run(SimRunInput(sim_id=sim_id))
        assert result.status == "success"
        assert result.sim_state == "done"
        assert result.metrics["solved"] is True

    def test_run_requires_sim_without_backend(self) -> None:
        _doc()
        sim_id = cad_sim_setup(SimSetupInput(name="b", kind="kinematics")).sim_id
        result = cad_sim_run(SimRunInput(sim_id=sim_id))
        assert result.status == "error"
        assert "requires_sim" in result.message or "PyBullet" in result.message

    def test_run_async_schedules_job(self) -> None:
        _doc()
        sim_id = cad_sim_setup(SimSetupInput(name="b", kind="fea")).sim_id
        result = cad_sim_run(SimRunInput(sim_id=sim_id, async_run=True))
        assert result.status == "success"
        assert result.sim_state == "running"
        assert result.job_id.startswith("job_sim_")
        from cad_mcp_server.core.scheduler import get_scheduler

        _wait_for_scheduler(get_scheduler(), result.job_id)

    def test_run_unknown_sim(self) -> None:
        result = cad_sim_run(SimRunInput(sim_id="nope"))
        assert result.status == "error"


class TestSimResultAndList:
    """`cad_sim_result` / `cad_sim_list` tests."""

    def test_result(self) -> None:
        _doc()
        sim_id = cad_sim_setup(SimSetupInput(name="b", kind="fea")).sim_id
        result = cad_sim_result(SimResultInput(sim_id=sim_id))
        assert result.status == "success"
        assert result.sim_id == sim_id
        assert result.state == "pending"

    def test_list(self) -> None:
        _doc()
        cad_sim_setup(SimSetupInput(name="a", kind="fea"))
        cad_sim_setup(SimSetupInput(name="b", kind="kinematics"))
        result = cad_sim_list(SimListInput())
        assert result.status == "success"
        assert len(result.simulations) == 2
