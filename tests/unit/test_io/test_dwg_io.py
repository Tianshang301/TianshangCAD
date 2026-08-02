"""DWG exporter/importer tests (ODA File Converter bridge)."""

from __future__ import annotations

import pytest

from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.io.exporters.dwg import DWGExporter
from cad_mcp_server.io.importers.dwg import DWGImporter
from cad_mcp_server.utils.errors import CADExportError, CADImportError


class TestDWGExporter:
    """DWG exporter tests."""

    def test_export_requires_odafc(
        self, document_manager: DocumentManager, monkeypatch, tmp_path
    ) -> None:
        doc_mgr = document_manager
        doc_mgr.create("part.json")
        doc = doc_mgr.get_current()
        doc.entities.create("box", {"origin": [0, 0, 0], "dimensions": [10, 10, 10]})
        monkeypatch.setattr("ezdxf.addons.odafc.is_installed", lambda: False)
        with pytest.raises(CADExportError) as exc:
            DWGExporter().export_document(doc, str(tmp_path / "out.dwg"))
        assert exc.value.code == "requires_odafc"

    def test_export_success_mocked(
        self, document_manager: DocumentManager, monkeypatch, tmp_path
    ) -> None:
        doc_mgr = document_manager
        doc_mgr.create("part.json")
        doc = doc_mgr.get_current()
        doc.entities.create("box", {"origin": [0, 0, 0], "dimensions": [10, 10, 10]})

        convert_calls: list[tuple] = []

        def fake_convert(source, dest, **kwargs):
            convert_calls.append((source, dest))
            import pathlib

            pathlib.Path(dest).write_bytes(b"DWG")

        monkeypatch.setattr("ezdxf.addons.odafc.is_installed", lambda: True)
        monkeypatch.setattr("ezdxf.addons.odafc.convert", fake_convert)
        target = tmp_path / "out.dwg"
        DWGExporter().export_document(doc, str(target))
        assert target.read_bytes() == b"DWG"
        assert len(convert_calls) == 1
        _, dest = convert_calls[0]
        assert str(dest) == str(target.resolve())


class TestDWGImporter:
    """DWG importer tests."""

    def test_import_missing_file(self, tmp_path) -> None:
        with pytest.raises(CADImportError):
            DWGImporter().import_file(str(tmp_path / "nope.dwg"))

    def test_import_requires_odafc(self, monkeypatch, tmp_path) -> None:
        source = tmp_path / "in.dwg"
        source.write_bytes(b"dwg-data")
        monkeypatch.setattr("ezdxf.addons.odafc.is_installed", lambda: False)
        with pytest.raises(CADImportError) as exc:
            DWGImporter().import_file(str(source))
        assert exc.value.code == "requires_odafc"

    def test_import_success_mocked(
        self, monkeypatch, tmp_path, document_manager: DocumentManager
    ) -> None:
        source = tmp_path / "in.dwg"
        source.write_bytes(b"dwg-data")

        def fake_convert(source_path, dest):
            import pathlib

            dxf = pathlib.Path(dest)
            dxf.write_text(
                "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0.0\n20\n0.0\n"
                "30\n0.0\n11\n100.0\n21\n0.0\n31\n0.0\n0\nENDSEC\n0\nEOF\n",
                encoding="utf-8",
            )

        monkeypatch.setattr("ezdxf.addons.odafc.is_installed", lambda: True)
        monkeypatch.setattr("ezdxf.addons.odafc.convert", fake_convert)
        doc = DWGImporter().import_file(str(source))
        assert len(doc.entities.list()) == 1
        record = doc.entities.list()[0]
        assert record.type == "line"
