"""Tests for the layer manager."""

from __future__ import annotations

import pytest

from tianshangcad.core.layer_manager import LayerManager
from tianshangcad.utils.errors import LayerError


class TestLayerManager:
    """Layer CRUD tests."""

    def test_default_layer_exists(self) -> None:
        manager = LayerManager()
        assert manager.read("0").name == "0"
        assert manager.get_current().name == "0"

    def test_create_and_read(self) -> None:
        manager = LayerManager()
        layer = manager.create("Outline", color="#FF0000")
        assert layer.color == "#FF0000"
        assert manager.read("Outline") is layer

    def test_duplicate_raises(self) -> None:
        manager = LayerManager()
        manager.create("A")
        with pytest.raises(LayerError):
            manager.create("A")

    def test_invalid_color_raises(self) -> None:
        manager = LayerManager()
        with pytest.raises(LayerError):
            manager.create("Bad", color="red")

    def test_update(self) -> None:
        manager = LayerManager()
        manager.create("A", color="#FFFFFF")
        manager.update("A", color="#00FF00", linewidth=0.5)
        layer = manager.read("A")
        assert layer.color == "#00FF00"
        assert layer.linewidth == 0.5

    def test_set_current(self) -> None:
        manager = LayerManager()
        manager.create("A")
        manager.set_current("A")
        assert manager.get_current().name == "A"

    def test_set_current_missing_raises(self) -> None:
        manager = LayerManager()
        with pytest.raises(LayerError):
            manager.set_current("ghost")

    def test_delete_resets_current(self) -> None:
        manager = LayerManager()
        manager.create("A")
        manager.set_current("A")
        manager.delete("A")
        assert manager.get_current().name == "0"

    def test_delete_protected_layer(self) -> None:
        manager = LayerManager()
        with pytest.raises(LayerError):
            manager.delete("0")

    def test_list(self) -> None:
        manager = LayerManager()
        manager.create("A")
        manager.create("B")
        assert {layer.name for layer in manager.list()} == {"0", "A", "B"}

    def test_snapshot_roundtrip(self) -> None:
        manager = LayerManager()
        manager.create("A", color="#123456")
        snapshot = manager.snapshot()
        manager.delete("A")
        manager.restore(snapshot)
        assert manager.read("A").color == "#123456"
