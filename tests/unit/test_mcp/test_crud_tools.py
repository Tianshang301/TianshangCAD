"""CRUD tool unit tests (files, objects, layers)."""

from __future__ import annotations

import json

from cad_mcp_server.mcp.tools.crud import (
    FileCreateInput,
    FileListInput,
    FileSaveInput,
    LayerCreateInput,
    LayerDeleteInput,
    LayerListInput,
    LayerReadInput,
    LayerUpdateInput,
    ObjectCreateInput,
    ObjectDeleteInput,
    ObjectListInput,
    ObjectReadInput,
    ObjectUpdateInput,
    cad_file_create,
    cad_file_list,
    cad_file_save,
    cad_layer_create,
    cad_layer_delete,
    cad_layer_list,
    cad_layer_read,
    cad_layer_update,
    cad_object_create,
    cad_object_delete,
    cad_object_list,
    cad_object_read,
    cad_object_update,
)


class TestFileTools:
    """File CRUD tools."""

    def test_create_success(self) -> None:
        result = cad_file_create(FileCreateInput(filename="part.dwg", unit="mm"))
        assert result.status == "success"
        assert result.file_id.startswith("file_")
        assert "part.dwg" in result.message

    def test_create_invalid_unit(self) -> None:
        result = cad_file_create(FileCreateInput(filename="part.dwg", unit="parsec"))
        assert result.status == "error"
        assert result.file_id == ""

    def test_list(self) -> None:
        cad_file_create(FileCreateInput(filename="a.dwg"))
        cad_file_create(FileCreateInput(filename="b.dwg"))
        result = cad_file_list(FileListInput())
        assert result.status == "success"
        assert len(result.files) == 2

    def test_save_requires_path(self) -> None:
        cad_file_create(FileCreateInput(filename="untitled.dwg"))
        result = cad_file_save(FileSaveInput())
        assert result.status == "error"
        assert "path" in result.message

    def test_save_to_path(self, tmp_path) -> None:
        cad_file_create(FileCreateInput(filename="scene.json"))
        target = tmp_path / "scene.json"
        result = cad_file_save(FileSaveInput(path=str(target)))
        assert result.status == "success"
        assert result.path == str(target)
        assert target.exists()


def _create_document_with_objects() -> str:
    cad_file_create(FileCreateInput(filename="draw.json"))
    created = cad_object_create(
        ObjectCreateInput(
            type="line",
            params={"start": [0, 0, 0], "end": [100, 0, 0]},
            layer="0",
        )
    )
    assert created.status == "success"
    return created.object_id


class TestObjectTools:
    """Object CRUD tools."""

    def test_create_line(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        result = cad_object_create(
            ObjectCreateInput(
                type="line",
                params={"start": [0, 0, 0], "end": [100, 0, 0]},
                layer="0",
            )
        )
        assert result.status == "success"
        assert result.bbox["min"] == [0.0, 0.0, 0.0]
        assert result.bbox["max"] == [100.0, 0.0, 0.0]

    def test_create_box(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        result = cad_object_create(
            ObjectCreateInput(
                type="box",
                params={"origin": [0, 0, 0], "dimensions": [10, 20, 30]},
                layer="0",
            )
        )
        assert result.status == "success"
        assert result.bbox["max"] == [10.0, 20.0, 30.0]

    def test_create_unsupported_type(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        result = cad_object_create(
            ObjectCreateInput(type="banana", params={}, layer="0")
        )
        assert result.status == "error"
        assert "Unsupported object type" in result.message

    def test_read(self) -> None:
        object_id = _create_document_with_objects()
        result = cad_object_read(ObjectReadInput(object_id=object_id))
        assert result.status == "success"
        assert result.type == "line"
        assert result.geometry["start"] == [0, 0, 0]

    def test_read_missing(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        result = cad_object_read(ObjectReadInput(object_id="nope"))
        assert result.status == "error"

    def test_update(self) -> None:
        object_id = _create_document_with_objects()
        result = cad_object_update(
            ObjectUpdateInput(object_id=object_id, layer="LayerA")
        )
        assert result.status == "success"
        read = cad_object_read(ObjectReadInput(object_id=object_id))
        assert read.layer == "LayerA"

    def test_delete(self) -> None:
        object_id = _create_document_with_objects()
        result = cad_object_delete(ObjectDeleteInput(object_id=object_id))
        assert result.status == "success"
        read = cad_object_read(ObjectReadInput(object_id=object_id))
        assert read.status == "error"

    def test_list_filter_by_layer(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        first = cad_object_create(
            ObjectCreateInput(
                type="circle",
                params={"center": [5, 5, 0], "radius": 2},
                layer="A",
            )
        )
        cad_object_create(
            ObjectCreateInput(
                type="circle",
                params={"center": [15, 5, 0], "radius": 2},
                layer="B",
            )
        )
        result = cad_object_list(ObjectListInput(layer="A"))
        assert result.status == "success"
        assert [obj["object_id"] for obj in result.objects] == [first.object_id]


class TestLayerTools:
    """Layer CRUD tools."""

    def test_create_read(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        created = cad_layer_create(
            LayerCreateInput(name="Outline", color="#FF0000")
        )
        assert created.status == "success"
        read = cad_layer_read(LayerReadInput(name="Outline"))
        assert read.color == "#FF0000"
        assert read.visible is True

    def test_create_invalid_color(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        result = cad_layer_create(LayerCreateInput(name="Bad", color="red"))
        assert result.status == "error"

    def test_update(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_layer_create(LayerCreateInput(name="Outline"))
        result = cad_layer_update(
            LayerUpdateInput(name="Outline", locked=True, color="#00FF00")
        )
        assert result.status == "success"
        read = cad_layer_read(LayerReadInput(name="Outline"))
        assert read.locked is True
        assert read.color == "#00FF00"

    def test_delete(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_layer_create(LayerCreateInput(name="Temp"))
        result = cad_layer_delete(LayerDeleteInput(name="Temp"))
        assert result.status == "success"
        read = cad_layer_read(LayerReadInput(name="Temp"))
        assert read.status == "error"

    def test_list(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_layer_create(LayerCreateInput(name="A"))
        cad_layer_create(LayerCreateInput(name="B"))
        result = cad_layer_list(LayerListInput())
        assert result.status == "success"
        assert {layer["name"] for layer in result.layers} >= {"A", "B"}


def test_object_list_no_document() -> None:
    result = cad_object_list(ObjectListInput())
    assert result.status == "error"


def test_layer_list_no_document() -> None:
    result = cad_layer_list(LayerListInput())
    assert result.status == "error"


def test_cad_file_save_roundtrip(tmp_path) -> None:
    cad_file_create(FileCreateInput(filename="scene.json"))
    cad_object_create(
        ObjectCreateInput(
            type="circle",
            params={"center": [10, 10, 0], "radius": 5},
            layer="0",
        )
    )
    target = tmp_path / "scene.json"
    saved = cad_file_save(FileSaveInput(path=str(target)))
    assert saved.status == "success"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["filename"] == "scene.json"
    assert len(data["entities"]) == 1
