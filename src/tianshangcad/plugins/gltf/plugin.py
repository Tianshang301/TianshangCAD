"""glTF plugin: MCP tool, CLI command and plugin entry point.

Exposes ``cad_gltf`` (export / import / preview) and a ``gltf`` CLI group,
and registers both through the plugin SDK extension points.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

import typer
from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.core.plugins.sdk import CADPlugin, PluginManifest, PluginPermission
from tianshangcad.plugins.gltf.gltf import (
    export_gltf,
    export_gltf_file,
    import_gltf,
    load_gltf,
)
from tianshangcad.utils.errors import CADError

# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------


class GltfExportParams(BaseModel):
    """Export the current document to a glTF file."""

    action: Literal["export"] = "export"
    path: str = Field(..., description="Target .gltf path")
    pretty: bool = Field(True, description="Pretty-print the JSON")


class GltfImportParams(BaseModel):
    """Import a glTF file as mesh entities."""

    action: Literal["import"] = "import"
    path: str = Field(..., description="Source .gltf path")
    layer: str = Field("0", description="Layer for the imported meshes")


class GltfPreviewParams(BaseModel):
    """Preview the current document's glTF representation."""

    action: Literal["preview"] = "preview"


GltfActionParams = Annotated[
    GltfExportParams | GltfImportParams | GltfPreviewParams,
    Field(discriminator="action"),
]


class GltfInput(BaseModel):
    """Input for the aggregate gltf tool."""

    gltf: GltfActionParams = Field(
        ...,
        description="glTF action, discriminated by `action`: export, import or preview.",
    )


class GltfOutput(BaseModel):
    """Output of the aggregate gltf tool."""

    action: str = Field(..., description="Action executed")
    path: str = Field("", description="File path written / read")
    mesh_count: int = Field(0, description="Number of meshes exported / imported")
    object_ids: list[str] = Field(default_factory=list, description="Imported object ids")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def cad_gltf(input: GltfInput) -> GltfOutput:
    """Export, import or preview glTF 2.0 geometry.

    聚合 glTF 工具。按 ``action`` 派发：
    - ``export``: 将当前文档的实体（实体几何）导出为自包含 glTF 2.0 文件，
      颜色属性映射为 PBR ``baseColorFactor``。
    - ``import``: 读取 glTF 文件并把每个 mesh 作为 ``mesh`` 实体导入当前文档。
    - ``preview``: 返回当前文档 glTF 表示的概要（mesh 数 / 包围盒）。

    When not to use: 需要 STEP/DXF/STL 等工程格式互操作时用 ``cad_file``
    （import/export）；本工具专注 glTF 网格资产。
    """
    params = input.gltf
    manager = DocumentManager()
    try:
        doc = manager.get_current()
    except CADError as exc:
        return GltfOutput(action=params.action, status="error", message=str(exc))

    try:
        if params.action == "export":
            document = export_gltf(doc.entities.list())
            path = export_gltf_file(doc.entities.list(), params.path, pretty=params.pretty)
            return GltfOutput(
                action="export",
                path=path,
                mesh_count=len(document["meshes"]),
                status="success",
            )
        if params.action == "import":
            gltf = load_gltf(params.path)
            meshes = import_gltf(gltf)
            object_ids: list[str] = []
            for mesh in meshes:
                object_ids.append(
                    doc.entities.create(
                        "mesh",
                        {"vertices": mesh["vertices"], "faces": mesh["faces"]},
                        layer=params.layer,
                    )
                )
            doc.touch()
            return GltfOutput(
                action="import",
                path=params.path,
                mesh_count=len(meshes),
                object_ids=object_ids,
                status="success",
            )
        document = export_gltf(doc.entities.list())
        return GltfOutput(
            action="preview",
            mesh_count=len(document["meshes"]),
            status="success",
            message=f"{len(document['meshes'])} mesh(es), {len(document['materials'])} material(s)",
        )
    except CADError as exc:
        return GltfOutput(action=params.action, status="error", message=str(exc))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

app = typer.Typer(help="glTF 2.0 import/export")


@app.command("export")
def cmd_export(
    path: str = typer.Argument(..., help="Target .gltf path"),
    pretty: bool = typer.Option(True, "--pretty/--no-pretty", help="Pretty-print JSON"),
) -> None:
    """Export the current document to a self-contained glTF file."""
    doc = DocumentManager().get_current()
    export_gltf_file(doc.entities.list(), path, pretty=pretty)
    typer.echo(f"Exported glTF to {path}")


@app.command("import")
def cmd_import(
    path: str = typer.Argument(..., help="Source .gltf path"),
    layer: str = typer.Option("0", "--layer", "-l", help="Layer for imported meshes"),
) -> None:
    """Import a glTF file as mesh entities."""
    doc = DocumentManager().get_current()
    meshes = import_gltf(load_gltf(path))
    for mesh in meshes:
        doc.entities.create(
            "mesh", {"vertices": mesh["vertices"], "faces": mesh["faces"]}, layer=layer
        )
    doc.touch()
    typer.echo(f"Imported {len(meshes)} mesh(es) from {path}")


@app.command("preview")
def cmd_preview() -> None:
    """Summarize the current document's glTF representation."""
    doc = DocumentManager().get_current()
    document = export_gltf(doc.entities.list())
    typer.echo(f"{len(document['meshes'])} mesh(es), {len(document['materials'])} material(s)")


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class GLTFPlugin(CADPlugin):
    """glTF/GLB bidirectional import/export plugin (glTF 2.0, PBR materials)."""

    manifest = PluginManifest(
        name="gltf",
        version="0.1.0",
        description="Bidirectional glTF 2.0 import/export with PBR material mapping",
        author="Tianshang301",
        permissions=[PluginPermission.TOOLS, PluginPermission.COMMANDS],
    )

    def register_tools(self, registry: dict[str, Any]) -> None:
        """Register the ``cad_gltf`` aggregate tool."""
        registry["cad_gltf"] = cad_gltf

    def register_commands(self, registry: dict[str, Any]) -> None:
        """Register the ``gltf`` CLI group."""
        registry["gltf"] = app
