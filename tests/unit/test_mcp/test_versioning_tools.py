"""Tests for the version snapshot tools and core VersionManager."""

from __future__ import annotations

import pytest

from tianshangcad.core.versioning import VersionManager
from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from tianshangcad.mcp.tools.versioning import (
    VersionDiffInput,
    VersionDiffParams,
    VersionInput,
    VersionListInput,
    VersionListParams,
    VersionRestoreInput,
    VersionRestoreParams,
    VersionSaveInput,
    VersionSaveParams,
    cad_version,
    cad_version_diff,
    cad_version_list,
    cad_version_restore,
    cad_version_save,
)
from tianshangcad.utils.errors import VersionError


@pytest.fixture(autouse=True)
def _clean_versions() -> None:
    VersionManager().clear()
    yield
    VersionManager().clear()


def _seed(origin: list[float] | None = None) -> None:
    cad_file_create(FileCreateInput(filename="draw.json"))
    cad_object_create(
        ObjectCreateInput(
            type="box",
            params={"origin": origin or [0, 0, 0], "dimensions": [10, 10, 10]},
            layer="0",
        )
    )


class TestVersionManager:
    """Core snapshot manager behaviour."""

    def test_save_and_get(self) -> None:
        _seed()
        version_id = VersionManager().save(label="v1")
        snapshot = VersionManager().get(version_id)
        assert snapshot["label"] == "v1"
        assert snapshot["payload"]["entities"]

    def test_save_without_document_errors(self) -> None:
        with pytest.raises(VersionError):
            VersionManager().save()

    def test_get_missing_errors(self) -> None:
        with pytest.raises(VersionError):
            VersionManager().get("v_missing")

    def test_restore_replaces_document(self) -> None:
        _seed()
        version_id = VersionManager().save(label="original")
        cad_object_create(
            ObjectCreateInput(
                type="circle",
                params={"center": [5, 5, 0], "radius": 2},
                layer="0",
            )
        )
        assert VersionManager().get(version_id)["payload"]["entities"] != []
        from tianshangcad.core.document import DocumentManager

        before = DocumentManager().get_current().entities.count()
        assert before == 2
        VersionManager().restore(version_id)
        after = DocumentManager().get_current().entities.count()
        assert after == 1

    def test_diff_identical(self) -> None:
        _seed()
        v1 = VersionManager().save()
        v2 = VersionManager().save()
        result = VersionManager().diff(v1, v2)
        assert result["identical"] is True
        assert result["changes"] == 0

    def test_diff_changed(self) -> None:
        _seed()
        v1 = VersionManager().save()
        cad_object_create(
            ObjectCreateInput(
                type="circle",
                params={"center": [1, 1, 0], "radius": 3},
                layer="0",
            )
        )
        v2 = VersionManager().save()
        result = VersionManager().diff(v1, v2)
        assert result["identical"] is False
        assert result["changes"] > 0
        assert result["added_count"] > 0


class TestVersionTools:
    """MCP version tools."""

    def test_save_success(self) -> None:
        _seed()
        result = cad_version_save(VersionSaveInput(label="checkpoint"))
        assert result.status == "success"
        assert result.version_id.startswith("v_")

    def test_save_no_document_error(self) -> None:
        result = cad_version_save(VersionSaveInput())
        assert result.status == "error"

    def test_list(self) -> None:
        _seed()
        cad_version_save(VersionSaveInput(label="a"))
        cad_version_save(VersionSaveInput(label="b"))
        result = cad_version_list(VersionListInput())
        assert result.status == "success"
        assert result.count == 2
        assert result.versions[0].created_at >= result.versions[1].created_at

    def test_list_filter_by_file(self) -> None:
        _seed()
        cad_version_save(VersionSaveInput(label="a"))
        listed = cad_version_list(VersionListInput())
        result = cad_version_list(VersionListInput(file_id=listed.versions[0].file_id))
        assert result.count == 1

    def test_diff_identical(self) -> None:
        _seed()
        v1 = cad_version_save(VersionSaveInput())
        v2 = cad_version_save(VersionSaveInput())
        result = cad_version_diff(
            VersionDiffInput(version_a=v1.version_id, version_b=v2.version_id)
        )
        assert result.status == "success"
        assert result.identical is True

    def test_diff_changed(self) -> None:
        _seed()
        v1 = cad_version_save(VersionSaveInput())
        cad_object_create(
            ObjectCreateInput(
                type="sphere",
                params={"center": [0, 0, 0], "radius": 4},
                layer="0",
            )
        )
        v2 = cad_version_save(VersionSaveInput())
        result = cad_version_diff(
            VersionDiffInput(version_a=v1.version_id, version_b=v2.version_id)
        )
        assert result.status == "success"
        assert result.identical is False
        assert result.added_count > 0
        assert result.changes > 0

    def test_diff_missing_version_error(self) -> None:
        result = cad_version_diff(VersionDiffInput(version_a="v_x", version_b="v_y"))
        assert result.status == "error"

    def test_restore_success(self) -> None:
        _seed()
        saved = cad_version_save(VersionSaveInput(label="base"))
        cad_object_create(
            ObjectCreateInput(
                type="line",
                params={"start": [0, 0, 0], "end": [5, 5, 0]},
                layer="0",
            )
        )
        result = cad_version_restore(VersionRestoreInput(version_id=saved.version_id))
        assert result.status == "success"
        assert result.file_id.startswith("file_")
        from tianshangcad.core.document import DocumentManager

        assert DocumentManager().get_current().entities.count() == 1

    def test_restore_missing_error(self) -> None:
        result = cad_version_restore(VersionRestoreInput(version_id="v_nope"))
        assert result.status == "error"


class TestVersionAggregate:
    """Aggregate cad_version tool (discriminated action)."""

    def test_action_save_success_and_no_doc(self) -> None:
        _seed()
        ok = cad_version(
            VersionInput(version=VersionSaveParams(label="checkpoint"))
        )
        assert ok.status == "success"
        assert ok.action == "save"
        assert ok.version_id.startswith("v_")
        from tianshangcad.mcp.tools.status import SessionManager

        SessionManager().reset()
        missing = cad_version(VersionInput(version=VersionSaveParams()))
        assert missing.status == "error"

    def test_action_list_and_filter(self) -> None:
        _seed()
        cad_version(VersionInput(version=VersionSaveParams(label="a")))
        cad_file_create(FileCreateInput(filename="other.json"))
        cad_version(VersionInput(version=VersionSaveParams(label="b")))
        listed = cad_version(VersionInput(version=VersionListParams()))
        assert listed.status == "success"
        assert listed.count == 2
        filtered = cad_version(
            VersionInput(version=VersionListParams(file_id=listed.versions[0].file_id))
        )
        assert filtered.count == 1

    def test_action_diff_identical_and_changed(self) -> None:
        _seed()
        v1 = cad_version(VersionInput(version=VersionSaveParams()))
        v2 = cad_version(VersionInput(version=VersionSaveParams()))
        identical = cad_version(
            VersionInput(
                version=VersionDiffParams(
                    version_a=v1.version_id, version_b=v2.version_id
                )
            )
        )
        assert identical.status == "success"
        assert identical.identical is True
        cad_object_create(
            ObjectCreateInput(
                type="sphere",
                params={"center": [0, 0, 0], "radius": 4},
                layer="0",
            )
        )
        v3 = cad_version(VersionInput(version=VersionSaveParams()))
        changed = cad_version(
            VersionInput(
                version=VersionDiffParams(
                    version_a=v1.version_id, version_b=v3.version_id
                )
            )
        )
        assert changed.identical is False
        assert changed.added_count > 0

    def test_action_diff_error(self) -> None:
        result = cad_version(
            VersionInput(version=VersionDiffParams(version_a="v_x", version_b="v_y"))
        )
        assert result.status == "error"

    def test_action_restore_success_and_missing(self) -> None:
        _seed()
        saved = cad_version(VersionInput(version=VersionSaveParams(label="base")))
        cad_object_create(
            ObjectCreateInput(
                type="line",
                params={"start": [0, 0, 0], "end": [5, 5, 0]},
                layer="0",
            )
        )
        restored = cad_version(
            VersionInput(version=VersionRestoreParams(version_id=saved.version_id))
        )
        assert restored.status == "success"
        assert restored.file_id.startswith("file_")
        from tianshangcad.core.document import DocumentManager

        assert DocumentManager().get_current().entities.count() == 1
        missing = cad_version(
            VersionInput(version=VersionRestoreParams(version_id="v_nope"))
        )
        assert missing.status == "error"
