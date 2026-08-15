"""Tests for the gltf example plugin."""

from __future__ import annotations

from typing import Any

from tianshangcad.core.document import DocumentState
from tianshangcad.plugins.gltf.gltf import export_gltf, import_gltf
from tianshangcad.plugins.gltf.plugin import GLTFPlugin


def _box(document: DocumentState, **properties: Any) -> None:
    document.entities.create(
        "box",
        {"origin": [0, 0, 0], "dimensions": [10, 20, 30]},
        layer="Body",
        properties=properties or None,
    )


class TestExport:
    def test_export_has_gltf_asset(self, document: DocumentState) -> None:
        _box(document)
        gltf = export_gltf(document.entities.list())
        assert gltf["asset"]["version"] == "2.0"
        assert len(gltf["meshes"]) == 1

    def test_export_maps_color_to_pbr(self, document: DocumentState) -> None:
        _box(document, color="#FF0000")
        gltf = export_gltf(document.entities.list())
        material = gltf["materials"][0]
        assert material["pbrMetallicRoughness"]["baseColorFactor"] == [1.0, 0.0, 0.0, 1.0]

    def test_export_skips_wireframe(self, document: DocumentState) -> None:
        document.entities.create("line", {"start": [0, 0, 0], "end": [1, 1, 1]})
        assert len(export_gltf(document.entities.list())["meshes"]) == 0

    def test_export_empty_document(self, document: DocumentState) -> None:
        gltf = export_gltf(document.entities.list())
        assert gltf["meshes"] == []
        assert gltf["nodes"] == []


class TestRoundtrip:
    def test_export_import_roundtrip(self, document: DocumentState) -> None:
        _box(document)
        gltf = export_gltf(document.entities.list())
        meshes = import_gltf(gltf)
        assert len(meshes) == 1
        assert len(meshes[0]["vertices"]) == 8
        assert len(meshes[0]["faces"]) == 12

    def test_roundtrip_preserves_geometry(self, document: DocumentState) -> None:
        _box(document)
        gltf = export_gltf(document.entities.list())
        mesh = import_gltf(gltf)[0]
        xs = [v[0] for v in mesh["vertices"]]
        ys = [v[1] for v in mesh["vertices"]]
        zs = [v[2] for v in mesh["vertices"]]
        assert min(xs) == 0.0 and max(xs) == 10.0
        assert min(ys) == 0.0 and max(ys) == 20.0
        assert min(zs) == 0.0 and max(zs) == 30.0


class TestPlugin:
    def test_registers_tool(self) -> None:
        registry: dict[str, Any] = {}
        GLTFPlugin().register_tools(registry)
        assert "cad_gltf" in registry

    def test_registers_command(self) -> None:
        registry: dict[str, Any] = {}
        GLTFPlugin().register_commands(registry)
        assert "gltf" in registry
