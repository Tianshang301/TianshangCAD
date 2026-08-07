"""JSON read/parse/validate/import/export tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.io.exporters.json_io import JSONExporter
from tianshangcad.io.importers.json_io import JSONImporter
from tianshangcad.schemas.scene import SceneDefinition
from tianshangcad.utils.errors import CADError


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
    # Deprecated, merged into cad_json (action=load)
    try:
        content = Path(input.path).read_text(encoding="utf-8")
        return JsonLoadOutput(content=content, status="success")
    except (OSError, CADError) as exc:
        return JsonLoadOutput(content="", status="error", message=str(exc))


def cad_json_parse(input: JsonParseInput) -> JsonParseOutput:
    """Parse a JSON string and report its structure."""
    # Deprecated, merged into cad_json (action=parse)
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
    # Deprecated, merged into cad_json (action=validate)
    try:
        data = json.loads(input.json_string)
    except json.JSONDecodeError as exc:
        return JsonValidateOutput(is_valid=False, errors=[f"Invalid JSON: {exc.msg}"])
    try:
        if input.schema_name == "geometry":
            from tianshangcad.schemas.geometry import GeometryObject

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
    # Deprecated, merged into cad_json (action=import_geometry)
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
    # Deprecated, merged into cad_json (action=export_geometry)
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
    # Deprecated, merged into cad_json (action=import_scene)
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
    # Deprecated, merged into cad_json (action=export_scene)
    try:
        doc = DocumentManager().get_current()
        json_string = JSONExporter().export_document(doc, pretty=input.pretty)
        return JsonExportSceneOutput(json_string=json_string, status="success")
    except CADError as exc:
        return JsonExportSceneOutput(json_string="", status="error", message=str(exc))


def cad_json_save(input: JsonSaveInput) -> JsonSaveOutput:
    """Write a JSON string to a file."""
    # Deprecated, merged into cad_json (action=save)
    try:
        path = Path(input.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(input.json_string, encoding="utf-8")
        return JsonSaveOutput(path=str(path), status="success", message="Saved")
    except OSError as exc:
        return JsonSaveOutput(path="", status="error", message=str(exc))


# ---------------------------------------------------------------------------
# Aggregate cad_json tool (action-discriminated union)
# ---------------------------------------------------------------------------


class JsonLoadParams(BaseModel):
    """Read the raw content of a JSON file."""

    action: Literal["load"] = "load"
    path: str = Field(..., description="File path to read")


class JsonParseParams(BaseModel):
    """Parse a JSON string and report its structure."""

    action: Literal["parse"] = "parse"
    json_string: str = Field(..., description="JSON string to parse")


class JsonValidateParams(BaseModel):
    """Validate JSON against the scene or geometry schema."""

    action: Literal["validate"] = "validate"
    json_string: str = Field(..., description="JSON string to validate")
    schema_name: str = Field("scene", description="Schema: scene / geometry")


class JsonImportGeometryParams(BaseModel):
    """Import geometry objects from JSON into the current document."""

    action: Literal["import_geometry"] = "import_geometry"
    json_data: str = Field(..., description="JSON string containing geometry objects")
    coordinate_system: str = Field("world", description="Coordinate system")


class JsonExportGeometryParams(BaseModel):
    """Export selected objects from the current document as JSON."""

    action: Literal["export_geometry"] = "export_geometry"
    object_ids: list[str] | None = Field(None, description="Object ids (all when omitted)")
    include_properties: bool = Field(True, description="Include object properties")


class JsonImportSceneParams(BaseModel):
    """Import a full scene definition as a new document."""

    action: Literal["import_scene"] = "import_scene"
    json_data: str = Field(..., description="JSON scene string")


class JsonExportSceneParams(BaseModel):
    """Export the current document as a JSON scene string."""

    action: Literal["export_scene"] = "export_scene"
    pretty: bool = Field(True, description="Pretty-print the JSON")


class JsonSaveParams(BaseModel):
    """Write a JSON string to a file."""

    action: Literal["save"] = "save"
    json_string: str = Field(..., description="JSON content to write")
    path: str = Field(..., description="Target file path")


JsonActionParams = Annotated[
    JsonLoadParams
    | JsonParseParams
    | JsonValidateParams
    | JsonImportGeometryParams
    | JsonExportGeometryParams
    | JsonImportSceneParams
    | JsonExportSceneParams
    | JsonSaveParams,
    Field(discriminator="action"),
]


class JsonInput(BaseModel):
    """Input for the aggregate JSON tool.

    聚合 JSON 工具。``action`` 决定操作类型，各 action 使用各自的参数字段：
    - ``load``: ``path``
    - ``parse``: ``json_string``
    - ``validate``: ``json_string`` / ``schema_name``
    - ``import_geometry``: ``json_data`` / ``coordinate_system``
    - ``export_geometry``: ``object_ids`` / ``include_properties``
    - ``import_scene``: ``json_data``
    - ``export_scene``: ``pretty``
    - ``save``: ``json_string`` / ``path``
    """

    params: JsonActionParams = Field(
        ...,
        description=(
            "JSON action, discriminated by `action`: load, parse, validate, "
            "import_geometry, export_geometry, import_scene, export_scene "
            "or save."
        ),
    )


class JsonOutput(BaseModel):
    """Output of the aggregate JSON tool."""

    action: str = Field(..., description="Action executed")
    content: str = Field("", description="Raw / serialized JSON content")
    is_valid: bool = Field(False, description="Validity (parse/validate actions)")
    object_count: int = Field(0, description="Number of objects handled")
    imported_objects: list[dict[str, Any]] = Field(
        default_factory=list, description="Imported object summaries"
    )
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def cad_json(input: JsonInput) -> JsonOutput:
    """Read / parse / validate / import / export JSON.

    按 ``action`` 执行 JSON 读写、解析、校验、导入与导出：
    - load：读取文件原文
    - parse：解析并报告结构
    - validate：按 scene/geometry 模式校验
    - import_geometry：将 JSON 几何导入当前文档
    - export_geometry：将对象导出为 JSON
    - import_scene：以 JSON 场景创建新文档
    - export_scene：导出当前文档为 JSON 场景
    - save：将 JSON 字符串写入文件
    """
    params = input.params
    try:
        if params.action == "load":
            content = Path(params.path).read_text(encoding="utf-8")
            return JsonOutput(
                action="load", content=content, is_valid=True, status="success"
            )

        if params.action == "parse":
            try:
                data = json.loads(params.json_string)
            except json.JSONDecodeError as exc:
                return JsonOutput(
                    action="parse", status="error", message=f"Invalid JSON: {exc.msg}"
                )
            if isinstance(data, dict):
                root, count = "object", 1
            elif isinstance(data, list):
                root, count = "array", len(data)
            else:
                root, count = "scalar", 1
            return JsonOutput(
                action="parse",
                content=root,
                is_valid=True,
                object_count=count,
                status="success",
            )

        if params.action == "validate":
            try:
                data = json.loads(params.json_string)
            except json.JSONDecodeError as exc:
                return JsonOutput(
                    action="validate", errors=[f"Invalid JSON: {exc.msg}"], status="error"
                )
            try:
                if params.schema_name == "geometry":
                    from tianshangcad.schemas.geometry import GeometryObject

                    if isinstance(data, list):
                        for item in data:
                            GeometryObject.model_validate(item)
                    else:
                        GeometryObject.model_validate(data)
                else:
                    SceneDefinition.model_validate(data)
                return JsonOutput(action="validate", is_valid=True, status="success")
            except Exception as exc:
                return JsonOutput(
                    action="validate", errors=[str(exc)], status="error"
                )

        if params.action == "import_geometry":
            doc = DocumentManager().get_current()
            objects = JSONImporter().import_geometry(params.json_data)
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
            return JsonOutput(
                action="import_geometry",
                imported_objects=summaries,
                object_count=len(summaries),
                is_valid=True,
                status="success",
                message=f"Imported {len(summaries)} objects",
            )

        if params.action == "export_geometry":
            doc = DocumentManager().get_current()
            if params.object_ids is None:
                records = doc.entities.list()
            else:
                records = [doc.entities.read(object_id) for object_id in params.object_ids]
            json_string = JSONExporter().export_geometry(records)
            return JsonOutput(
                action="export_geometry",
                content=json_string,
                object_count=len(records),
                is_valid=True,
                status="success",
            )

        if params.action == "import_scene":
            importer = JSONImporter()
            scene = importer.parse(params.json_data)
            doc = importer.scene_to_document(scene)
            session = DocumentManager()._session
            session.active_files[doc.file_id] = doc
            session.current_file_id = doc.file_id
            return JsonOutput(
                action="import_scene",
                object_count=doc.entities.count(),
                is_valid=True,
                status="success",
                message=f"Imported scene {doc.filename}",
            )

        if params.action == "export_scene":
            doc = DocumentManager().get_current()
            json_string = JSONExporter().export_document(doc, pretty=params.pretty)
            return JsonOutput(
                action="export_scene",
                content=json_string,
                is_valid=True,
                status="success",
            )

        if params.action == "save":
            path = Path(params.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(params.json_string, encoding="utf-8")
            return JsonOutput(
                action="save",
                content=str(path),
                is_valid=True,
                status="success",
                message="Saved",
            )

        return JsonOutput(action=params.action, status="error", message="Unknown action")
    except (CADError, ValueError, OSError) as exc:
        return JsonOutput(action=input.params.action, status="error", message=str(exc))


TOOLS: list[tuple[str, Any]] = [
    ("cad_json", cad_json),
]
