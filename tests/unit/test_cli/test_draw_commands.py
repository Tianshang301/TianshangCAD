"""CLI draw command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from tianshangcad.cli.main import app

runner = CliRunner()


def _new_file() -> None:
    result = runner.invoke(app, ["file", "new", "draw.json"])
    assert result.exit_code == 0


class TestDrawCommands:
    """`tianshangcad draw` command tests."""

    def test_draw_line(self) -> None:
        _new_file()
        result = runner.invoke(app, ["draw", "line", "0,0", "100,0"])
        assert result.exit_code == 0
        assert "Created" in result.stdout

    def test_draw_circle(self) -> None:
        _new_file()
        result = runner.invoke(app, ["draw", "circle", "50,50", "--radius", "25"])
        assert result.exit_code == 0
        assert "Created" in result.stdout

    def test_draw_rectangle(self) -> None:
        _new_file()
        result = runner.invoke(app, ["draw", "rectangle", "0,0", "--width", "10", "--height", "5"])
        assert result.exit_code == 0

    def test_draw_polygon(self) -> None:
        _new_file()
        result = runner.invoke(app, ["draw", "polygon", "0,0", "--radius", "10", "--sides", "6"])
        assert result.exit_code == 0

    def test_draw_polyline(self) -> None:
        _new_file()
        result = runner.invoke(app, ["draw", "polyline", "0,0 10,0 10,10"])
        assert result.exit_code == 0

    def test_draw_arc(self) -> None:
        _new_file()
        result = runner.invoke(app, [
            "draw", "arc", "0,0", "--radius", "5", "--start-angle", "0", "--end-angle", "90",
        ])
        assert result.exit_code == 0

    def test_draw_box(self) -> None:
        _new_file()
        result = runner.invoke(app, ["draw", "box", "0,0,0", "--dimensions", "100,50,30"])
        assert result.exit_code == 0

    def test_draw_cylinder(self) -> None:
        _new_file()
        result = runner.invoke(
            app, ["draw", "cylinder", "0,0,0", "--radius", "10", "--height", "20"]
        )
        assert result.exit_code == 0

    def test_draw_sphere(self) -> None:
        _new_file()
        result = runner.invoke(app, ["draw", "sphere", "0,0,0", "--radius", "5"])
        assert result.exit_code == 0

    def test_draw_without_document(self) -> None:
        result = runner.invoke(app, ["draw", "line", "0,0", "1,0"])
        assert result.exit_code == 1
        assert "No active document" in result.output

    def test_invalid_point(self) -> None:
        _new_file()
        result = runner.invoke(app, ["draw", "line", "abc", "1,0"])
        assert result.exit_code == 1
        assert "Invalid numeric point" in result.output

    def test_invalid_radius(self) -> None:
        _new_file()
        result = runner.invoke(app, ["draw", "circle", "0,0", "--radius", "-5"])
        assert result.exit_code == 1
        assert "radius must be > 0" in result.output

    def test_draw_on_layer(self) -> None:
        _new_file()
        runner.invoke(app, ["layer", "create", "Outline", "--color", "#FF0000"])
        result = runner.invoke(app, ["draw", "line", "0,0", "10,0", "--layer", "Outline"])
        assert result.exit_code == 0
        list_result = runner.invoke(app, ["edit", "list"])
        assert "layer=Outline" in list_result.stdout
