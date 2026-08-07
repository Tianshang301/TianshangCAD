"""Tests for the measure MCP tools."""

from __future__ import annotations

import math

import pytest

from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from tianshangcad.mcp.tools.measure import (
    MeasureAreaInput,
    MeasureDistanceInput,
    cad_measure_area,
    cad_measure_distance,
)


def _seed_circle() -> str:
    cad_file_create(FileCreateInput(filename="measure.json"))
    result = cad_object_create(
        ObjectCreateInput(
            type="circle",
            params={"center": [0, 0, 0], "radius": 5},
            layer="0",
        )
    )
    return result.object_id


class TestMeasureDistance:
    """cad_measure_distance tool behaviour."""

    def test_distance_2d(self) -> None:
        cad_file_create(FileCreateInput(filename="m.json"))
        result = cad_measure_distance(
            MeasureDistanceInput(point_a=[0, 0], point_b=[3, 4])
        )
        assert result.status == "success"
        assert result.distance == pytest.approx(5.0)

    def test_distance_3d(self) -> None:
        cad_file_create(FileCreateInput(filename="m.json"))
        result = cad_measure_distance(
            MeasureDistanceInput(point_a=[0, 0, 0], point_b=[1, 1, 1])
        )
        assert result.status == "success"
        assert result.distance == pytest.approx(math.sqrt(3))

    def test_invalid_point(self) -> None:
        cad_file_create(FileCreateInput(filename="m.json"))
        result = cad_measure_distance(
            MeasureDistanceInput(point_a=[0], point_b=[3, 4])
        )
        assert result.status == "error"


class TestMeasureArea:
    """cad_measure_area tool behaviour."""

    def test_circle_area(self) -> None:
        object_id = _seed_circle()
        result = cad_measure_area(MeasureAreaInput(object_id=object_id))
        assert result.status == "success"
        assert result.kind == "area"
        assert result.unit == "mm^2"
        assert result.value == pytest.approx(math.pi * 25)

    def test_box_volume(self) -> None:
        cad_file_create(FileCreateInput(filename="m.json"))
        object_id = cad_object_create(
            ObjectCreateInput(
                type="box",
                params={"origin": [0, 0, 0], "dimensions": [2, 3, 4]},
                layer="0",
            )
        ).object_id
        result = cad_measure_area(MeasureAreaInput(object_id=object_id))
        assert result.status == "success"
        assert result.kind == "volume"
        assert result.unit == "mm^3"
        assert result.value == pytest.approx(24.0)

    def test_missing_object(self) -> None:
        cad_file_create(FileCreateInput(filename="m.json"))
        result = cad_measure_area(MeasureAreaInput(object_id="nope"))
        assert result.status == "error"

    def test_no_document(self) -> None:
        from tianshangcad.core.session import SessionManager

        SessionManager().reset()
        result = cad_measure_area(MeasureAreaInput(object_id="x"))
        assert result.status == "error"
