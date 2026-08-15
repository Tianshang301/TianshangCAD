"""Tests for the cam example plugin."""

from __future__ import annotations

from typing import Any

from tianshangcad.core.document import DocumentState
from tianshangcad.plugins.cam.gcode import emit_gcode
from tianshangcad.plugins.cam.plugin import CAMPlugin
from tianshangcad.plugins.cam.toolpath import build_toolpath


def _part(document: DocumentState) -> None:
    document.entities.create(
        "rectangle", {"origin": [0, 0, 0], "width": 50, "height": 30}, layer="Body"
    )
    document.entities.create(
        "circle", {"center": [10, 10, 0], "radius": 3}, layer="Hole"
    )


class TestToolpath:
    def test_contour_and_drill(self, document: DocumentState) -> None:
        _part(document)
        toolpath = build_toolpath(document.entities.list())
        assert len(toolpath.contours) == 1
        assert len(toolpath.drills) == 1

    def test_contour_is_closed(self, document: DocumentState) -> None:
        _part(document)
        contour = build_toolpath(document.entities.list()).contours[0]
        first = contour[0]
        last = contour[-1]
        assert (first.x, first.y) == (last.x, last.y)

    def test_path_length_positive(self, document: DocumentState) -> None:
        _part(document)
        assert build_toolpath(document.entities.list()).path_length > 0

    def test_drill_uses_circle_center(self, document: DocumentState) -> None:
        _part(document)
        drill = build_toolpath(document.entities.list()).drills[0]
        assert (drill.x, drill.y) == (10.0, 10.0)
        assert drill.depth < 0


class TestGcode:
    def test_emit_has_header_and_footer(self, document: DocumentState) -> None:
        _part(document)
        program = emit_gcode(build_toolpath(document.entities.list()))
        assert "G21" in program
        assert "G90" in program
        assert "G1" in program
        assert "M5" in program
        assert "M2" in program

    def test_emit_has_drill_cycle(self, document: DocumentState) -> None:
        _part(document)
        program = emit_gcode(build_toolpath(document.entities.list()))
        assert "X10" in program
        assert "Y10" in program


class TestPlugin:
    def test_registers_tool(self) -> None:
        registry: dict[str, Any] = {}
        CAMPlugin().register_tools(registry)
        assert "cad_cam" in registry

    def test_registers_command(self) -> None:
        registry: dict[str, Any] = {}
        CAMPlugin().register_commands(registry)
        assert "cam" in registry
