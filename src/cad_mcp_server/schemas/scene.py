"""Pydantic v2 scene schema model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from cad_mcp_server.schemas.geometry import GeometryObject


class LayerDefinition(BaseModel):
    """A layer definition."""

    name: str
    color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    linetype: str = "Continuous"
    linewidth: float = 0.25
    visible: bool = True
    locked: bool = False


class StyleDefinition(BaseModel):
    """A named style definition."""

    name: str
    type: Literal["dim", "text", "leader", "table"]
    properties: dict[str, Any] = Field(default_factory=dict)


class SceneDefinition(BaseModel):
    """A scene definition: the top-level interchange document."""

    scene_id: str = Field(..., description="Scene unique identifier")
    name: str = Field(..., description="Scene name")
    version: str = Field("1.0", description="Scene version")
    unit: str = Field("mm", description="Unit")

    layers: list[LayerDefinition] = Field(default_factory=list)
    styles: list[StyleDefinition] = Field(default_factory=list)
    objects: list[GeometryObject] = Field(default_factory=list)

    # Global settings
    grid_enabled: bool = True
    grid_size: float = 10.0
    snap_enabled: bool = True
    snap_mode: str = "endpoint"

    # Metadata
    created_by: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)

    # External references
    external_refs: list[dict[str, str]] = Field(default_factory=list)
