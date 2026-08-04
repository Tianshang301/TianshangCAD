"""Rendering and preview tools."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.render.renderer_2d import VALID_VIEWS, render_view
from tianshangcad.utils.config import get_settings
from tianshangcad.utils.errors import CADError, CADValidationError


class RenderViewInput(BaseModel):
    """Input for rendering an orthographic PNG view."""

    view: str = Field("top", description="View: top / front / side")
    dpi: int = Field(96, description="Resolution in DPI within [72, 300]")
    output: str | None = Field(None, description="Optional output PNG path")
    title: str | None = Field(None, description="Optional plot title")


class RenderViewOutput(BaseModel):
    """Output for PNG rendering."""

    path: str = Field(..., description="Path of the written PNG file")
    view: str = Field(..., description="Rendered view")
    dpi: int = Field(..., description="Used DPI")
    size_bytes: int = Field(..., description="PNG size in bytes")
    data_uri: str = Field(..., description="PNG data URI (base64)")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _default_output_path(view: str) -> str:
    temp = get_settings().temp_path
    temp.mkdir(parents=True, exist_ok=True)
    return str(temp / f"cad_view_{view}.png")


def cad_render_view(input: RenderViewInput) -> RenderViewOutput:
    """Render the current document to a PNG in an orthographic view.

    渲染当前文档的正交投影 PNG 视图。
    Views: ``top`` (XY), ``front`` (XZ), ``side`` (YZ). DPI must be between
    72 and 300. Returns the output path and a base64 data URI so the image
    can be embedded directly by MCP clients.
    """
    try:
        if input.view not in VALID_VIEWS:
            raise CADValidationError(
                f"Unknown view {input.view!r}; expected one of {', '.join(VALID_VIEWS)}",
                code="invalid_view",
            )
        doc = DocumentManager().get_current()
        records = doc.entities.list()
        output = input.output or _default_output_path(input.view)
        png = render_view(
            records,
            view=input.view,
            dpi=input.dpi,
            output=output,
            kernel=doc.entities.kernel,
            title=input.title,
        )
        data_uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        return RenderViewOutput(
            path=str(Path(output)),
            view=input.view,
            dpi=input.dpi,
            size_bytes=len(png),
            data_uri=data_uri,
            status="success",
            message=f"Rendered {input.view} view ({len(png)} bytes)",
        )
    except CADError as exc:
        return RenderViewOutput(
            path="",
            view=input.view,
            dpi=input.dpi,
            size_bytes=0,
            data_uri="",
            status="error",
            message=str(exc),
        )


TOOLS: list[tuple[str, Any]] = [
    ("cad_render_view", cad_render_view),
]
