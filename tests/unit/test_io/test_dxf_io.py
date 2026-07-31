"""DXF import / export tests."""

from __future__ import annotations

import ezdxf

from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.io.exporters.dxf import DXFExporter
from cad_mcp_server.io.importers.dxf import DXFImporter


class TestDXFExport:
    """DXF export tests."""

    def _make_doc(self, document_manager: DocumentManager):
        doc_mgr = document_manager
        doc_mgr.create("part.json", unit="mm")
        doc = doc_mgr.get_current()
        doc.layers.create("Outline", color="#FF0000")
        doc.entities.create("line", {"start": [0, 0, 0], "end": [100, 0, 0]}, layer="Outline")
        doc.entities.create("circle", {"center": [50, 50, 0], "radius": 25}, layer="Outline")
        doc.entities.create(
            "rectangle", {"origin": [0, 0, 0], "width": 10, "height": 5}, layer="0"
        )
        return doc

    def test_export_document(self, document_manager: DocumentManager, tmp_path) -> None:
        doc = self._make_doc(document_manager)
        target = tmp_path / "out.dxf"
        DXFExporter().export_document(doc, str(target))
        assert target.is_file()
        d = ezdxf.readfile(str(target))
        entities = list(d.modelspace())
        types = {entity.dxftype() for entity in entities}
        assert "LINE" in types
        assert "CIRCLE" in types
        assert "LWPOLYLINE" in types

    def test_export_layers(self, document_manager: DocumentManager, tmp_path) -> None:
        doc = self._make_doc(document_manager)
        target = tmp_path / "layers.dxf"
        DXFExporter().export_document(doc, str(target))
        d = ezdxf.readfile(str(target))
        assert "Outline" in d.layers


class TestDXFImport:
    """DXF import tests."""

    def _write_dxf(self, path) -> None:
        d = ezdxf.new("R2010")
        layer = d.layers.add("L1")
        layer.rgb = (255, 0, 0)
        msp = d.modelspace()
        msp.add_line((0, 0, 0), (10, 0, 0), dxfattribs={"layer": "L1"})
        msp.add_circle((5, 5, 0), 2.5, dxfattribs={"layer": "L1"})
        msp.add_lwpolyline([(0, 0), (1, 1), (2, 0)], close=True)
        d.saveas(str(path))

    def test_import_file(self, tmp_path) -> None:
        path = tmp_path / "in.dxf"
        self._write_dxf(path)
        doc = DXFImporter().import_file(str(path))
        records = doc.entities.list()
        assert len(records) == 3
        by_type = {record.type for record in records}
        assert by_type == {"line", "circle", "polyline"}
        layers = {record.layer for record in records}
        assert "L1" in layers

    def test_roundtrip_bbox(self, document_manager: DocumentManager, tmp_path) -> None:
        doc_mgr = document_manager
        doc_mgr.create("a.json")
        doc = doc_mgr.get_current()
        doc.entities.create("circle", {"center": [0, 0, 0], "radius": 10})
        target = tmp_path / "round.dxf"
        DXFExporter().export_document(doc, str(target))
        imported = DXFImporter().import_file(str(target))
        bbox = imported.entities.get_bbox(imported.entities.list()[0].id)
        assert bbox["max"] == [10.0, 10.0, 0.0]

    def test_import_missing_file(self) -> None:
        import pytest

        from cad_mcp_server.utils.errors import CADImportError

        with pytest.raises(CADImportError):
            DXFImporter().import_file("/nope.dxf")

    def test_import_empty_dxf_raises(self, tmp_path) -> None:
        import pytest

        from cad_mcp_server.utils.errors import CADImportError

        path = tmp_path / "empty.dxf"
        d = ezdxf.new("R2010")
        d.saveas(str(path))
        with pytest.raises(CADImportError):
            DXFImporter().import_file(str(path))
