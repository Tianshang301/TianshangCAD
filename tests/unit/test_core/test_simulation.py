"""Simulation interface core tests (mesh + lifecycle + async submit)."""

from __future__ import annotations

import time

import pytest

from cad_mcp_server.core.simulation import (
    SimulationManager,
    mesh_hex_bbox,
)
from cad_mcp_server.utils.errors import CADValidationError, SimulationError


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


class TestMeshHex:
    """Pure-Python hexahedral meshing."""

    def test_counts(self) -> None:
        mesh = mesh_hex_bbox([0, 0, 0], [10, 10, 10], 2, 3, 4)
        assert mesh["node_count"] == (2 + 1) * (3 + 1) * (4 + 1)
        assert mesh["element_count"] == 2 * 3 * 4
        assert mesh["element_type"] == "hexa8"
        assert mesh["volume"] == pytest.approx(1000.0)

    def test_origin_offset(self) -> None:
        mesh = mesh_hex_bbox([5, 5, 5], [1, 1, 1], 1, 1, 1)
        assert mesh["bbox"]["min"] == [5.0, 5.0, 5.0]
        assert mesh["bbox"]["max"] == [6.0, 6.0, 6.0]
        assert mesh["nodes"][0] == [5.0, 5.0, 5.0]

    def test_invalid_division(self) -> None:
        with pytest.raises(CADValidationError):
            mesh_hex_bbox([0, 0, 0], [1, 1, 1], 0, 1, 1)


class TestManagerLifecycle:
    """SimulationManager create/run/result/list."""

    def test_create_knows_id(self) -> None:
        manager = SimulationManager()
        sim_id = manager.create(name="beam", kind="fea")
        assert sim_id.startswith("sim_")
        assert manager.get(sim_id).status.value == "pending"

    def test_unknown_kind(self) -> None:
        manager = SimulationManager()
        with pytest.raises(SimulationError):
            manager.create(name="x", kind="explode")

    def test_result_not_found(self) -> None:
        with pytest.raises(SimulationError):
            SimulationManager().result("nope")


class TestManagerRunWithStub:
    """Run with an injectable stub backend."""

    def _stub_fea(self) -> None:
        class StubFEABackend:
            name = "stub"

            def run(self, config):
                return {"engine": "stub", "solved": True, "elements": 8}

        SimulationManager.register_backend("fea", lambda: StubFEABackend())

    def test_run_sync_success(self) -> None:
        self._stub_fea()
        manager = SimulationManager()
        sim_id = manager.create(name="beam", kind="fea")
        result = manager.run(sim_id)
        assert result.status.value == "done"
        assert result.metrics["solved"] is True
        assert result.metrics["elements"] == 8

    def test_run_backend_error_marks_error(self) -> None:
        class FailingBackend:
            name = "failing"

            def run(self, config):
                raise RuntimeError("solver crashed")

        SimulationManager.register_backend("kinematics", lambda: FailingBackend())
        manager = SimulationManager()
        sim_id = manager.create(name="kin", kind="kinematics")
        result = manager.run(sim_id)
        assert result.status.value == "error"
        assert "crashed" in result.message


class TestAsyncSubmit:
    """Async scheduling through the batch subsystem."""

    def test_submit_creates_batch_job(self) -> None:
        manager = SimulationManager()
        sim_id = manager.create(name="async", kind="fea")
        job_id = manager.submit(sim_id)
        assert job_id.startswith("job_sim_")
        from cad_mcp_server.core.scheduler import get_scheduler

        job = get_scheduler().get_job(job_id)
        assert job is not None
        assert job["commands"][0]["tool"] == "cad_sim_run"
        _wait_for_scheduler(get_scheduler(), job_id)

    def test_submit_completed_rejected(self) -> None:
        class _Done:
            def run(self, config):
                return {"engine": "stub"}

        SimulationManager.register_backend("kinematics", lambda: _Done())
        manager = SimulationManager()
        sim_id = manager.create(name="x", kind="kinematics")
        manager.run(sim_id)
        with pytest.raises(SimulationError):
            manager.submit(sim_id)


class TestMeshFromEntity:
    """Mesh an entity through the manager."""
    def test_mesh_entity(self, document) -> None:
        from cad_mcp_server.core.document import DocumentManager

        manager = DocumentManager()
        manager.create("e.json")
        doc = manager.get_current()
        box_id = doc.entities.create(
            "box", {"origin": [0, 0, 0], "dimensions": [10, 10, 10]}, object_id="box1"
        )
        mesh = SimulationManager().mesh(box_id, 2, 2, 2)
        assert mesh["node_count"] == 27
        assert mesh["element_count"] == 8
