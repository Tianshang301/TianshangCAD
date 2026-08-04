"""Tests for the entity manager."""

from __future__ import annotations

import pytest

from tianshangcad.core.entity import EntityManager, EntityRecord
from tianshangcad.core.transform import translation
from tianshangcad.utils.errors import EntityError


class TestCreate:
    """Entity creation tests."""

    def test_create_line(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create(
            "line", {"start": [0, 0, 0], "end": [100, 0, 0]}, layer="0"
        )
        assert entity_id
        assert entity_manager.get_bbox(entity_id) == {
            "min": [0.0, 0.0, 0.0],
            "max": [100.0, 0.0, 0.0],
        }

    def test_create_circle(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create(
            "circle", {"center": [50, 50, 0], "radius": 25}, layer="0"
        )
        bbox = entity_manager.get_bbox(entity_id)
        assert bbox["min"] == [25.0, 25.0, 0.0]
        assert bbox["max"] == [75.0, 75.0, 0.0]

    def test_create_box(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create(
            "box", {"origin": [0, 0, 0], "dimensions": [100, 50, 30]}, layer="0"
        )
        bbox = entity_manager.get_bbox(entity_id)
        assert bbox["max"] == [100.0, 50.0, 30.0]

    def test_create_rect_alias(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create(
            "rect", {"origin": [0, 0], "width": 10, "height": 5}
        )
        assert entity_manager.get(entity_id).type == "rectangle"

    def test_unsupported_type(self, entity_manager: EntityManager) -> None:
        with pytest.raises(EntityError):
            entity_manager.create("dodecahedron", {})

    def test_missing_params(self, entity_manager: EntityManager) -> None:
        with pytest.raises(EntityError):
            entity_manager.create("circle", {})


class TestReadUpdateDelete:
    """Entity CRUD tests."""

    def test_read(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create("line", {"start": [0, 0], "end": [1, 1]})
        record = entity_manager.read(entity_id)
        assert isinstance(record, EntityRecord)
        assert record.layer == "0"

    def test_read_missing_raises(self, entity_manager: EntityManager) -> None:
        with pytest.raises(EntityError):
            entity_manager.read("nope")

    def test_update_geometry(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create("line", {"start": [0, 0], "end": [1, 1]})
        entity_manager.update(entity_id, params={"start": [0, 0], "end": [10, 10]})
        assert entity_manager.get_bbox(entity_id)["max"] == [10.0, 10.0, 0.0]

    def test_update_properties(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create("line", {"start": [0, 0], "end": [1, 1]})
        entity_manager.update(entity_id, properties={"color": "#FF0000"})
        assert entity_manager.get(entity_id).properties["color"] == "#FF0000"

    def test_delete(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create("line", {"start": [0, 0], "end": [1, 1]})
        entity_manager.delete(entity_id)
        assert entity_manager.count() == 0

    def test_delete_missing_raises(self, entity_manager: EntityManager) -> None:
        with pytest.raises(EntityError):
            entity_manager.delete("nope")


class TestCopyTransform:
    """Copy and transform tests."""

    def test_copy(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create("circle", {"center": [0, 0], "radius": 5})
        new_id = entity_manager.copy(entity_id)
        assert new_id != entity_id
        assert entity_manager.get_bbox(new_id) == entity_manager.get_bbox(entity_id)
        assert entity_manager.count() == 2

    def test_transform_moves_bbox(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create("line", {"start": [0, 0], "end": [10, 0]})
        entity_manager.transform(entity_id, translation(5, 5, 0))
        assert entity_manager.get_bbox(entity_id) == {
            "min": [5.0, 5.0, 0.0],
            "max": [15.0, 5.0, 0.0],
        }

    def test_list_by_layer(self, entity_manager: EntityManager) -> None:
        entity_manager.create("line", {"start": [0, 0], "end": [1, 0]}, layer="A")
        entity_manager.create("line", {"start": [0, 0], "end": [1, 0]}, layer="B")
        entity_manager.create("line", {"start": [0, 0], "end": [1, 0]}, layer="A")
        assert len(entity_manager.list(layer="A")) == 2
        assert len(entity_manager.list()) == 3


class TestSnapshot:
    """Snapshot / restore tests."""

    def test_roundtrip(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create("line", {"start": [0, 0], "end": [1, 0]})
        snapshot = entity_manager.snapshot()
        entity_manager.delete(entity_id)
        assert entity_manager.count() == 0
        entity_manager.restore(snapshot)
        assert entity_manager.count() == 1
        assert entity_manager.get(entity_id).type == "line"

    def test_serialization_roundtrip(self, entity_manager: EntityManager) -> None:
        entity_id = entity_manager.create(
            "box", {"origin": [0, 0, 0], "dimensions": [10, 5, 2]}, layer="main"
        )
        record = entity_manager.get(entity_id)
        restored = EntityRecord.from_dict(record.to_dict())
        assert restored.id == entity_id
        assert restored.type == "box"


class TestBoolean:
    """Entity-level boolean operations."""

    def test_union_creates_mesh(self, entity_manager: EntityManager) -> None:
        pytest.importorskip("trimesh")
        a = entity_manager.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        b = entity_manager.create("box", {"origin": [1, 1, 1], "dimensions": [2, 2, 2]})
        result_id = entity_manager.boolean("union", a, b)
        record = entity_manager.get(result_id)
        assert record.type == "mesh"
        assert entity_manager.get_bbox(result_id) == {
            "min": [0.0, 0.0, 0.0],
            "max": [3.0, 3.0, 3.0],
        }
        assert entity_manager.count() == 3

    def test_subtract(self, entity_manager: EntityManager) -> None:
        pytest.importorskip("trimesh")
        a = entity_manager.create("box", {"origin": [0, 0, 0], "dimensions": [4, 4, 4]})
        b = entity_manager.create("box", {"origin": [1, 1, 1], "dimensions": [2, 2, 2]})
        result_id = entity_manager.boolean("subtract", a, b)
        record = entity_manager.get(result_id)
        assert record.type == "mesh"
        assert entity_manager.get_bbox(result_id) == {
            "min": [0.0, 0.0, 0.0],
            "max": [4.0, 4.0, 4.0],
        }

    def test_intersect(self, entity_manager: EntityManager) -> None:
        pytest.importorskip("trimesh")
        a = entity_manager.create("box", {"origin": [0, 0, 0], "dimensions": [4, 4, 4]})
        b = entity_manager.create("box", {"origin": [1, 1, 1], "dimensions": [2, 2, 2]})
        result_id = entity_manager.boolean("intersect", a, b)
        record = entity_manager.get(result_id)
        assert record.type == "mesh"
        assert entity_manager.get_bbox(result_id) == {
            "min": [1.0, 1.0, 1.0],
            "max": [3.0, 3.0, 3.0],
        }

    def test_unsupported_operation(self, entity_manager: EntityManager) -> None:
        a = entity_manager.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        b = entity_manager.create("box", {"origin": [1, 1, 1], "dimensions": [2, 2, 2]})
        with pytest.raises(EntityError) as exc:
            entity_manager.boolean("xor", a, b)
        assert exc.value.code == "unknown_boolean_op"

    def test_missing_entity_raises(self, entity_manager: EntityManager) -> None:
        pytest.importorskip("trimesh")
        a = entity_manager.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        with pytest.raises(EntityError):
            entity_manager.boolean("union", a, "nope")
        with pytest.raises(EntityError):
            entity_manager.boolean("union", "nope", a)
