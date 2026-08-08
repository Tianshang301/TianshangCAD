"""CRUD tools: files, geometry objects and layers."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.utils.errors import CADError

# ---------------------------------------------------------------------------
# File tools
# ---------------------------------------------------------------------------


class FileCreateInput(BaseModel):
    """Input for creating a new file."""

    filename: str = Field(..., description="File name with extension")
    template: str | None = Field(None, description="Template file path")
    unit: str = Field("mm", description="Unit: mm, cm, m, in, ft")


class FileCreateOutput(BaseModel):
    """Output for file creation."""

    file_id: str = Field(..., description="File unique identifier")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class FileOpenInput(BaseModel):
    """Input for opening a JSON scene file."""

    path: str = Field(..., description="File path to open")


class FileOpenOutput(BaseModel):
    """Output for opening a file."""

    file_id: str = Field(..., description="File unique identifier")
    filename: str = Field(..., description="Opened file name")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class FileSaveInput(BaseModel):
    """Input for saving the current file."""

    path: str | None = Field(None, description="Target path (defaults to current)")
    file_id: str | None = Field(None, description="File id to save (defaults to current)")


class FileSaveOutput(BaseModel):
    """Output for saving a file."""

    path: str = Field(..., description="Saved path")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class FileCloseInput(BaseModel):
    """Input for closing a file."""

    file_id: str | None = Field(None, description="File id to close (defaults to current)")


class FileCloseOutput(BaseModel):
    """Output for closing a file."""

    file_id: str = Field(..., description="Closed file id")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class FileDeleteInput(BaseModel):
    """Input for deleting a file from the session."""

    file_id: str = Field(..., description="File id to delete")


class FileDeleteOutput(BaseModel):
    """Output for deleting a file."""

    file_id: str = Field(..., description="Deleted file id")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def cad_file_create(input: FileCreateInput) -> FileCreateOutput:
    """Create a new CAD file.

    Initializes a new design document with an optional template and unit.
    Returns the file id required for subsequent operations.
    """
    try:
        file_id = DocumentManager().create(
            filename=input.filename,
            template=input.template,
            unit=input.unit,
        )
        return FileCreateOutput(
            file_id=file_id,
            status="success",
            message=f"File {input.filename} created successfully",
        )
    except CADError as exc:
        return FileCreateOutput(file_id="", status="error", message=str(exc))


def cad_file_open(input: FileOpenInput) -> FileOpenOutput:
    """Open an existing JSON scene file.

    打开一个 JSON 场景文件并设为当前文档。The file must be a scene snapshot
    written by ``cad_file_save`` or ``cad_json`` (save/export_scene).

    When not to use: for DXF/STEP/STL import use ``cad_file_io`` (import)
    instead — this tool only reads JSON scenes. Opening replaces the
    current document.
    """
    try:
        file_id = DocumentManager().open(input.path)
        doc = DocumentManager().get_current()
        return FileOpenOutput(
            file_id=file_id,
            filename=doc.filename,
            status="success",
            message=f"Opened {input.path}",
        )
    except CADError as exc:
        return FileOpenOutput(file_id="", filename="", status="error", message=str(exc))


def cad_file_save(input: FileSaveInput) -> FileSaveOutput:
    """Save a document to disk.

    保存文档到磁盘。Defaults to the current document; pass ``file_id`` to
    save another open file and ``path`` to override the destination. The
    saved file is a JSON scene snapshot that ``cad_file_open`` can reload.

    When not to use: to export to STEP/DXF/STL use ``cad_file_io``
    (export) — ``cad_file_save`` always writes the JSON scene format.
    """
    try:
        path = DocumentManager().save(file_id=input.file_id, path=input.path)
        return FileSaveOutput(path=path, status="success", message="Saved")
    except CADError as exc:
        return FileSaveOutput(path="", status="error", message=str(exc))


def cad_file_close(input: FileCloseInput) -> FileCloseOutput:
    """Close a document (defaults to the current document)."""
    try:
        manager = DocumentManager()
        doc = manager._require(input.file_id)
        file_id = doc.file_id
        manager.close(file_id)
        return FileCloseOutput(file_id=file_id, status="success", message="Closed")
    except CADError as exc:
        return FileCloseOutput(file_id="", status="error", message=str(exc))


def cad_file_delete(input: FileDeleteInput) -> FileDeleteOutput:
    """Delete a document from the session (does not touch the file on disk).

    从会话中删除文档（不删除磁盘文件）。不可撤销，请谨慎使用。
    """
    try:
        DocumentManager().delete(input.file_id)
        return FileDeleteOutput(file_id=input.file_id, status="success", message="Deleted")
    except CADError as exc:
        return FileDeleteOutput(file_id="", status="error", message=str(exc))


# ---------------------------------------------------------------------------
# Object tools
# ---------------------------------------------------------------------------


class ObjectCreateInput(BaseModel):
    """Input for creating a geometry object."""

    type: str = Field(
        ...,
        description=(
            "Object type: line, circle, arc, rectangle, polygon, "
            "polyline, box, cylinder, sphere, cone"
        ),
    )
    params: dict[str, Any] = Field(..., description="Geometry parameters, varies by type")
    layer: str = Field("0", description="Target layer name")
    properties: dict[str, Any] | None = Field(
        None, description="Object properties: color, linetype, linewidth"
    )


class ObjectCreateOutput(BaseModel):
    """Output for creating an object."""

    object_id: str = Field(..., description="Object unique identifier")
    bbox: dict[str, list[float]] = Field(
        ..., description="Bounding box: {min: [x,y,z], max: [x,y,z]}"
    )
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ObjectReadInput(BaseModel):
    """Input for reading an object."""

    object_id: str = Field(..., description="Object unique identifier")


class ObjectReadOutput(BaseModel):
    """Output for reading an object."""

    object_id: str = Field(..., description="Object unique identifier")
    type: str = Field(..., description="Object type")
    layer: str = Field(..., description="Layer name")
    geometry: dict[str, Any] = Field(..., description="Geometry parameters")
    properties: dict[str, Any] = Field(default_factory=dict, description="Object properties")
    bbox: dict[str, list[float]] = Field(..., description="Bounding box")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ObjectUpdateInput(BaseModel):
    """Input for updating an object."""

    object_id: str = Field(..., description="Object unique identifier")
    params: dict[str, Any] | None = Field(None, description="New geometry parameters")
    layer: str | None = Field(None, description="New layer")
    properties: dict[str, Any] | None = Field(None, description="New properties to merge")


class ObjectUpdateOutput(BaseModel):
    """Output for updating an object."""

    object_id: str = Field(..., description="Object unique identifier")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ObjectDeleteInput(BaseModel):
    """Input for deleting an object."""

    object_id: str = Field(..., description="Object unique identifier")


class ObjectDeleteOutput(BaseModel):
    """Output for deleting an object."""

    object_id: str = Field(..., description="Deleted object id")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ObjectCopyInput(BaseModel):
    """Input for copying an object."""

    object_id: str = Field(..., description="Object unique identifier")
    new_id: str | None = Field(None, description="Id for the copy (auto-generated if empty)")


class ObjectCopyOutput(BaseModel):
    """Output for copying an object."""

    object_id: str = Field(..., description="New object id")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ObjectTransformInput(BaseModel):
    """Input for transforming an object with a 4x4 matrix."""

    object_id: str = Field(..., description="Object unique identifier")
    matrix: list[list[float]] = Field(..., description="4x4 transformation matrix")


class ObjectTransformOutput(BaseModel):
    """Output for transforming an object."""

    object_id: str = Field(..., description="Object unique identifier")
    bbox: dict[str, list[float]] = Field(..., description="Bounding box after transform")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def cad_object_create(input: ObjectCreateInput) -> ObjectCreateOutput:
    """Create a geometry object.

    Creates an entity based on the given type and parameters. Supported
    types include line, circle, arc, rectangle, polygon, polyline, box,
    cylinder, sphere and cone.
    """
    try:
        doc = DocumentManager().get_current()
        object_id = doc.entities.create(
            obj_type=input.type,
            params=dict(input.params),
            layer=input.layer,
            properties=dict(input.properties or {}),
        )
        from tianshangcad.utils.metrics import observe_entity

        observe_entity(input.type.lower())
        bbox = doc.entities.get_bbox(object_id)
        return ObjectCreateOutput(object_id=object_id, bbox=bbox, status="success")
    except CADError as exc:
        return ObjectCreateOutput(
            object_id="",
            bbox={"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
            status="error",
            message=str(exc),
        )


def cad_object_read(input: ObjectReadInput) -> ObjectReadOutput:
    """Read an object's geometry, layer, properties and bounding box."""
    try:
        doc = DocumentManager().get_current()
        record = doc.entities.read(input.object_id)
        bbox = doc.entities.get_bbox(input.object_id)
        return ObjectReadOutput(
            object_id=record.id,
            type=record.type,
            layer=record.layer,
            geometry=dict(record.shape["params"]),
            properties=dict(record.properties),
            bbox=bbox,
            status="success",
        )
    except CADError as exc:
        return ObjectReadOutput(
            object_id=input.object_id,
            type="",
            layer="",
            geometry={},
            bbox={"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
            status="error",
            message=str(exc),
        )


def cad_object_update(input: ObjectUpdateInput) -> ObjectUpdateOutput:
    """Update an object's geometry, layer and/or properties.

    更新对象。Only the fields you pass change: ``params`` replaces geometry,
    ``layer`` moves the object, ``properties`` overrides appearance. Pass
    ``None`` for a field to leave it untouched.

    When not to use: to translate/rotate/scale use ``cad_object_transform``
    (matrix-based) — this tool edits parameters directly. To create a
    derived copy use ``cad_object_copy``.
    """
    try:
        doc = DocumentManager().get_current()
        doc.entities.update(
            entity_id=input.object_id,
            params=dict(input.params) if input.params is not None else None,
            layer=input.layer,
            properties=input.properties,
        )
        return ObjectUpdateOutput(
            object_id=input.object_id, status="success", message="Updated"
        )
    except CADError as exc:
        return ObjectUpdateOutput(object_id="", status="error", message=str(exc))


def cad_object_delete(input: ObjectDeleteInput) -> ObjectDeleteOutput:
    """Delete an object from the current document."""
    try:
        doc = DocumentManager().get_current()
        doc.entities.delete(input.object_id)
        return ObjectDeleteOutput(
            object_id=input.object_id, status="success", message="Deleted"
        )
    except CADError as exc:
        return ObjectDeleteOutput(object_id="", status="error", message=str(exc))


def cad_object_copy(input: ObjectCopyInput) -> ObjectCopyOutput:
    """Copy an object, returning the new object's id."""
    try:
        doc = DocumentManager().get_current()
        target_id = doc.entities.copy(input.object_id, new_id=input.new_id)
        return ObjectCopyOutput(object_id=target_id, status="success", message="Copied")
    except CADError as exc:
        return ObjectCopyOutput(object_id="", status="error", message=str(exc))


def cad_object_transform(input: ObjectTransformInput) -> ObjectTransformOutput:
    """Apply a 4x4 matrix to an object's geometry.

    对对象应用 4x4 变换矩阵（平移/旋转/缩放）。列向量约定：平移量位于
    第四列（matrix[0][3]、matrix[1][3]、matrix[2][3]）。
    """
    try:
        import numpy as np

        matrix = np.asarray(input.matrix, dtype=float)
        if matrix.shape != (4, 4):
            raise CADError("matrix must be 4x4", code="invalid_matrix")
        doc = DocumentManager().get_current()
        doc.entities.transform(input.object_id, matrix)
        bbox = doc.entities.get_bbox(input.object_id)
        return ObjectTransformOutput(
            object_id=input.object_id, bbox=bbox, status="success", message="Transformed"
        )
    except CADError as exc:
        return ObjectTransformOutput(
            object_id=input.object_id,
            bbox={"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
            status="error",
            message=str(exc),
        )


# ---------------------------------------------------------------------------
# Layer tools
# ---------------------------------------------------------------------------


class LayerCreateInput(BaseModel):
    """Input for creating a layer."""

    name: str = Field(..., description="Layer name")
    color: str = Field("#FFFFFF", description="Layer color as #RRGGBB")
    linetype: str = Field("Continuous", description="Line type")
    linewidth: float = Field(0.25, description="Line width")


class LayerCreateOutput(BaseModel):
    """Output for creating a layer."""

    name: str = Field(..., description="Created layer name")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class LayerReadInput(BaseModel):
    """Input for reading a layer."""

    name: str = Field(..., description="Layer name")


class LayerReadOutput(BaseModel):
    """Output for reading a layer."""

    name: str = Field(..., description="Layer name")
    color: str = Field(..., description="Layer color")
    linetype: str = Field(..., description="Line type")
    linewidth: float = Field(..., description="Line width")
    visible: bool = Field(..., description="Visibility")
    locked: bool = Field(..., description="Lock state")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class LayerUpdateInput(BaseModel):
    """Input for updating a layer."""

    name: str = Field(..., description="Layer name")
    color: str | None = Field(None, description="New color as #RRGGBB")
    linetype: str | None = Field(None, description="New line type")
    linewidth: float | None = Field(None, description="New line width")
    visible: bool | None = Field(None, description="Visibility")
    locked: bool | None = Field(None, description="Lock state")


class LayerUpdateOutput(BaseModel):
    """Output for updating a layer."""

    name: str = Field(..., description="Updated layer name")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class LayerDeleteInput(BaseModel):
    """Input for deleting a layer."""

    name: str = Field(..., description="Layer name")


class LayerDeleteOutput(BaseModel):
    """Output for deleting a layer."""

    name: str = Field(..., description="Deleted layer name")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def cad_layer_create(input: LayerCreateInput) -> LayerCreateOutput:
    """Create a layer in the current document.

    创建图层。Accepts an optional color/linetype/linewidth; layers are used
    to group objects for display and selection.

    When not to use: if you only need one group, the default ``0`` layer is
    created implicitly — create a layer only when grouping matters.
    """
    try:
        doc = DocumentManager().get_current()
        doc.layers.create(
            name=input.name,
            color=input.color,
            linetype=input.linetype,
            linewidth=input.linewidth,
        )
        return LayerCreateOutput(name=input.name, status="success", message="Created")
    except CADError as exc:
        return LayerCreateOutput(name="", status="error", message=str(exc))


def cad_layer_read(input: LayerReadInput) -> LayerReadOutput:
    """Read a layer's definition from the current document.

    读取图层定义（颜色、线型、线宽、可见/锁定状态）。

    When not to use: to enumerate all layers use ``cad_layer_list``; this
    tool returns a single named layer and errors if it is missing.
    """
    try:
        doc = DocumentManager().get_current()
        layer = doc.layers.read(input.name)
        return LayerReadOutput(
            name=layer.name,
            color=layer.color,
            linetype=layer.linetype,
            linewidth=layer.linewidth,
            visible=layer.visible,
            locked=layer.locked,
            status="success",
        )
    except CADError as exc:
        return LayerReadOutput(
            name=input.name,
            color="",
            linetype="",
            linewidth=0.0,
            visible=False,
            locked=False,
            status="error",
            message=str(exc),
        )


def cad_layer_update(input: LayerUpdateInput) -> LayerUpdateOutput:
    """Update a layer's attributes.

    更新图层属性。Only the fields you pass are changed; provide the layer
    ``name`` plus any of color, linetype, linewidth, visible or locked to
    override. Returns the updated definition.

    When not to use: to rename a layer you must update its ``name`` field
    directly; there is no separate rename operation. Deleting a layer is
    ``cad_layer_delete`` (destructive).
    """
    try:
        doc = DocumentManager().get_current()
        kwargs: dict[str, Any] = {}
        if input.color is not None:
            kwargs["color"] = input.color
        if input.linetype is not None:
            kwargs["linetype"] = input.linetype
        if input.linewidth is not None:
            kwargs["linewidth"] = input.linewidth
        if input.visible is not None:
            kwargs["visible"] = input.visible
        if input.locked is not None:
            kwargs["locked"] = input.locked
        doc.layers.update(input.name, **kwargs)
        return LayerUpdateOutput(name=input.name, status="success", message="Updated")
    except CADError as exc:
        return LayerUpdateOutput(name="", status="error", message=str(exc))


def cad_layer_delete(input: LayerDeleteInput) -> LayerDeleteOutput:
    """Delete a layer from the current document.

    删除图层。Objects on the layer are removed with it; this is destructive
    and cannot be undone.

    When not to use: to hide a layer without losing its objects use
    ``cad_layer_update`` (visible=false) instead of deleting it.
    """
    try:
        doc = DocumentManager().get_current()
        doc.layers.delete(input.name)
        return LayerDeleteOutput(name=input.name, status="success", message="Deleted")
    except CADError as exc:
        return LayerDeleteOutput(name="", status="error", message=str(exc))


# ---------------------------------------------------------------------------
# Additional read-only tools referenced by the permission whitelist
# ---------------------------------------------------------------------------


class FileListInput(BaseModel):
    """Input for listing open files."""


class FileListOutput(BaseModel):
    """Output for listing open files."""

    files: list[dict[str, Any]] = Field(..., description="Open files")
    status: str = Field(..., description="Operation status")


class ObjectListInput(BaseModel):
    """Input for listing objects."""

    layer: str | None = Field(None, description="Filter by layer")


class ObjectListOutput(BaseModel):
    """Output for listing objects."""

    objects: list[dict[str, Any]] = Field(..., description="Object summaries")
    status: str = Field(..., description="Operation status")


class LayerListInput(BaseModel):
    """Input for listing layers."""


class LayerListOutput(BaseModel):
    """Output for listing layers."""

    layers: list[dict[str, Any]] = Field(..., description="Layer definitions")
    status: str = Field(..., description="Operation status")


def cad_file_list(input: FileListInput) -> FileListOutput:
    """List the currently open files.

    列出会话中打开的所有文档（file id、文件名、单位、实体数）。

    When not to use: to query one file's detail use ``cad_status``
    (target=file); this tool returns the open-file overview only.
    """
    files = DocumentManager().list()
    return FileListOutput(files=files, status="success")


def cad_object_list(input: ObjectListInput) -> ObjectListOutput:
    """List objects in the current document, optionally filtered by layer."""
    try:
        doc = DocumentManager().get_current()
        records = doc.entities.list(layer=input.layer)
        summaries = [
            {
                "object_id": record.id,
                "type": record.type,
                "layer": record.layer,
                "bbox": doc.entities.get_bbox(record.id),
            }
            for record in records
        ]
        return ObjectListOutput(objects=summaries, status="success")
    except CADError:
        return ObjectListOutput(objects=[], status="error")


def cad_layer_list(input: LayerListInput) -> LayerListOutput:
    """List the layers of the current document.

    列出当前文档的全部图层及其属性（颜色、线型、可见/锁定状态）。

    When not to use: for a single layer's detail use ``cad_layer_read``;
    for per-layer object counts use ``cad_status`` (target=layer).
    """
    try:
        doc = DocumentManager().get_current()
        layers = [layer.to_dict() for layer in doc.layers.list()]
        return LayerListOutput(layers=layers, status="success")
    except CADError:
        return LayerListOutput(layers=[], status="error")


# ---------------------------------------------------------------------------
# Aggregate cad_file / cad_object / cad_layer tools
# ---------------------------------------------------------------------------


class FileCreateParams(FileCreateInput):
    """Create a new CAD file."""

    action: Literal["create"] = "create"


class FileOpenParams(FileOpenInput):
    """Open an existing JSON scene file."""

    action: Literal["open"] = "open"


class FileSaveParams(FileSaveInput):
    """Save a document to disk."""

    action: Literal["save"] = "save"


class FileCloseParams(FileCloseInput):
    """Close a document."""

    action: Literal["close"] = "close"


class FileDeleteParams(FileDeleteInput):
    """Delete a document from the session."""

    action: Literal["delete"] = "delete"


class FileListParams(FileListInput):
    """List the open files."""

    action: Literal["list"] = "list"


class FileImportParams(BaseModel):
    """Import a file as a new document."""

    action: Literal["import"] = "import"
    path: str = Field(..., description="File path to import (.json / .dxf / .step)")


class FileExportParams(BaseModel):
    """Export the current document to a file."""

    action: Literal["export"] = "export"
    format: str = Field(
        ...,
        description="Export format: step (recommended), dxf, stl, dwg, json",
        examples=["step"],
    )
    path: str = Field(..., description="Target file path")


FileActionParams = Annotated[
    FileCreateParams
    | FileOpenParams
    | FileSaveParams
    | FileCloseParams
    | FileDeleteParams
    | FileListParams
    | FileImportParams
    | FileExportParams,
    Field(discriminator="action"),
]


class FileInput(BaseModel):
    """Input for the aggregate file tool.

    聚合文件工具。``action`` 决定操作：create / open / save / close / delete /
    list / import / export。
    """

    file: FileActionParams = Field(
        ...,
        description=(
            "File action to perform, discriminated by `action`: create, open, "
            "save, close, delete, list, import or export."
        ),
    )


class FileOutput(BaseModel):
    """Output of the aggregate file tool."""

    action: str = Field(..., description="File action executed")
    file_id: str = Field("", description="File unique identifier")
    filename: str = Field("", description="File name")
    path: str = Field("", description="Saved / exported path")
    files: list[dict[str, Any]] = Field(default_factory=list, description="Open files")
    object_count: int = Field(0, description="Number of imported objects")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ObjectCreateParams(ObjectCreateInput):
    """Create a geometry object."""

    action: Literal["create"] = "create"


class ObjectReadParams(ObjectReadInput):
    """Read an object's details."""

    action: Literal["read"] = "read"


class ObjectUpdateParams(ObjectUpdateInput):
    """Update an object."""

    action: Literal["update"] = "update"


class ObjectDeleteParams(ObjectDeleteInput):
    """Delete an object."""

    action: Literal["delete"] = "delete"


class ObjectCopyParams(ObjectCopyInput):
    """Copy an object."""

    action: Literal["copy"] = "copy"


class ObjectTransformParams(ObjectTransformInput):
    """Apply a 4x4 matrix to an object."""

    action: Literal["transform"] = "transform"


class ObjectListParams(ObjectListInput):
    """List objects, optionally filtered by layer."""

    action: Literal["list"] = "list"


class ObjectBooleanParams(BaseModel):
    """Combine several objects with a boolean operation."""

    action: Literal["boolean"] = "boolean"
    operation: Literal["union", "subtract", "intersect"] = Field(
        ..., description="Boolean operation", examples=["subtract"]
    )
    target_id: str = Field(..., description="Target object id")
    tool_ids: list[str] = Field(..., description="Tool object ids to combine")
    new_id: str | None = Field(None, description="Optional id for the result object")
    layer: str = Field("0", description="Layer for the result object")


ObjectActionParams = Annotated[
    ObjectCreateParams
    | ObjectReadParams
    | ObjectUpdateParams
    | ObjectDeleteParams
    | ObjectCopyParams
    | ObjectTransformParams
    | ObjectListParams
    | ObjectBooleanParams,
    Field(discriminator="action"),
]


class ObjectInput(BaseModel):
    """Input for the aggregate object tool.

    聚合对象工具。``action`` 决定操作：create / read / update / delete / copy /
    transform / list / boolean。
    """

    object: ObjectActionParams = Field(
        ...,
        description=(
            "Object action to perform, discriminated by `action`: create, read, "
            "update, delete, copy, transform, list or boolean."
        ),
    )


class ObjectOutput(BaseModel):
    """Output of the aggregate object tool."""

    action: str = Field(..., description="Object action executed")
    object_id: str = Field("", description="Object unique identifier")
    result_id: str = Field("", description="Result object id (boolean / copy)")
    type: str = Field("", description="Object type")
    layer: str = Field("", description="Layer name")
    geometry: dict[str, Any] = Field(default_factory=dict, description="Geometry parameters")
    properties: dict[str, Any] = Field(default_factory=dict, description="Object properties")
    bbox: dict[str, list[float]] = Field(
        default_factory=lambda: {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
        description="Bounding box",
    )
    objects: list[dict[str, Any]] = Field(default_factory=list, description="Object summaries")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class LayerCreateParams(LayerCreateInput):
    """Create a layer."""

    action: Literal["create"] = "create"


class LayerReadParams(LayerReadInput):
    """Read a layer's definition."""

    action: Literal["read"] = "read"


class LayerUpdateParams(LayerUpdateInput):
    """Update a layer's attributes."""

    action: Literal["update"] = "update"


class LayerDeleteParams(LayerDeleteInput):
    """Delete a layer."""

    action: Literal["delete"] = "delete"


class LayerListParams(LayerListInput):
    """List the layers of the current document."""

    action: Literal["list"] = "list"


LayerActionParams = Annotated[
    LayerCreateParams
    | LayerReadParams
    | LayerUpdateParams
    | LayerDeleteParams
    | LayerListParams,
    Field(discriminator="action"),
]


class LayerInput(BaseModel):
    """Input for the aggregate layer tool.

    聚合图层工具。``action`` 决定操作：create / read / update / delete / list。
    """

    layer: LayerActionParams = Field(
        ...,
        description=(
            "Layer action to perform, discriminated by `action`: create, read, "
            "update, delete or list."
        ),
    )


class LayerOutput(BaseModel):
    """Output of the aggregate layer tool."""

    action: str = Field(..., description="Layer action executed")
    name: str = Field("", description="Layer name")
    color: str = Field("", description="Layer color")
    linetype: str = Field("", description="Line type")
    linewidth: float = Field(0.0, description="Line width")
    visible: bool = Field(False, description="Visibility")
    locked: bool = Field(False, description="Lock state")
    layers: list[dict[str, Any]] = Field(default_factory=list, description="Layer definitions")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _file_result(action: str, result: BaseModel) -> FileOutput:
    data = result.model_dump()
    data["action"] = action
    return FileOutput(**data)


def cad_file(input: FileInput) -> FileOutput:
    """Create, open, save, close, delete, list, import or export files.

    聚合文件操作。按 ``action`` 派发：create / open / save / close / delete /
    list / import / export。
    - ``create`` / ``open`` / ``save`` / ``close`` / ``delete`` / ``list``:
      manage in-memory documents. ``open`` and ``save`` read/write the JSON
      scene format; ``create`` starts a new document (optional ``template`` /
      ``unit``).
    - ``export``: write the current document to an interop format — step
      (recommended), dxf, stl, dwg or json — at ``path``.
    - ``import``: load an interop file (.json / .dxf / .step / .dwg) as a new
      document.

    When not to use: ``cad_file`` handles whole files/documents. For
    per-object geometry edits use ``cad_object``; to import/export raw JSON
    scene data (not files) use ``cad_json`` (import_scene/export_scene).
    """
    params = input.file
    if params.action == "create":
        return _file_result("create", cad_file_create(params))
    if params.action == "open":
        return _file_result("open", cad_file_open(params))
    if params.action == "save":
        return _file_result("save", cad_file_save(params))
    if params.action == "close":
        return _file_result("close", cad_file_close(params))
    if params.action == "delete":
        return _file_result("delete", cad_file_delete(params))
    if params.action == "list":
        return _file_result("list", cad_file_list(FileListInput()))
    if params.action == "import":
        from tianshangcad.mcp.tools.file_io import FileImportInput, cad_file_import

        return _file_result("import", cad_file_import(FileImportInput(path=params.path)))
    if params.action == "export":
        from tianshangcad.mcp.tools.file_io import FileExportInput, cad_file_export

        return _file_result(
            "export",
            cad_file_export(FileExportInput(format=params.format, path=params.path)),
        )
    return FileOutput(action=params.action, status="error", message="Unknown action")


def _object_result(action: str, result: BaseModel) -> ObjectOutput:
    data = result.model_dump()
    data["action"] = action
    return ObjectOutput(**data)


def cad_object(input: ObjectInput) -> ObjectOutput:
    """Create, read, update, delete, copy, transform, list or boolean objects.

    聚合对象操作。按 ``action`` 派发：create / read / update / delete / copy /
    transform / list / boolean。
    - ``create``: add an entity by ``type`` (line, circle, arc, rectangle,
      polygon, polyline, box, cylinder, sphere, cone) with ``params``;
      returns the new ``object_id`` and bounding box.
    - ``read`` / ``update`` / ``delete`` / ``copy``: inspect, edit (geometry /
      layer / properties), remove, or duplicate an object by ``object_id``.
    - ``transform``: apply a 4x4 matrix (column-major, translation in the
      fourth column) for translate / rotate / scale.
    - ``list``: enumerate objects, optionally filtered by ``layer``.
    - ``boolean``: combine objects (union / subtract / intersect) into a new
      mesh; requires the optional ``boolean`` extra.

    When not to use: ``cad_object`` edits the current document's geometry.
    For interop file formats use ``cad_file`` (import/export); for JSON
    scene round-trips use ``cad_json``; for measurements on existing objects
    use ``cad_measure``; for geometric validation use ``cad_validate``.
    """
    params = input.object
    if params.action == "create":
        return _object_result("create", cad_object_create(params))
    if params.action == "read":
        return _object_result("read", cad_object_read(params))
    if params.action == "update":
        return _object_result("update", cad_object_update(params))
    if params.action == "delete":
        return _object_result("delete", cad_object_delete(params))
    if params.action == "copy":
        return _object_result("copy", cad_object_copy(params))
    if params.action == "transform":
        return _object_result("transform", cad_object_transform(params))
    if params.action == "list":
        return _object_result("list", cad_object_list(ObjectListInput(layer=params.layer)))
    if params.action == "boolean":
        from tianshangcad.mcp.tools.boolean import ObjectBooleanInput, cad_object_boolean

        return _object_result(
            "boolean",
            cad_object_boolean(
                ObjectBooleanInput(
                    operation=params.operation,
                    target_id=params.target_id,
                    tool_ids=params.tool_ids,
                    new_id=params.new_id,
                    layer=params.layer,
                )
            ),
        )
    return ObjectOutput(action=params.action, status="error", message="Unknown action")


def _layer_result(action: str, result: BaseModel) -> LayerOutput:
    data = result.model_dump()
    data["action"] = action
    return LayerOutput(**data)


def cad_layer(input: LayerInput) -> LayerOutput:
    """Create, read, update, delete or list layers.

    聚合图层操作。按 ``action`` 派发：create / read / update / delete / list。
    Layers group objects for display and selection. ``create`` accepts
    color / linetype / linewidth; ``update`` can also toggle ``visible`` /
    ``locked``; ``delete`` removes the layer *and* the objects on it.

    When not to use: for per-object layer membership use ``cad_object``
    (create/update with a ``layer``); for per-layer object counts use
    ``cad_status`` (target=layer). To hide objects without deleting them
    prefer ``cad_layer`` (update visible=false).
    """
    params = input.layer
    if params.action == "create":
        return _layer_result("create", cad_layer_create(params))
    if params.action == "read":
        return _layer_result("read", cad_layer_read(params))
    if params.action == "update":
        return _layer_result("update", cad_layer_update(params))
    if params.action == "delete":
        return _layer_result("delete", cad_layer_delete(params))
    if params.action == "list":
        return _layer_result("list", cad_layer_list(LayerListInput()))
    return LayerOutput(action=params.action, status="error", message="Unknown action")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_file", cad_file),
    ("cad_object", cad_object),
    ("cad_layer", cad_layer),
]
