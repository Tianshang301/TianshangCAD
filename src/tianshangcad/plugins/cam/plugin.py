"""CAM plugin: MCP tool, CLI command and plugin entry point.

Exposes ``cad_cam`` (toolpath / simulate / export_gcode) and a ``cam`` CLI
group, registered through the plugin SDK extension points.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

import typer
from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.core.plugins.sdk import CADPlugin, PluginManifest, PluginPermission
from tianshangcad.plugins.cam.gcode import emit_gcode
from tianshangcad.plugins.cam.toolpath import build_toolpath
from tianshangcad.utils.errors import CADError

# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------


class CamToolpathParams(BaseModel):
    """Generate a 2.5-axis toolpath and return its summary."""

    action: Literal["toolpath"] = "toolpath"
    depth: float = Field(-10.0, description="Cutting depth (negative = below plane)")
    clearance: float = Field(5.0, description="Retract height above the XY plane")


class CamSimulateParams(BaseModel):
    """Simulate the toolpath and return a report."""

    action: Literal["simulate"] = "simulate"
    depth: float = Field(-10.0, description="Cutting depth")
    clearance: float = Field(5.0, description="Retract height")
    feed: float = Field(200.0, description="Feed rate (mm/min)")


class CamExportGcodeParams(BaseModel):
    """Generate and write a G-code program."""

    action: Literal["export_gcode"] = "export_gcode"
    path: str = Field(..., description="Target .nc / .gcode path")
    depth: float = Field(-10.0, description="Cutting depth")
    clearance: float = Field(5.0, description="Retract height")
    feed: float = Field(200.0, description="Feed rate (mm/min)")
    plunge: float = Field(100.0, description="Plunge feed rate (mm/min)")
    spindle: int = Field(2000, description="Spindle speed (RPM)")


CamActionParams = Annotated[
    CamToolpathParams | CamSimulateParams | CamExportGcodeParams,
    Field(discriminator="action"),
]


class CamInput(BaseModel):
    """Input for the aggregate cam tool."""

    cam: CamActionParams = Field(
        ...,
        description="CAM action, discriminated by `action`: toolpath, simulate or export_gcode.",
    )


class CamOutput(BaseModel):
    """Output of the aggregate cam tool."""

    action: str = Field(..., description="Action executed")
    path: str = Field("", description="Written G-code path")
    contour_count: int = Field(0, description="Number of contour operations")
    drill_count: int = Field(0, description="Number of drill operations")
    move_count: int = Field(0, description="Total tool moves")
    path_length: float = Field(0.0, description="Cutting path length (mm)")
    est_seconds: float = Field(0.0, description="Estimated machining time (s)")
    bounds: dict[str, list[float]] = Field(default_factory=dict, description="Toolpath bounds")
    line_count: int = Field(0, description="G-code line count")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def cad_cam(input: CamInput) -> CamOutput:
    """Generate, simulate or export 2.5-axis toolpaths (contour + drilling).

    聚合 CAM 工具。按 ``action`` 派发：
    - ``toolpath``: 从当前文档的矩形/多边形（轮廓）与圆（钻孔）生成 2.5 轴刀轨，
      返回轮廓数、钻孔数、刀轨长度与包围盒。
    - ``simulate``: 返回仿真报告（刀轨长度 + 估算加工时间）。
    - ``export_gcode``: 生成并写出 G-code（G0/G1 + 钻孔循环，M2 结束）。

    When not to use: 需要完整 3D 刀具路径或刀轴控制时超出本工具范围；本工具
    聚焦 2.5 轴轮廓铣削 + 钻孔。
    """
    params = input.cam
    try:
        doc = DocumentManager().get_current()
        toolpath = build_toolpath(
            doc.entities.list(), depth=params.depth, clearance=params.clearance
        )
    except CADError as exc:
        return CamOutput(action=params.action, status="error", message=str(exc))

    feed = getattr(params, "feed", 200.0)
    est_seconds = (toolpath.path_length / feed) * 60.0 if feed > 0 else 0.0

    if params.action == "export_gcode":
        program = emit_gcode(
            toolpath,
            clearance=params.clearance,
            feed=params.feed,
            plunge=params.plunge,
            spindle=params.spindle,
        )
        target = Path(params.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(program, encoding="utf-8")
        except OSError as exc:
            return CamOutput(action="export_gcode", status="error", message=str(exc))
        return CamOutput(
            action="export_gcode",
            path=str(target),
            contour_count=len(toolpath.contours),
            drill_count=len(toolpath.drills),
            move_count=toolpath.move_count,
            path_length=round(toolpath.path_length, 4),
            est_seconds=round(est_seconds, 2),
            bounds=toolpath.bounds,
            line_count=len(program.splitlines()),
            status="success",
        )

    return CamOutput(
        action=params.action,
        contour_count=len(toolpath.contours),
        drill_count=len(toolpath.drills),
        move_count=toolpath.move_count,
        path_length=round(toolpath.path_length, 4),
        est_seconds=round(est_seconds, 2),
        bounds=toolpath.bounds,
        status="success",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

app = typer.Typer(help="2.5-axis CAM toolpaths")


@app.command("toolpath")
def cmd_toolpath(
    depth: float = typer.Option(-10.0, "--depth", "-d", help="Cutting depth"),
    clearance: float = typer.Option(5.0, "--clearance", "-c", help="Retract height"),
) -> None:
    """Generate and print a 2.5-axis toolpath summary."""
    doc = DocumentManager().get_current()
    toolpath = build_toolpath(doc.entities.list(), depth=depth, clearance=clearance)
    typer.echo(
        f"{len(toolpath.contours)} contour(s), {len(toolpath.drills)} drill(s), "
        f"{toolpath.move_count} moves, {toolpath.path_length:.3f} mm"
    )


@app.command("gcode")
def cmd_gcode(
    path: str = typer.Argument(..., help="Target .nc / .gcode path"),
    depth: float = typer.Option(-10.0, "--depth", "-d", help="Cutting depth"),
    clearance: float = typer.Option(5.0, "--clearance", "-c", help="Retract height"),
) -> None:
    """Generate G-code and write it to a file."""
    doc = DocumentManager().get_current()
    toolpath = build_toolpath(doc.entities.list(), depth=depth, clearance=clearance)
    program = emit_gcode(toolpath, clearance=clearance)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(program, encoding="utf-8")
    typer.echo(f"Wrote {len(program.splitlines())} G-code lines to {path}")


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class CAMPlugin(CADPlugin):
    """2.5-axis CAM plugin: contour milling + drilling toolpaths to G-code."""

    manifest = PluginManifest(
        name="cam",
        version="0.1.0",
        description="2.5-axis contour + drilling toolpaths and G-code export",
        author="Tianshang301",
        permissions=[PluginPermission.TOOLS, PluginPermission.COMMANDS],
    )

    def register_tools(self, registry: dict[str, Any]) -> None:
        """Register the ``cad_cam`` aggregate tool."""
        registry["cad_cam"] = cad_cam

    def register_commands(self, registry: dict[str, Any]) -> None:
        """Register the ``cam`` CLI group."""
        registry["cam"] = app
