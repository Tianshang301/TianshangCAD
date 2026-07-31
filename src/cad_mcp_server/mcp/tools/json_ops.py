"""JSON read/parse/validate/import/export tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.io.exporters.json_io import JSONExporter
from cad_mcp_server.io.importers.json_io import JSONImporter
from cad_mcp_server.schemas.scene import SceneDefinition
from cad_mcp_server.utils.errors import CADError


class JsonLoadInput(BaseModel):
    """Input for reading a JSON file."""

    path: str = Field(..., description="File path to read")


class JsonLoadOutput(BaseModel):
    """Output for reading a JSON file."""

    content: str = Field(..., description="Raw JSON content")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class JsonParseInput(BaseModel):
    """Input for parsing a JSON string."""

    json_string: str = Field(..., description="JSON string to parse")


class JsonParseOutput(BaseModel):
    """Output for parsing a JSON string."""

    is_valid: bool = Field(..., description="Whether the JSON parses")
    root_type: str | None = Field(None, description="JSON root type: object / array / scalar")
    object_count: int = Field(0, description="Number of top-level elements")
    message: str | None = Field(None, description="Parse error message")


class JsonValidateInput(BaseModel):
    """Input for validating JSON against the scene schema."""

    json_string: str = Field(..., description="JSON scene string to validate")
    schema_name: str = Field("scene", description="Schema to validate against: scene / geometry")


class JsonValidateOutput(BaseModel):
    """Output for schema validation."""

    is_valid: bool = Field(..., description="Whether the JSON validates")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    message: str | None = Field(None, description="Status description")


class JsonImportGeometryInput(BaseModel):
    """Input for importing geometry objects."""

    json_data: str = Field(..., description="JSON string containing one or more geometry objects")
    coordinate_system: str = Field("world", description="Coordinate system (world)")


class JsonImportGeometryOutput(BaseModel):
    """Output for importing geometry objects."""

    imported_objects: list[dict[str, Any]] = Field(..., description="Imported object summaries")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class JsonExportGeometryInput(BaseModel):
    """Input for exporting geometry objects."""

    object_ids: list[str] | None = Field(
        None, description="Object ids to export (all when omitted)"
    )
    include_properties: bool = Field(True, description="Include object properties")


class JsonExportGeometryOutput(BaseModel):
    """Output for exporting geometry objects."""

    json_string: str = Field(..., description="Serialized geometry JSON")
    count: int = Field(..., description="Number of exported objects")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class JsonImportSceneInput(BaseModel):
    """Input for importing a scene."""

    json_data: str = Field(..., description="JSON scene string")


class JsonImportSceneOutput(BaseModel):
    """Output for importing a scene."""

    scene_id: str = Field(..., description="Imported scene id")
    name: str = Field(..., description="Scene name")
    object_count: int = Field(..., description="Number of objects in the scene")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class JsonExportSceneInput(BaseModel):
    """Input for exporting the current scene."""

    pretty: bool = Field(True, description="Pretty-print the JSON")


class JsonExportSceneOutput(BaseModel):
    """Output for exporting the current scene."""

    json_string: str = Field(..., description="Serialized scene JSON")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class JsonSaveInput(BaseModel):
    """Input for saving JSON content to a file."""

    json_string: str = Field(..., description="JSON content to write")
    path: str = Field(..., description="Target file path")


class JsonSaveOutput(BaseModel):
    """Output for saving JSON content."""

    path: str = Field(..., description="Saved file path")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def cad_json_load(input: JsonLoadInput) -> JsonLoadOutput:
    """Read the raw content of a JSON file."""
    try:
        content = Path(input.path).read_text(encoding="utf-8")
        return JsonLoadOutput(content=content, status="success")
    except (OSError, CADError) as exc:
        return JsonLoadOutput(content="", status="error", message=str(exc))


def cad_json_parse(input: JsonParseInput) -> JsonParseOutput:
    """Parse a JSON string and report its structure."""
    try:
        data = json.loads(input.json_string)
    except json.JSONDecodeError as exc:
        return JsonParseOutput(is_valid=False, message=f"Invalid JSON: {exc.msg}")
    if isinstance(data, dict):
        root_type = "object"
        count = 1
    elif isinstance(data, list):
        root_type = "array"
        count = len(data)
    else:
        root_type = "scalar"
        count = 1
    return JsonParseOutput(is_valid=True, root_type=root_type, object_count=count)


def cad_json_validate(input: JsonValidateInput) -> JsonValidateOutput:
    """Validate a JSON string against the scene or geometry schema."""
    try:
        data = json.loads(input.json_string)
    except json.JSONDecodeError as exc:
        return JsonValidateOutput(is_valid=False, errors=[f"Invalid JSON: {exc.msg}"])
    try:
        if input.schema_name == "geometry":
            from cad_mcp_server.schemas.geometry import GeometryObject

            if isinstance(data, list):
                for item in data:
                    GeometryObject.model_validate(item)
            else:
                GeometryObject.model_validate(data)
        else:
            SceneDefinition.model_validate(data)
        return JsonValidateOutput(is_valid=True)
    except Exception as exc:
        return JsonValidateOutput(is_valid=False, errors=[str(exc)])


def cad_json_import_geometry(input: JsonImportGeometryInput) -> JsonImportGeometryOutput:
    """Import geometry objects from JSON into the current document."""
    try:
        doc = DocumentManager().get_current()
        objects = JSONImporter().import_geometry(input.json_data)
        summaries: list[dict[str, Any]] = []
        for obj in objects:
            object_id = doc.entities.create(
                obj_type=obj.type,
                params=dict(obj.geometry.model_dump(exclude={"type"})),
                layer=obj.layer,
                properties=dict(obj.properties),
                object_id=obj.id,
                metadata=dict(obj.metadata),
            )
            summaries.append(
                {
                    "object_id": object_id,
                    "type": obj.type,
                    "layer": obj.layer,
                    "bbox": doc.entities.get_bbox(object_id),
                }
            )
        return JsonImportGeometryOutput(
            imported_objects=summaries,
            status="success",
            message=f"Imported {len(summaries)} objects",
        )
    except (CADError, ValueError) as exc:
        return JsonImportGeometryOutput(imported_objects=[], status="error", message=str(exc))


def cad_json_export_geometry(input: JsonExportGeometryInput) -> JsonExportGeometryOutput:
    """Export selected objects from the current document as JSON."""
    try:
        doc = DocumentManager().get_current()
        if input.object_ids is None:
            records = doc.entities.list()
        else:
            records = [doc.entities.read(object_id) for object_id in input.object_ids]
        json_string = JSONExporter().export_geometry(records)
        return JsonExportGeometryOutput(
            json_string=json_string, count=len(records), status="success"
        )
    except (CADError, ValueError) as exc:
        return JsonExportGeometryOutput(json_string="", count=0, status="error", message=str(exc))


def cad_json_import_scene(input: JsonImportSceneInput) -> JsonImportSceneOutput:
    """Import a full scene definition as a new document."""
    try:
        importer = JSONImporter()
        scene = importer.parse(input.json_data)
        doc = importer.scene_to_document(scene)
        session = DocumentManager()._session
        session.active_files[doc.file_id] = doc
        session.current_file_id = doc.file_id
        return JsonImportSceneOutput(
            scene_id=doc.file_id,
            name=doc.filename,
            object_count=doc.entities.count(),
            status="success",
        )
    except (CADError, ValueError) as exc:
        return JsonImportSceneOutput(
            scene_id="", name="", object_count=0, status="error", message=str(exc)
        )


def cad_json_export_scene(input: JsonExportSceneInput) -> JsonExportSceneOutput:
    """Export the current document as a JSON scene string."""
    try:
        doc = DocumentManager().get_current()
        json_string = JSONExporter().export_document(doc, pretty=input.pretty)
        return JsonExportSceneOutput(json_string=json_string, status="success")
    except CADError as exc:
        return JsonExportSceneOutput(json_string="", status="error", message=str(exc))


def cad_json_save(input: JsonSaveInput) -> JsonSaveOutput:
    """Write a JSON string to a file."""
    try:
        path = Path(input.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(input.json_string, encoding="utf-8")
        return JsonSaveOutput(path=str(path), status="success", message="Saved")
    except OSError as exc:
        return JsonSaveOutput(path="", status="error", message=str(exc))


TOOLS: list[tuple[str, Any]] = [
    ("cad_json_load", cad_json_load),
    ("cad_json_parse", cad_json_parse),
    ("cad_json_validate", cad_json_validate),
    ("cad_json_import_geometry", cad_json_import_geometry),
    ("cad_json_export_geometry", cad_json_export_geometry),
    ("cad_json_import_scene", cad_json_import_scene),
    ("cad_json_export_scene", cad_json_export_scene),
    ("cad_json_save", cad_json_save),
]
