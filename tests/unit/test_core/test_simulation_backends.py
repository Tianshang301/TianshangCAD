"""Dep-gated real simulation backend tests (Phase 8).

These verify the CalculiX (``ccx``) and PyBullet backends when their
engines are installed. They skip in CI by default; installed engines
gate each test via :func:`pytest.mark.skipif`.
"""

from __future__ import annotations

import shutil

import pytest

from cad_mcp_server.core.simulation import (
    LinearStaticFEA,
    RigidBodyKinematics,
    SimulationConfig,
)

ccx = shutil.which("ccx")

try:
    import pybullet
except ImportError:  # pragma: no cover - depends on environment
    pybullet = None


@pytest.mark.skipif(ccx is None, reason="ccx (CalculiX) not installed")
class TestLinearStaticFEA:
    """Real CalculiX solve."""

    def test_solves_box(self) -> None:
        backend = LinearStaticFEA()
        config = SimulationConfig(
            name="beam",
            kind="fea",
            params={"nx": 2, "ny": 2, "nz": 2, "young_modulus": 210000.0},
        )
        metrics = backend.run(config)
        assert metrics["engine"] == "calculix"
        assert metrics["elements"] == 8
        assert metrics["returncode"] == 0

    def test_build_inp_smells_like_calculix(self) -> None:
        from cad_mcp_server.core.simulation import mesh_hex_bbox

        backend = LinearStaticFEA()
        mesh = mesh_hex_bbox([0, 0, 0], [10, 10, 10], 2, 2, 2)
        inp = backend._build_inp(mesh, 210000.0, 0.3, 1.0)
        assert "*ELEMENT,TYPE=C3D8" in inp
        assert "*MATERIAL,NAME=CADMAT" in inp
        assert "*END STEP" in inp


@pytest.mark.skipif(pybullet is None, reason="pybullet not installed")
class TestRigidBodyKinematics:
    """Real PyBullet rigid-body solve."""

    def test_free_fall_drop(self) -> None:
        backend = RigidBodyKinematics()
        config = SimulationConfig(
            name="drop", kind="kinematics", params={"duration": 1.0}
        )
        metrics = backend.run(config)
        assert metrics["engine"] == "pybullet"
        assert metrics["steps"] > 0
        assert metrics["drop"] > 0.0
