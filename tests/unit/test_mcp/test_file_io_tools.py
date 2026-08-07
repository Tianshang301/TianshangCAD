"""File export/import MCP tool unit tests."""

from __future__ import annotations

from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from tianshangcad.mcp.tools.file_io import (
    FileExportInput,
    FileExportOutput,
    FileExportParams,
    FileImportInput,
    FileImportOutput,
    FileImportParams,
    FileIoInput,
    cad_file_export,
    cad_file_import,
    cad_file_io,
)


def _new_doc(filename: str = "io.json") -> None:
    cad_file_create(FileCreateInput(filename=filename, unit="mm"))
    cad_object_create(
        ObjectCreateInput(
            type="box", params={"origin": [0, 0, 0], "dimensions": [4, 4, 4]}
        )
    )


class TestFileExport:
    """`cad_file_export` MCP tool."""

    def test_export_step(self, tmp_path) -> None:
        _new_doc()
        target = tmp_path / "out.step"
        result = cad_file_export(FileExportInput(format="step", path=str(target)))
        assert isinstance(result, FileExportOutput)
        assert result.status == "success"
        assert target.exists()

    def test_export_dxf(self, tmp_path) -> None:
        _new_doc()
        target = tmp_path / "out.dxf"
        result = cad_file_export(FileExportInput(format="dxf", path=str(target)))
        assert result.status == "success"
        assert target.exists()

    def test_export_json(self, tmp_path) -> None:
        _new_doc()
        target = tmp_path / "out.json"
        result = cad_file_export(FileExportInput(format="json", path=str(target)))
        assert result.status == "success"
        assert target.exists()

    def test_export_unsupported_format(self, tmp_path) -> None:
        _new_doc()
        result = cad_file_export(
            FileExportInput(format="bogus", path=str(tmp_path / "x.foo"))
        )
        assert result.status == "error"
        assert "Unsupported" in result.message


class TestFileImport:
    """`cad_file_import` MCP tool."""

    def test_import_step(self, tmp_path) -> None:
        _new_doc()
        step_path = tmp_path / "out.step"
        cad_file_export(FileExportInput(format="step", path=str(step_path)))
        result = cad_file_import(FileImportInput(path=str(step_path)))
        assert isinstance(result, FileImportOutput)
        assert result.status == "success"
        assert result.object_count == 1
        assert result.file_id != ""

    def test_import_missing_file(self, tmp_path) -> None:
        result = cad_file_import(FileImportInput(path=str(tmp_path / "nope.step")))
        assert result.status == "error"
        assert result.object_count == 0

    def test_import_unsupported_suffix(self, tmp_path) -> None:
        bogus = tmp_path / "file.xyz"
        bogus.write_text("data", encoding="utf-8")
        result = cad_file_import(FileImportInput(path=str(bogus)))
        assert result.status == "error"
        assert "Unsupported" in result.message


class TestFileIoAggregate:
    """Aggregate cad_file_io tool (discriminated action)."""

    def test_action_export_formats_and_unsupported(self, tmp_path) -> None:
        _new_doc()
        for fmt, suffix in (("step", ".step"), ("dxf", ".dxf"), ("json", ".json")):
            target = tmp_path / f"out{suffix}"
            ok = cad_file_io(
                FileIoInput(
                    file=FileExportParams(format=fmt, path=str(target))
                )
            )
            assert ok.status == "success"
            assert ok.action == "export"
            assert target.exists()
        bad = cad_file_io(
            FileIoInput(file=FileExportParams(format="bogus", path=str(tmp_path / "x.foo")))
        )
        assert bad.status == "error"
        assert "Unsupported" in bad.message

    def test_action_import_success_and_errors(self, tmp_path) -> None:
        _new_doc()
        step_path = tmp_path / "out.step"
        cad_file_io(FileIoInput(file=FileExportParams(format="step", path=str(step_path))))
        ok = cad_file_io(FileIoInput(file=FileImportParams(path=str(step_path))))
        assert ok.status == "success"
        assert ok.action == "import"
        assert ok.object_count == 1
        assert ok.file_id != ""
        missing = cad_file_io(
            FileIoInput(file=FileImportParams(path=str(tmp_path / "nope.step")))
        )
        assert missing.status == "error"
        assert missing.object_count == 0
        bogus = tmp_path / "file.xyz"
        bogus.write_text("data", encoding="utf-8")
        unsupported = cad_file_io(FileIoInput(file=FileImportParams(path=str(bogus))))
        assert unsupported.status == "error"
        assert "Unsupported" in unsupported.message
