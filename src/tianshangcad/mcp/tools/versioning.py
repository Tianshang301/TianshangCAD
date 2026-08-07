"""Document version snapshot tools.

The public surface is the single aggregate ``cad_version`` tool. The legacy
``cad_version_save`` / ``cad_version_list`` / ``cad_version_diff`` /
``cad_version_restore`` functions remain importable but are no longer
registered.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from tianshangcad.core.versioning import VersionManager
from tianshangcad.utils.errors import CADError


class VersionSaveInput(BaseModel):
    """Input for saving a document version snapshot."""

    label: str | None = Field(None, description="Human-readable label for the snapshot")
    file_id: str | None = Field(None, description="File id to snapshot (defaults to current)")
    author: str | None = Field(None, description="Snapshot author (optional)")


class VersionSaveOutput(BaseModel):
    """Output for version snapshot save."""

    version_id: str = Field(..., description="Generated version id")
    label: str | None = Field(None, description="Snapshot label")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class VersionListInput(BaseModel):
    """Input for listing version snapshots."""

    file_id: str | None = Field(None, description="Filter by file id (optional)")


class VersionEntry(BaseModel):
    """Metadata for a single version snapshot."""

    version_id: str = Field(..., description="Version id")
    label: str | None = Field(None, description="Snapshot label")
    author: str | None = Field(None, description="Snapshot author")
    created_at: str = Field(..., description="ISO creation time")
    file_id: str = Field(..., description="File id the snapshot belongs to")
    entity_count: int = Field(..., description="Number of entities in the snapshot")


class VersionListOutput(BaseModel):
    """Output for version listing."""

    versions: list[VersionEntry] = Field(default_factory=list, description="Snapshots")
    count: int = Field(..., description="Number of snapshots")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class VersionDiffInput(BaseModel):
    """Input for diffing two version snapshots."""

    version_a: str = Field(..., description="First version id")
    version_b: str = Field(..., description="Second version id")


class VersionDiffOutput(BaseModel):
    """Output for version diffing."""

    identical: bool = Field(..., description="Whether the two snapshots are identical")
    changed_fields: list[str] = Field(default_factory=list, description="Changed field paths")
    added_count: int = Field(..., description="Added items")
    removed_count: int = Field(..., description="Removed items")
    changes: int = Field(..., description="Total number of differences")
    raw: dict[str, Any] = Field(default_factory=dict, description="Raw deepdiff result")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class VersionRestoreInput(BaseModel):
    """Input for restoring a document to a snapshot."""

    version_id: str = Field(..., description="Version id to restore")
    file_id: str | None = Field(None, description="Target file id (defaults to snapshot's)")


class VersionRestoreOutput(BaseModel):
    """Output for version restore."""

    version_id: str = Field(..., description="Restored version id")
    file_id: str = Field(..., description="Restored file id")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


_manager = VersionManager()


def cad_version_save(input: VersionSaveInput) -> VersionSaveOutput:
    """Save a version snapshot of a document."""
    # Deprecated, merged into cad_version (action=save)
    try:
        version_id = _manager.save(
            label=input.label, file_id=input.file_id, author=input.author
        )
        return VersionSaveOutput(
            version_id=version_id,
            label=input.label,
            status="success",
            message=f"Version {version_id} saved",
        )
    except CADError as exc:
        return VersionSaveOutput(version_id="", status="error", message=str(exc))


def cad_version_list(input: VersionListInput) -> VersionListOutput:
    """List saved version snapshots, most recent first."""
    # Deprecated, merged into cad_version (action=list)
    try:
        versions = _manager.list(file_id=input.file_id)
        entries = [VersionEntry(**entry) for entry in versions]
        return VersionListOutput(
            versions=entries, count=len(entries), status="success"
        )
    except CADError as exc:
        return VersionListOutput(versions=[], count=0, status="error", message=str(exc))


def cad_version_diff(input: VersionDiffInput) -> VersionDiffOutput:
    """Compare two snapshots with deepdiff."""
    # Deprecated, merged into cad_version (action=diff)
    try:
        result = _manager.diff(input.version_a, input.version_b)
        return VersionDiffOutput(
            identical=result["identical"],
            changed_fields=result["changed_fields"],
            added_count=result["added_count"],
            removed_count=result["removed_count"],
            changes=result["changes"],
            raw=result["raw"],
            status="success",
        )
    except CADError as exc:
        return VersionDiffOutput(
            identical=False,
            added_count=0,
            removed_count=0,
            changes=0,
            status="error",
            message=str(exc),
        )


def cad_version_restore(input: VersionRestoreInput) -> VersionRestoreOutput:
    """Restore a document to a previously saved snapshot."""
    # Deprecated, merged into cad_version (action=restore)
    try:
        file_id = _manager.restore(input.version_id, file_id=input.file_id)
        return VersionRestoreOutput(
            version_id=input.version_id,
            file_id=file_id,
            status="success",
            message=f"Restored version {input.version_id}",
        )
    except CADError as exc:
        return VersionRestoreOutput(
            version_id=input.version_id,
            file_id=input.file_id or "",
            status="error",
            message=str(exc),
        )


# ---------------------------------------------------------------------------
# Aggregate cad_version tool
# ---------------------------------------------------------------------------


class VersionSaveParams(BaseModel):
    """Save a version snapshot."""

    action: Literal["save"] = "save"
    label: str | None = Field(None, description="Human-readable label for the snapshot")
    file_id: str | None = Field(None, description="File id to snapshot (defaults to current)")
    author: str | None = Field(None, description="Snapshot author (optional)")


class VersionListParams(BaseModel):
    """List version snapshots."""

    action: Literal["list"] = "list"
    file_id: str | None = Field(None, description="Filter by file id (optional)")


class VersionDiffParams(BaseModel):
    """Diff two version snapshots."""

    action: Literal["diff"] = "diff"
    version_a: str = Field(..., description="First version id")
    version_b: str = Field(..., description="Second version id")


class VersionRestoreParams(BaseModel):
    """Restore a document to a snapshot."""

    action: Literal["restore"] = "restore"
    version_id: str = Field(..., description="Version id to restore")
    file_id: str | None = Field(None, description="Target file id (defaults to snapshot's)")


VersionActionParams = Annotated[
    VersionSaveParams
    | VersionListParams
    | VersionDiffParams
    | VersionRestoreParams,
    Field(discriminator="action"),
]


class VersionInput(BaseModel):
    """Input for the aggregate version tool.

    聚合版本工具。``action`` 为 ``save``（保存快照）、``list``（列出快照）、
    ``diff``（对比两个快照）或 ``restore``（恢复快照）。
    """

    version: VersionActionParams = Field(
        default_factory=VersionListParams,
        description=(
            "Version action, discriminated by `action`: save, list, diff "
            "or restore a document snapshot."
        ),
    )


class VersionOutput(BaseModel):
    """Output of the aggregate version tool."""

    action: str = Field(..., description="Version action")
    version_id: str = Field("", description="Version id")
    label: str | None = Field(None, description="Snapshot label")
    file_id: str | None = Field(None, description="File id")
    versions: list[VersionEntry] = Field(default_factory=list, description="Snapshots")
    count: int = Field(0, description="Number of snapshots")
    identical: bool = Field(False, description="Whether two snapshots are identical")
    changed_fields: list[str] = Field(default_factory=list, description="Changed field paths")
    added_count: int = Field(0, description="Added items")
    removed_count: int = Field(0, description="Removed items")
    changes: int = Field(0, description="Total number of differences")
    raw: dict[str, Any] = Field(default_factory=dict, description="Raw deepdiff result")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def cad_version(input: VersionInput) -> VersionOutput:
    """Save, list, diff or restore document version snapshots.

    按 ``action`` 执行版本快照操作：save / list / diff / restore。
    """
    params = input.version
    try:
        if params.action == "save":
            version_id = _manager.save(
                label=params.label, file_id=params.file_id, author=params.author
            )
            return VersionOutput(
                action="save",
                version_id=version_id,
                label=params.label,
                status="success",
                message=f"Version {version_id} saved",
            )
        if params.action == "list":
            versions = _manager.list(file_id=params.file_id)
            entries = [VersionEntry(**entry) for entry in versions]
            return VersionOutput(
                action="list",
                versions=entries,
                count=len(entries),
                status="success",
            )
        if params.action == "diff":
            result = _manager.diff(params.version_a, params.version_b)
            return VersionOutput(
                action="diff",
                identical=result["identical"],
                changed_fields=result["changed_fields"],
                added_count=result["added_count"],
                removed_count=result["removed_count"],
                changes=result["changes"],
                raw=result["raw"],
                status="success",
            )
        file_id = _manager.restore(params.version_id, file_id=params.file_id)
        return VersionOutput(
            action="restore",
            version_id=params.version_id,
            file_id=file_id,
            status="success",
            message=f"Restored version {params.version_id}",
        )
    except CADError as exc:
        return VersionOutput(action=params.action, status="error", message=str(exc))


TOOLS: list[tuple[str, Any]] = [
    ("cad_version", cad_version),
]
