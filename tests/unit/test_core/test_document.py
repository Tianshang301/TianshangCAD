"""Tests for document management."""

from __future__ import annotations

import json

import pytest

from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.utils.errors import CADImportError, CADValidationError, DocumentError


class TestCreate:
    """Document creation tests."""

    def test_create(self, document_manager: DocumentManager) -> None:
        file_id = document_manager.create("design.json", unit="mm")
        assert file_id
        doc = document_manager.get_current()
        assert doc.filename == "design.json"
        assert doc.unit == "mm"

    def test_create_invalid_unit(self, document_manager: DocumentManager) -> None:
        with pytest.raises(CADValidationError):
            document_manager.create("design.json", unit="parsec")

    def test_create_missing_template(self, document_manager: DocumentManager) -> None:
        with pytest.raises(DocumentError):
            document_manager.create("design.json", template="/nonexistent/tpl.json")


class TestSaveOpenRoundtrip:
    """Save / open roundtrip tests."""

    def test_save_and_open(self, document_manager: DocumentManager, tmp_path) -> None:
        doc_mgr = document_manager
        doc_mgr.create("design.json", unit="mm")
        doc = doc_mgr.get_current()
        doc.entities.create("circle", {"center": [50, 50, 0], "radius": 25})
        doc.layers.create("Outline", color="#FF0000")
        saved = doc_mgr.save(path=str(tmp_path / "design.json"))
        assert saved.endswith("design.json")

        doc_mgr2 = DocumentManager()
        file_id = doc_mgr2.open(str(tmp_path / "design.json"))
        reopened = doc_mgr2.get_current()
        assert reopened.unit == "mm"
        assert reopened.entities.count() == 1
        assert reopened.layers.read("Outline").color == "#FF0000"
        assert reopened.entities.get_bbox(reopened.entities.list()[0].id) == {
            "min": [25.0, 25.0, 0.0],
            "max": [75.0, 75.0, 0.0],
        }
        assert file_id != ""

    def test_save_without_path_raises(self, document_manager: DocumentManager) -> None:
        document_manager.create("design.json")
        with pytest.raises(DocumentError):
            document_manager.save()

    def test_open_missing_file(self, document_manager: DocumentManager) -> None:
        with pytest.raises(DocumentError):
            document_manager.open("/nonexistent/file.json")

    def test_open_invalid_json(self, document_manager: DocumentManager, tmp_path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(CADImportError):
            document_manager.open(str(bad))

    def test_file_content_roundtrip(self, document_manager: DocumentManager, tmp_path) -> None:
        document_manager.create("design.json")
        document_manager.get_current().entities.create(
            "box", {"origin": [0, 0, 0], "dimensions": [10, 10, 10]}
        )
        path = document_manager.save(path=str(tmp_path / "design.json"))
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        assert data["format"] == "tianshang-cad-scene"
        assert len(data["entities"]) == 1


class TestCloseAndList:
    """Close / list / info tests."""

    def test_close(self, document_manager: DocumentManager) -> None:
        file_id = document_manager.create("design.json")
        document_manager.close(file_id)
        assert document_manager.list() == []
        with pytest.raises(DocumentError):
            document_manager.get_current()

    def test_list_and_info(self, document_manager: DocumentManager) -> None:
        document_manager.create("a.json")
        document_manager.create("b.json", unit="cm")
        docs = document_manager.list()
        assert len(docs) == 2
        info = document_manager.info()
        assert info["filename"] == "b.json"
        assert info["unit"] == "cm"
        assert info["entity_count"] == 0

    def test_close_missing_raises(self, document_manager: DocumentManager) -> None:
        with pytest.raises(DocumentError):
            document_manager.close("ghost")

    def test_no_active_document(self, document_manager: DocumentManager) -> None:
        with pytest.raises(DocumentError):
            document_manager.get_current()
