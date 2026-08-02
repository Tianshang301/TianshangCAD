"""CLI edit command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from cad_mcp_server.cli.main import app

runner = CliRunner()


def _setup_line() -> str:
    runner.invoke(app, ["file", "new", "edit.json"])
    result = runner.invoke(app, ["draw", "line", "0,0", "100,0"])
    return result.stdout.split()[-1]


class TestEditCommands:
    """`cad-cli edit` command tests."""

    def test_move(self) -> None:
        entity_id = _setup_line()
        result = runner.invoke(app, ["edit", "move", entity_id, "--dx", "10", "--dy", "5"])
        assert result.exit_code == 0
        assert f"Moved {entity_id}" in result.stdout

    def test_copy(self) -> None:
        entity_id = _setup_line()
        result = runner.invoke(app, ["edit", "copy", entity_id])
        assert result.exit_code == 0
        assert f"Copied {entity_id}" in result.stdout
        list_result = runner.invoke(app, ["edit", "list"])
        assert "line" in list_result.stdout

    def test_rotate(self) -> None:
        entity_id = _setup_line()
        result = runner.invoke(app, ["edit", "rotate", entity_id, "--angle", "90"])
        assert result.exit_code == 0
        assert "Rotated" in result.stdout

    def test_scale(self) -> None:
        entity_id = _setup_line()
        result = runner.invoke(app, ["edit", "scale", entity_id, "--factor", "2"])
        assert result.exit_code == 0
        assert "Scaled" in result.stdout

    def test_erase(self) -> None:
        entity_id = _setup_line()
        result = runner.invoke(app, ["edit", "erase", entity_id])
        assert result.exit_code == 0
        assert f"Erased {entity_id}" in result.stdout
        assert "No objects" in runner.invoke(app, ["edit", "list"]).stdout

    def test_erase_missing(self) -> None:
        _setup_line()
        result = runner.invoke(app, ["edit", "erase", "ghost"])
        assert result.exit_code == 1
        assert "Object not found" in result.output

    def test_undo_redo(self) -> None:
        entity_id = _setup_line()
        runner.invoke(app, ["edit", "move", entity_id, "--dx", "50"])
        undo = runner.invoke(app, ["edit", "undo"])
        assert "Undone" in undo.stdout
        redo = runner.invoke(app, ["edit", "redo"])
        assert "Redone" in redo.stdout

    def test_undo_nothing(self) -> None:
        _setup_line()
        result = runner.invoke(app, ["edit", "undo"])
        assert "Nothing to undo" in result.stdout

    def test_edit_list_shows_bbox(self) -> None:
        entity_id = _setup_line()
        result = runner.invoke(app, ["edit", "list"])
        assert entity_id in result.stdout
        assert "min=" in result.stdout


class TestBooleanCommands:
    """`cad-cli edit` boolean command tests."""

    def _setup_boxes(self) -> tuple[str, str]:
        runner.invoke(app, ["file", "new", "bool.json"])
        a = runner.invoke(app, ["draw", "box", "0,0,0", "--dimensions", "2,2,2"])
        b = runner.invoke(app, ["draw", "box", "1,1,1", "--dimensions", "2,2,2"])
        return a.stdout.split()[-1], b.stdout.split()[-1]

    def test_union(self) -> None:
        a, b = self._setup_boxes()
        result = runner.invoke(app, ["edit", "union", a, b])
        assert result.exit_code == 0
        assert f"Union {a} + {b}" in result.stdout
        assert "-> " in result.stdout

    def test_subtract(self) -> None:
        a, b = self._setup_boxes()
        result = runner.invoke(app, ["edit", "subtract", a, b])
        assert result.exit_code == 0
        assert f"Subtract {b} from {a}" in result.stdout

    def test_intersect(self) -> None:
        a, b = self._setup_boxes()
        result = runner.invoke(app, ["edit", "intersect", a, b])
        assert result.exit_code == 0
        assert f"Intersect {a} & {b}" in result.stdout
