"""CLI constraint command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from cad_mcp_server.cli.main import app

runner = CliRunner()


class TestConstraintCommands:
    """`cad-cli constraint` command tests."""

    def _new_file(self) -> None:
        runner.invoke(app, ["file", "new", "constraints.json"])

    def _setup_lines(self) -> tuple[str, str]:
        self._new_file()
        line_a = runner.invoke(
            app, ["draw", "line", "0,0", "10,0"]
        ).stdout.strip().split()[-1]
        line_b = runner.invoke(
            app, ["draw", "line", "0,5", "8,5"]
        ).stdout.strip().split()[-1]
        return line_a, line_b

    def test_add(self) -> None:
        line_a, line_b = self._setup_lines()
        result = runner.invoke(
            app, ["constraint", "add", line_a, line_b, "--type", "parallel"]
        )
        assert result.exit_code == 0
        assert "Added parallel constraint" in result.stdout

    def test_add_invalid_type(self) -> None:
        line_a, line_b = self._setup_lines()
        result = runner.invoke(
            app, ["constraint", "add", line_a, line_b, "--type", "bogus"]
        )
        assert result.exit_code == 1
        assert "unsupported constraint type" in result.output

    def test_list_empty(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["constraint", "list"])
        assert result.exit_code == 0
        assert "No constraints" in result.stdout

    def test_remove(self) -> None:
        line_a, line_b = self._setup_lines()
        added = runner.invoke(
            app, ["constraint", "add", line_a, line_b, "--type", "parallel"]
        )
        constraint_id = added.stdout.strip().split()[3]
        result = runner.invoke(app, ["constraint", "remove", constraint_id])
        assert result.exit_code == 0
        assert "Removed constraint" in result.stdout
        assert "No constraints" in runner.invoke(app, ["constraint", "list"]).stdout

    def test_remove_missing(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["constraint", "remove", "nope"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_solve_parallel_moves_line(self) -> None:
        line_a, line_b = self._setup_lines()
        runner.invoke(app, ["constraint", "add", line_a, line_b, "--type", "fixed"])
        runner.invoke(app, ["constraint", "add", line_a, line_b, "--type", "parallel"])
        result = runner.invoke(app, ["constraint", "solve"])
        assert result.exit_code == 0
        assert "Solved" in result.stdout
        assert line_b in result.stdout

    def test_solve_no_constraints(self) -> None:
        self._new_file()
        runner.invoke(app, ["draw", "line", "0,0", "1,1"])
        result = runner.invoke(app, ["constraint", "solve"])
        assert result.exit_code == 0
        assert "No constraints to solve" in result.stdout

    def test_solve_undo_restores_constraints(self) -> None:
        line_a, line_b = self._setup_lines()
        runner.invoke(app, ["constraint", "add", line_a, line_b, "--type", "fixed"])
        result = runner.invoke(app, ["edit", "undo"])
        assert result.exit_code == 0
        assert "No constraints" in runner.invoke(app, ["constraint", "list"]).stdout
