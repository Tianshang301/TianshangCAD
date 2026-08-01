"""Document version snapshots and diffing.

A snapshot is a full JSON-safe copy of a document (``DocumentState``). The
:class:`VersionManager` keeps in-memory snapshots and supports saving,
listing, diffing (via ``deepdiff``) and restoring them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from deepdiff import DeepDiff

from cad_mcp_server.core.document import DocumentManager, DocumentState
from cad_mcp_server.core.session import SessionManager
from cad_mcp_server.utils.errors import CADError, VersionError

_VERSION_FORMAT = "tianshang-cad-version"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_version_id() -> str:
    """Generate a new version identifier."""
    return f"v_{uuid.uuid4().hex[:10]}"


class VersionManager:
    """In-memory version snapshot manager (singleton)."""

    _instance: ClassVar[VersionManager | None] = None
    _snapshots: ClassVar[dict[str, dict[str, Any]]] = {}

    def __new__(cls) -> VersionManager:
        """Return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def clear(self) -> None:
        """Remove all stored snapshots (used by tests)."""
        type(self)._snapshots.clear()

    @property
    def snapshots(self) -> dict[str, dict[str, Any]]:
        """Return the raw snapshot mapping."""
        return type(self)._snapshots

    def save(
        self,
        label: str | None = None,
        file_id: str | None = None,
        author: str | None = None,
    ) -> str:
        """Snapshot the current document and return its version id."""
        try:
            doc = DocumentManager()._require(file_id)
        except CADError as exc:
            raise VersionError(str(exc), code="no_active_document") from exc
        version_id = new_version_id()
        snapshot = {
            "format": _VERSION_FORMAT,
            "version_id": version_id,
            "label": label,
            "author": author,
            "created_at": _now_iso(),
            "file_id": doc.file_id,
            "payload": doc.to_dict(),
        }
        type(self)._snapshots[version_id] = snapshot
        return version_id

    def list(self, file_id: str | None = None) -> list[dict[str, Any]]:
        """Return snapshot metadata, most recent first."""
        snapshots = [
            {
                "version_id": item["version_id"],
                "label": item["label"],
                "author": item["author"],
                "created_at": item["created_at"],
                "file_id": item["file_id"],
                "entity_count": len(item["payload"].get("entities", [])),
            }
            for item in type(self)._snapshots.values()
        ]
        if file_id is not None:
            snapshots = [item for item in snapshots if item["file_id"] == file_id]
        snapshots.sort(key=lambda item: item["created_at"], reverse=True)
        return snapshots

    def get(self, version_id: str) -> dict[str, Any]:
        """Return a snapshot or raise ``VersionError``."""
        snapshot = type(self)._snapshots.get(version_id)
        if snapshot is None:
            raise VersionError(f"Version not found: {version_id}", code="version_not_found")
        return snapshot

    def diff(self, version_a: str, version_b: str) -> dict[str, Any]:
        """Compare two snapshots with ``deepdiff``.

        Returns a structured summary with the raw deepdiff result.
        """
        snapshot_a = self.get(version_a)
        snapshot_b = self.get(version_b)
        payload_a = snapshot_a["payload"]
        payload_b = snapshot_b["payload"]
        raw = DeepDiff(
            payload_a,
            payload_b,
            ignore_order=True,
            ignore_nan_inequality=True,
            significant_digits=6,
        )
        result = raw.to_dict() if hasattr(raw, "to_dict") else dict(raw)
        changed_fields = sorted(str(key) for key in result.get("values_changed", {}))
        added = len(result.get("dictionary_item_added", [])) + len(
            result.get("iterable_item_added", [])
        )
        removed = len(result.get("dictionary_item_removed", [])) + len(
            result.get("iterable_item_removed", [])
        )
        return {
            "version_a": version_a,
            "version_b": version_b,
            "identical": not result,
            "changed_fields": changed_fields,
            "added_count": added,
            "removed_count": removed,
            "changes": len(result),
            "raw": result,
        }

    def restore(self, version_id: str, file_id: str | None = None) -> str:
        """Restore a document to the state captured in ``version_id``.

        Reconstructs a ``DocumentState`` from the snapshot payload and makes
        it the active file. Returns the restored file id.
        """
        snapshot = self.get(version_id)
        payload = dict(snapshot["payload"])
        target_file_id = file_id or snapshot["file_id"]
        payload["file_id"] = target_file_id
        restored = DocumentState.from_dict(payload)
        session = SessionManager().current_session
        session.active_files[target_file_id] = restored
        session.current_file_id = target_file_id
        return target_file_id
