"""CRUD tools: files, geometry objects and layers."""

from __future__ import annotations

from typing import Any

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
    """Open an existing JSON scene file."""
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
    """Save a document to disk (defaults to the current document)."""
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
    """Update an object's geometry, layer and/or properties."""
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
    """Create a layer in the current document."""
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
    """Read a layer's definition from the current document."""
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
    """Update a layer's attributes."""
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
    """Delete a layer from the current document."""
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
    """List the currently open files."""
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
    """List the layers of the current document."""
    try:
        doc = DocumentManager().get_current()
        layers = [layer.to_dict() for layer in doc.layers.list()]
        return LayerListOutput(layers=layers, status="success")
    except CADError:
        return LayerListOutput(layers=[], status="error")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_file_create", cad_file_create),
    ("cad_file_open", cad_file_open),
    ("cad_file_save", cad_file_save),
    ("cad_file_close", cad_file_close),
    ("cad_file_delete", cad_file_delete),
    ("cad_file_list", cad_file_list),
    ("cad_object_create", cad_object_create),
    ("cad_object_read", cad_object_read),
    ("cad_object_update", cad_object_update),
    ("cad_object_delete", cad_object_delete),
    ("cad_object_copy", cad_object_copy),
    ("cad_object_transform", cad_object_transform),
    ("cad_object_list", cad_object_list),
    ("cad_layer_create", cad_layer_create),
    ("cad_layer_read", cad_layer_read),
    ("cad_layer_update", cad_layer_update),
    ("cad_layer_delete", cad_layer_delete),
    ("cad_layer_list", cad_layer_list),
]
