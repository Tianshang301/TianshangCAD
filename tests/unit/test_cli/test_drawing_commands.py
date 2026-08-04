"""CLI drawing command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from tianshangcad.cli.main import app

runner = CliRunner()


class TestDrawingCommands:
    """`tianshangcad drawing` command tests."""

    def _new_file(self) -> None:
        runner.invoke(app, ["file", "new", "drawing.json"])

    def test_create(self) -> None:
        self._new_file()
        result = runner.invoke(
            app, ["drawing", "create", "--name", "engine", "--paper", "A3", "--title", "Reducer"]
        )
        assert result.exit_code == 0
        assert "engine ready (A3" in result.stdout

    def test_create_invalid_paper(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["drawing", "create", "--paper", "XXL"])
        assert result.exit_code == 1

    def test_add_view(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["drawing", "add-view", "main", "main"])
        assert result.exit_code == 0
        assert "Added main view main" in result.stdout

    def test_add_view_invalid_type(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["drawing", "add-view", "x", "bogus"])
        assert result.exit_code == 1

    def test_section(self) -> None:
        self._new_file()
        result = runner.invoke(
            app, ["drawing", "section", "sec", "--plane", "XY", "--offset", "5"]
        )
        assert result.exit_code == 0
        assert "Added section view sec" in result.stdout

    def test_dim(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["drawing", "dim", "linear", "42.5"])
        assert result.exit_code == 0
        assert "Added linear dimension 42.5" in result.stdout

    def test_dim_invalid_type(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["drawing", "dim", "bogus", "1"])
        assert result.exit_code == 1

    def test_gdt(self) -> None:
        self._new_file()
        result = runner.invoke(
            app, ["drawing", "gdt", "flatness", "--value", "0.05", "--datum", "A"]
        )
        assert result.exit_code == 0
        assert "flatness 0.05 [A]" in result.stdout

    def test_gdt_invalid_symbol(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["drawing", "gdt", "bogus"])
        assert result.exit_code == 1

    def test_export_svg(self, tmp_path) -> None:
        self._new_file()
        runner.invoke(app, ["drawing", "add-view", "main", "main"])
        out = tmp_path / "sheet.svg"
        result = runner.invoke(app, ["drawing", "export", "svg", str(out)])
        assert result.exit_code == 0
        assert "Exported SVG" in result.stdout
        assert out.exists()

    def test_export_unsupported(self) -> None:
        self._new_file()
        result = runner.invoke(app, ["drawing", "export", "bmp", "x.bmp"])
        assert result.exit_code == 1
