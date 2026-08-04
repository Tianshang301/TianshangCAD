"""CLI file command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from tianshangcad.cli.main import app

runner = CliRunner()


class TestFileCommands:
    """`tianshangcad file` command tests."""

    def test_new(self) -> None:
        result = runner.invoke(app, ["file", "new", "design.json"])
        assert result.exit_code == 0
        assert "File created: design.json" in result.stdout

    def test_new_with_unit(self) -> None:
        result = runner.invoke(app, ["file", "new", "part.json", "--unit", "cm"])
        assert result.exit_code == 0
        assert "File created" in result.stdout

    def test_new_invalid_unit(self) -> None:
        result = runner.invoke(app, ["file", "new", "part.json", "--unit", "parsec"])
        assert result.exit_code == 1
        assert "Unsupported unit" in result.output

    def test_new_missing_template(self) -> None:
        result = runner.invoke(app, ["file", "new", "part.json", "--template", "/nope/tpl.json"])
        assert result.exit_code == 1
        assert "Template not found" in result.output

    def test_list_empty(self) -> None:
        result = runner.invoke(app, ["file", "list"])
        assert result.exit_code == 0
        assert "No open files" in result.stdout

    def test_info_without_file(self) -> None:
        result = runner.invoke(app, ["file", "info"])
        assert result.exit_code == 1
        assert "No active document" in result.output

    def test_save_open_roundtrip(self, tmp_path) -> None:
        save_path = tmp_path / "scene.json"
        result = runner.invoke(app, ["file", "new", "scene.json"])
        assert result.exit_code == 0
        result = runner.invoke(app, ["draw", "circle", "10,10", "--radius", "5"])
        assert result.exit_code == 0
        result = runner.invoke(app, ["file", "save", str(save_path)])
        assert result.exit_code == 0
        assert "Saved" in result.stdout

        result = runner.invoke(app, ["file", "list"])
        assert "scene.json" in result.stdout

        result = runner.invoke(app, ["file", "info"])
        assert result.exit_code == 0
        assert "Objects:" in result.stdout
        assert "1" in result.stdout

    def test_close(self) -> None:
        runner.invoke(app, ["file", "new", "a.json"])
        result = runner.invoke(app, ["file", "close"])
        assert result.exit_code == 0
        assert "Closed: a.json" in result.stdout

    def test_open_missing(self) -> None:
        result = runner.invoke(app, ["file", "open", "/nope/scene.json"])
        assert result.exit_code == 1
        assert "File does not exist" in result.output


class TestDxfDataParity:
    """DXF export data parity tests."""

    def test_dxf_export_matches_entities(self, tmp_path) -> None:
        import ezdxf

        dxf_path = tmp_path / "parity.dxf"
        runner.invoke(app, ["file", "new", "parity.json"])
        runner.invoke(app, ["draw", "line", "0,0", "100,0"])
        runner.invoke(app, ["draw", "circle", "50,50", "--radius", "25"])
        result = runner.invoke(
            app, ["file", "export", "--format", "dxf", "--output", str(dxf_path)]
        )
        assert result.exit_code == 0
        assert dxf_path.exists()
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        lines = [e for e in msp if e.dxftype() == "LINE"]
        circles = [e for e in msp if e.dxftype() == "CIRCLE"]
        assert len(lines) == 1
        assert len(circles) == 1
        assert tuple(circles[0].dxf.center) == (50.0, 50.0, 0.0)
        assert circles[0].dxf.radius == 25.0

    def test_dxf_export_empty_geometry(self, tmp_path) -> None:
        dxf_path = tmp_path / "empty.dxf"
        runner.invoke(app, ["file", "new", "empty.json"])
        result = runner.invoke(
            app, ["file", "export", "--format", "dxf", "--output", str(dxf_path)]
        )
        assert result.exit_code == 0
        assert dxf_path.exists()


class TestStepExportImport:
    """`tianshangcad file` STEP export/import tests."""

    def test_export_import_step(self, tmp_path) -> None:
        step_path = tmp_path / "out.step"
        runner.invoke(app, ["file", "new", "part.json"])
        result = runner.invoke(
            app, ["draw", "box", "0,0,0", "--dimensions", "10,10,10"]
        )
        assert result.exit_code == 0
        exported = runner.invoke(
            app, ["file", "export", "--format", "step", "--output", str(step_path)]
        )
        assert exported.exit_code == 0
        assert "Exported" in exported.stdout
        assert step_path.exists()

        imported = runner.invoke(app, ["file", "import", str(step_path)])
        assert imported.exit_code == 0
        assert "Imported" in imported.stdout
        assert "1 objects" in imported.stdout

    def test_import_missing_step(self, tmp_path) -> None:
        result = runner.invoke(app, ["file", "import", str(tmp_path / "nope.step")])
        assert result.exit_code == 1
        assert "File does not exist" in result.output

    def test_export_unsupported_format(self, tmp_path) -> None:
        runner.invoke(app, ["file", "new", "part.json"])
        result = runner.invoke(
            app, ["file", "export", "--format", "bogus", "--output", str(tmp_path / "x.foo")]
        )
        assert result.exit_code == 1
        assert "Unsupported export format" in result.output

    def test_import_unsupported_suffix(self, tmp_path) -> None:
        bogus = tmp_path / "file.xyz"
        bogus.write_text("data", encoding="utf-8")
        result = runner.invoke(app, ["file", "import", str(bogus)])
        assert result.exit_code == 1
        assert "Unsupported import format" in result.output

    def test_step_export_reimport_preserves_geometry(self, tmp_path) -> None:
        """STEP export -> reimport must preserve the solid's extent."""
        step_path = tmp_path / "roundtrip.step"
        runner.invoke(app, ["file", "new", "roundtrip.json"])
        result = runner.invoke(
            app, ["draw", "box", "0,0,0", "--dimensions", "10,20,30"]
        )
        assert result.exit_code == 0
        exported = runner.invoke(
            app, ["file", "export", "--format", "step", "--output", str(step_path)]
        )
        assert exported.exit_code == 0
        imported = runner.invoke(app, ["file", "import", str(step_path)])
        assert imported.exit_code == 0
        info = runner.invoke(app, ["file", "info"])
        assert info.exit_code == 0
        assert "min=[0.0, 0.0, 0.0]" in info.stdout
        assert "max=[10.0, 20.0, 30.0]" in info.stdout

    def test_step_export_multi_entity(self, tmp_path) -> None:
        """STEP export must include every solid entity."""
        step_path = tmp_path / "multi.step"
        runner.invoke(app, ["file", "new", "multi.json"])
        runner.invoke(app, ["draw", "box", "0,0,0", "--dimensions", "10,10,10"])
        runner.invoke(app, ["draw", "sphere", "20,0,0", "--radius", "5"])
        exported = runner.invoke(
            app, ["file", "export", "--format", "step", "--output", str(step_path)]
        )
        assert exported.exit_code == 0
        text = step_path.read_text(encoding="utf-8")
        assert text.count("MANIFOLD_SOLID_BREP") >= 2
        imported = runner.invoke(app, ["file", "import", str(step_path)])
        assert imported.exit_code == 0
        assert "2 objects" in imported.stdout

    def test_step_export_default_format(self, tmp_path) -> None:
        """STEP is the recommended default export format."""
        step_path = tmp_path / "default.step"
        runner.invoke(app, ["file", "new", "default.json"])
        runner.invoke(app, ["draw", "box", "0,0,0", "--dimensions", "1,1,1"])
        exported = runner.invoke(
            app, ["file", "export", "--output", str(step_path)]
        )
        assert exported.exit_code == 0
        assert step_path.exists()
        assert step_path.read_text(encoding="utf-8").startswith("ISO-10303-21;")
