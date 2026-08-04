"""Serialization utilities shared by importers and exporters."""

from __future__ import annotations

from typing import Any

from tianshangcad.core.entity import EntityRecord
from tianshangcad.core.kernel import Shape
from tianshangcad.schemas.geometry import GeometryObject


def shape_to_geometry_dict(shape: Shape) -> dict[str, Any]:
    """Convert an internal shape dict into a geometry dict with a ``type`` key."""
    return {"type": shape["kind"], **shape["params"]}


def geometry_dict_to_shape(geometry: dict[str, Any]) -> Shape:
    """Convert a geometry dict (with a ``type`` key) back into a shape dict."""
    kind = geometry["type"]
    params = {key: value for key, value in geometry.items() if key != "type"}
    return {"kind": kind, "params": params}


def record_to_geometry_object(record: EntityRecord) -> GeometryObject:
    """Convert an entity record to a validated geometry object."""
    return GeometryObject(
        id=record.id,
        type=record.type,
        layer=record.layer,
        properties=record.properties,
        geometry=shape_to_geometry_dict(record.shape),
        metadata=record.metadata,
    )


def geometry_object_to_record(obj: GeometryObject) -> EntityRecord:
    """Convert a geometry object back into an entity record."""
    return EntityRecord(
        entity_id=obj.id,
        type=obj.type,
        shape=geometry_dict_to_shape(obj.geometry.model_dump()),
        layer=obj.layer,
        properties=dict(obj.properties),
        metadata=dict(obj.metadata),
    )
