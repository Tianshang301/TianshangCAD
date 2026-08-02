"""STL / STEP import-export tests."""

from __future__ import annotations

import struct

import pytest

from cad_mcp_server.core.document import DocumentManager, DocumentState
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
    """Pure-Python AP203 STEP round-trip tests."""

    def _export_and_import(
        self, document_manager: DocumentManager, tmp_path, *shapes: tuple[str, dict]
    ) -> DocumentState:
        doc_mgr = document_manager
        doc_mgr.create("part.json")
        doc = doc_mgr.get_current()
        for obj_type, params in shapes:
            doc.entities.create(obj_type, params)
        target = tmp_path / "out.step"
        STEPExporter().export_document(doc, str(target))
        return STEPImporter().import_file(str(target))

    def test_export_box_roundtrip(
        self, document_manager: DocumentManager, tmp_path
    ) -> None:
        imported = self._export_and_import(
            document_manager,
            tmp_path,
            ("box", {"origin": [0, 0, 0], "dimensions": [10, 10, 10]}),
        )
        record = imported.entities.list()[0]
        assert record.type == "mesh"
        assert len(record.shape["params"]["vertices"]) == 8
        assert len(record.shape["params"]["faces"]) == 12
        assert imported.entities.get_bbox(record.id) == {
            "min": [0.0, 0.0, 0.0],
            "max": [10.0, 10.0, 10.0],
        }

    def test_export_cylinder_sphere_roundtrip(
        self, document_manager: DocumentManager, tmp_path
    ) -> None:
        imported = self._export_and_import(
            document_manager,
            tmp_path,
            ("cylinder", {"origin": [0, 0, 0], "radius": 5, "height": 10, "axis": [0, 0, 1]}),
            ("sphere", {"center": [10, 10, 10], "radius": 3}),
        )
        records = imported.entities.list()
        assert len(records) == 2
        for record in records:
            assert record.type == "mesh"
            assert len(record.shape["params"]["faces"]) > 10

    def test_export_skips_2d_entities(
        self, document_manager: DocumentManager, tmp_path
    ) -> None:
        doc_mgr = document_manager
        doc_mgr.create("mixed.json")
        doc = doc_mgr.get_current()
        doc.entities.create("line", {"start": [0, 0, 0], "end": [1, 0, 0]})
        doc.entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        target = tmp_path / "mixed.step"
        STEPExporter().export_document(doc, str(target))
        imported = STEPImporter().import_file(str(target))
        assert len(imported.entities.list()) == 1

    def test_export_no_solid_raises(
        self, document_manager: DocumentManager, tmp_path
    ) -> None:
        doc_mgr = document_manager
        doc_mgr.create("empty.json")
        doc = doc_mgr.get_current()
        doc.entities.create("line", {"start": [0, 0, 0], "end": [1, 0, 0]})
        with pytest.raises(CADExportError):
            STEPExporter().export_document(doc, str(tmp_path / "out.step"))

    def test_import_missing_file(self, tmp_path) -> None:
        with pytest.raises(CADImportError) as exc:
            STEPImporter().import_file(str(tmp_path / "nope.step"))
        assert exc.value.code == "file_not_found"

    def test_import_garbage_raises(self, tmp_path) -> None:
        target = tmp_path / "garbage.step"
        target.write_text("not a step file", encoding="utf-8")
        with pytest.raises(CADImportError):
            STEPImporter().import_file(str(target))


class TestSTLImport:
    """STL importer stub tests."""

    def test_import_not_implemented(self) -> None:
        with pytest.raises(CADImportError):
            STLImporter().import_file("in.stl")
