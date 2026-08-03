"""CLI simulation command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from cad_mcp_server.cli.main import app
from cad_mcp_server.core.document import DocumentManager

runner = CliRunner()


def _setup() -> None:
    manager = DocumentManager()
    manager.create("sim.json", unit="mm")


def _run(*args: str):
    return runner.invoke(app, [*args])


def _box() -> str:
    doc = DocumentManager().get_current()
    box_id = doc.entities.create(
        "box", {"origin": [0, 0, 0], "dimensions": [10, 10, 10]}, object_id="box1"
    )
    return box_id


class TestSimCommands:
    """`sim` CLI group tests."""

    def test_mesh(self) -> None:
        _setup()
        box = _box()
        result = _run("sim", "mesh", box, "--nx", "2", "--ny", "2", "--nz", "2")
        assert result.exit_code == 0, result.output
        assert "27 nodes, 8 hexa8 elements" in result.output

    def test_setup_and_list(self) -> None:
        _setup()
        result = _run("sim", "setup", "beam", "--kind", "fea")
        assert result.exit_code == 0, result.output
        sim_id = result.output.split()[-1]
        assert sim_id.startswith("sim_")
        listing = _run("sim", "list")
        assert listing.exit_code == 0
        assert sim_id in listing.output

    def test_run_requires_backend_error(self) -> None:
        _setup()
        result = _run("sim", "setup", "kin", "--kind", "kinematics")
        sim_id = result.output.split()[-1]
        run_result = _run("sim", "run", sim_id)
        assert run_result.exit_code == 0
        assert "error" in run_result.output.lower()

    def test_result_not_found(self) -> None:
        _setup()
        result = _run("sim", "result", "nope")
        assert result.exit_code == 1
