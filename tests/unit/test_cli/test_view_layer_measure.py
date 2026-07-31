"""CLI view / layer / measure command tests."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from cad_mcp_server.cli.main import app

runner = CliRunner()


class TestLayerCommands:
    """`cad-cli layer` command tests."""

    def test_create_list_set(self) -> None:
        runner.invoke(app, ["file", "new", "layers.json"])
        result = runner.invoke(app, ["layer", "create", "Outline", "--color", "#FF0000"])
        assert result.exit_code == 0
        result = runner.invoke(app, ["layer", "set", "Outline"])
        assert result.exit_code == 0
        result = runner.invoke(app, ["layer", "list"])
        assert "Outline" in result.stdout
        assert "* Outline" in result.stdout

    def test_on_off(self) -> None:
        runner.invoke(app, ["file", "new", "layers.json"])
        runner.invoke(app, ["layer", "create", "A"])
        assert "off" in runner.invoke(app, ["layer", "off", "A"]).stdout
        assert "on" in runner.invoke(app, ["layer", "on", "A"]).stdout

    def test_delete(self) -> None:
        runner.invoke(app, ["file", "new", "layers.json"])
        runner.invoke(app, ["layer", "create", "A"])
        result = runner.invoke(app, ["layer", "delete", "A"])
        assert result.exit_code == 0

    def test_delete_protected(self) -> None:
        runner.invoke(app, ["file", "new", "layers.json"])
        result = runner.invoke(app, ["layer", "delete", "0"])
        assert result.exit_code == 1
        assert "cannot be deleted" in result.output


class TestViewCommands:
    """`cad-cli view` command tests."""

    def test_zoom_extents(self) -> None:
        runner.invoke(app, ["file", "new", "view.json"])
        runner.invoke(app, ["draw", "box", "0,0,0", "--dimensions", "10,20,30"])
        result = runner.invoke(app, ["view", "zoom", "--extents"])
        assert result.exit_code == 0
        assert "min=" in result.stdout
        assert "10.0, 20.0, 30.0" in result.stdout

    def test_pan(self) -> None:
        runner.invoke(app, ["file", "new", "view.json"])
        runner.invoke(app, ["draw", "line", "0,0", "10,0"])
        result = runner.invoke(app, ["view", "pan", "--dx", "5", "--dy", "5"])
        assert result.exit_code == 0

    def test_view_list(self) -> None:
        runner.invoke(app, ["file", "new", "view.json"])
        runner.invoke(app, ["draw", "line", "0,0", "10,0"])
        assert "line" in runner.invoke(app, ["view", "list"]).stdout


class TestMeasureCommands:
    """`cad-cli measure` command tests."""

    def test_distance(self) -> None:
        runner.invoke(app, ["file", "new", "measure.json"])
        result = runner.invoke(app, ["measure", "distance", "0,0", "3,4"])
        assert result.exit_code == 0
        assert "Distance: 5.000000" in result.stdout

    def test_area_circle(self) -> None:
        runner.invoke(app, ["file", "new", "measure.json"])
        draw = runner.invoke(app, ["draw", "circle", "0,0", "--radius", "2"])
        entity_id = draw.stdout.split()[-1]
        result = runner.invoke(app, ["measure", "area", entity_id])
        assert result.exit_code == 0
        assert "Area: 12.566371" in result.stdout

    def test_volume_box(self) -> None:
        runner.invoke(app, ["file", "new", "measure.json"])
        entity_id = runner.invoke(
            app, ["draw", "box", "0,0,0", "--dimensions", "10,10,10"]
        ).stdout.split()[-1]
        result = runner.invoke(app, ["measure", "area", entity_id])
        assert result.exit_code == 0
        assert "Volume: 1000.000000" in result.stdout

    def test_measure_list(self) -> None:
        runner.invoke(app, ["file", "new", "measure.json"])
        runner.invoke(app, ["draw", "line", "0,0", "1,0"])
        assert "line" in runner.invoke(app, ["measure", "list"]).stdout


class TestAliases:
    """Alias expansion via the CLI entry function."""

    def test_line_alias(self, monkeypatch, capsys) -> None:
        runner.invoke(app, ["file", "new", "alias.json"])
        from cad_mcp_server.cli.main import main as cli_main

        monkeypatch.setattr("sys.argv", ["cad-cli", "l", "0,0", "100,0"])
        with pytest.raises(SystemExit) as exc_info:
            cli_main()
        assert exc_info.value.code == 0
        output = capsys.readouterr().out
        assert "Created" in output

    def test_unknown_alias_not_expanded(self, monkeypatch, capsys) -> None:
        from cad_mcp_server.cli.main import main as cli_main

        monkeypatch.setattr("sys.argv", ["cad-cli", "not-an-alias"])
        with pytest.raises(SystemExit) as exc_info:
            cli_main()
        assert exc_info.value.code != 0
