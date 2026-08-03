"""CLI assembly command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from cad_mcp_server.cli.main import app

runner = CliRunner()


class TestAssemblyCommands:
    """`cad-cli assembly` command tests."""

    def _new_file(self) -> None:
        runner.invoke(app, ["file", "new", "assembly.json"])

    def _add_two_parts(self) -> tuple[str, str]:
        self._new_file()
        out_a = runner.invoke(app, ["assembly", "add-part", "base"])
        out_b = runner.invoke(app, ["assembly", "add-part", "gear"])
        node_a = out_a.stdout.strip().split()[3].strip("()")
        node_b = out_b.stdout.strip().split()[3].strip("()")
        return node_a, node_b

    def test_create(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["assembly", "create", "--name", "engine"])
        assert result.exit_code == 0
        assert "engine" in result.stdout

    def test_add_part(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["assembly", "add-part", "base"])
        assert result.exit_code == 0
        assert "Added part base" in result.stdout

    def test_add_subasm(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["assembly", "add-subasm", "motor"])
        assert result.exit_code == 0
        assert "Added sub-assembly motor" in result.stdout

    def test_mate(self) -> None:
        node_a, node_b = self._add_two_parts()
        result = runner.invoke(
            app,
            ["assembly", "mate", node_a, node_b, "--type", "distance", "--distance", "20"],
        )
        assert result.exit_code == 0
        assert "distance mate" in result.stdout

    def test_mate_invalid_type(self) -> None:
        node_a, node_b = self._add_two_parts()
        result = runner.invoke(
            app, ["assembly", "mate", node_a, node_b, "--type", "weld"]
        )
        assert result.exit_code == 1

    def test_mate_bad_axis(self) -> None:
        node_a, node_b = self._add_two_parts()
        result = runner.invoke(
            app,
            [
                "assembly", "mate", node_a, node_b, "--type", "distance",
                "--axis", "1,2",
            ],
        )
        assert result.exit_code == 1

    def test_solve(self) -> None:
        node_a, node_b = self._add_two_parts()
        runner.invoke(
            app,
            ["assembly", "mate", node_a, node_b, "--type", "distance",
             "--distance", "20", "--axis", "1,0,0"],
        )
        result = runner.invoke(app, ["assembly", "solve"])
        assert result.exit_code == 0
        assert node_b in result.stdout
        assert "Solved 1 mates" in result.stdout

    def test_solve_no_mates(self) -> None:
        self._new_file()
        runner.invoke(app, ["assembly", "add-part", "base"])
        result = runner.invoke(app, ["assembly", "solve"])
        assert result.exit_code == 0
        assert "No mates to solve" in result.stdout

    def test_bom(self) -> None:
        node_a, node_b = self._add_two_parts()
        del node_a, node_b
        result = runner.invoke(app, ["assembly", "bom"])
        assert result.exit_code == 0
        assert "x1" in result.stdout

    def test_bom_csv(self) -> None:
        self._add_two_parts()
        result = runner.invoke(app, ["assembly", "bom", "--csv"])
        assert result.exit_code == 0
        assert "name,quantity,entity_id" in result.stdout

    def test_bom_empty(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["assembly", "bom"])
        assert result.exit_code == 0
        assert "No parts in assembly" in result.stdout

    def test_explode(self) -> None:
        self._add_two_parts()
        result = runner.invoke(
            app, ["assembly", "explode", "--spacing", "5", "--direction", "z"]
        )
        assert result.exit_code == 0
        assert "depth=1" in result.stdout
