"""STL / STEP import-export tests."""

from __future__ import annotations

import struct

import pytest

from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.io.exporters.step import STEPExporter
from cad_mcp_server.io.exporters.stl import STLExporter
from cad_mcp_server.io.importers.step import STEPImporter
from cad_mcp_server.io.importers.stl import STLImporter
from cad_mcp_server.utils.errors import CADExportError, CADImportError


class TestSTLExporter:
    """Binary STL export tests."""

    def _make_doc(self, document_manager: DocumentManager):
        doc_mgr = document_manager
        doc_mgr.create("part.json")
        doc = doc_mgr.get_current()
        doc.entities.create("box", {"origin": [0, 0, 0], "dimensions": [10, 10, 10]})
        return doc

    def test_export_binary_stl(self, document_manager: DocumentManager, tmp_path) -> None:
        doc = self._make_doc(document_manager)
        target = tmp_path / "out.stl"
        STLExporter().export_document(doc, str(target))
        raw = target.read_bytes()
        count = struct.unpack("<I", raw[80:84])[0]
        assert count == 12
        assert len(raw) == 84 + 50 * count

    def test_export_no_solid_raises(self, document_manager: DocumentManager, tmp_path) -> None:
        doc_mgr = document_manager
        doc_mgr.create("empty.json")
        doc = doc_mgr.get_current()
        doc.entities.create("line", {"start": [0, 0, 0], "end": [1, 0, 0]})
        with pytest.raises(CADExportError):
            STLExporter().export_document(doc, str(tmp_path / "out.stl"))

    def test_export_cylinder(self, document_manager: DocumentManager, tmp_path) -> None:
        doc_mgr = document_manager
        doc_mgr.create("cyl.json")
        doc = doc_mgr.get_current()
        doc.entities.create(
            "cylinder", {"origin": [0, 0, 0], "radius": 5, "height": 10, "axis": [0, 0, 1]}
        )
        target = tmp_path / "cyl.stl"
        STLExporter().export_document(doc, str(target))
        raw = target.read_bytes()
        count = struct.unpack("<I", raw[80:84])[0]
        assert count > 0


class TestSTEP:
    """STEP backend-gated tests."""

    def test_export_requires_occ(self, document_manager: DocumentManager) -> None:
        doc_mgr = document_manager
        doc_mgr.create("a.json")
        with pytest.raises(CADExportError):
            STEPExporter().export_document(doc_mgr.get_current(), "out.step")

    def test_import_requires_occ(self) -> None:
        with pytest.raises(CADImportError):
            STEPImporter().import_file("in.step")


class TestSTLImport:
    """STL importer stub tests."""

    def test_import_not_implemented(self) -> None:
        with pytest.raises(CADImportError):
            STLImporter().import_file("in.stl")
