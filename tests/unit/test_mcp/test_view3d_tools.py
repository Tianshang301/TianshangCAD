"""Tests for the 3D view MCP tools."""

from __future__ import annotations

from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from tianshangcad.mcp.tools.view3d import (
    ViewAnimationInput,
    ViewCreateInput,
    ViewDeleteInput,
    ViewExplodeInput,
    ViewListInput,
    ViewReadInput,
    ViewRenderInput,
    ViewSectionInput,
    ViewUpdateInput,
    WebGLSyncInput,
    cad_view_3d_create,
    cad_view_3d_delete,
    cad_view_3d_list,
    cad_view_3d_read,
    cad_view_3d_render,
    cad_view_3d_update,
    cad_view_animation,
    cad_view_explode,
    cad_view_section,
    cad_webgl_sync,
)


def _seed() -> None:
    cad_file_create(FileCreateInput(filename="view3d.json"))
    cad_object_create(
        ObjectCreateInput(
            type="box",
            params={"origin": [0, 0, 0], "dimensions": [10, 5, 2]},
            layer="0",
        )
    )
    cad_object_create(
        ObjectCreateInput(
            type="sphere",
            params={"center": [20, 0, 0], "radius": 3},
            layer="0",
        )
    )


class TestViewCRUD:
    """cad_view_3d_* CRUD tool behaviour."""

    def test_create_and_read_by_name(self) -> None:
        _seed()
        created = cad_view_3d_create(
            ViewCreateInput(name="iso", projection="perspective")
        )
        assert created.status == "success"
        read = cad_view_3d_read(ViewReadInput(view_id="iso"))
        assert read.status == "success"
        assert read.view is not None
        assert read.view["name"] == "iso"
        assert read.view["projection"] == "perspective"

    def test_duplicate_name_error(self) -> None:
        _seed()
        cad_view_3d_create(ViewCreateInput(name="top"))
        result = cad_view_3d_create(ViewCreateInput(name="top"))
        assert result.status == "error"
        assert "already exists" in result.message

    def test_list(self) -> None:
        _seed()
        cad_view_3d_create(ViewCreateInput(name="iso"))
        cad_view_3d_create(ViewCreateInput(name="front"))
        result = cad_view_3d_list(ViewListInput())
        assert result.status == "success"
        assert result.count == 2

    def test_update_projection(self) -> None:
        _seed()
        cad_view_3d_create(ViewCreateInput(name="iso"))
        result = cad_view_3d_update(
            ViewUpdateInput(view_id="iso", projection="orthographic")
        )
        assert result.status == "success"
        assert result.view["projection"] == "orthographic"

    def test_update_invalid_projection(self) -> None:
        _seed()
        cad_view_3d_create(ViewCreateInput(name="iso"))
        result = cad_view_3d_update(
            ViewUpdateInput(view_id="iso", projection="fish-eye")
        )
        assert result.status == "error"

    def test_delete(self) -> None:
        _seed()
        cad_view_3d_create(ViewCreateInput(name="side"))
        deleted = cad_view_3d_delete(ViewDeleteInput(view_id="side"))
        assert deleted.status == "success"
        read = cad_view_3d_read(ViewReadInput(view_id="side"))
        assert read.status == "error"

    def test_create_invalid_projection(self) -> None:
        _seed()
        result = cad_view_3d_create(ViewCreateInput(name="x", projection="bogus"))
        assert result.status == "error"

    def test_read_missing_view(self) -> None:
        _seed()
        result = cad_view_3d_read(ViewReadInput(view_id="nope"))
        assert result.status == "error"


class TestViewRendering:
    """cad_view_3d_render / section / explode / animation behaviour."""

    def test_render_view_success(self) -> None:
        _seed()
        cad_view_3d_create(ViewCreateInput(name="iso"))
        result = cad_view_3d_render(ViewRenderInput(view_id="iso", dpi=72))
        assert result.status == "success"
        assert result.size_bytes > 1000
        assert result.data_uri.startswith("data:image/png;base64,")

    def test_render_writes_output(self, tmp_path) -> None:
        _seed()
        cad_view_3d_create(ViewCreateInput(name="iso"))
        target = tmp_path / "view.png"
        result = cad_view_3d_render(
            ViewRenderInput(view_id="iso", dpi=72, output=str(target))
        )
        assert result.status == "success"
        assert target.exists()

    def test_render_missing_view(self) -> None:
        _seed()
        result = cad_view_3d_render(ViewRenderInput(view_id="missing"))
        assert result.status == "error"

    def test_section_success(self) -> None:
        _seed()
        result = cad_view_section(
            ViewSectionInput(plane="XY", offset=1.0, dpi=72)
        )
        assert result.status == "success"
        assert result.size_bytes > 1000

    def test_section_invalid_plane(self) -> None:
        _seed()
        result = cad_view_section(ViewSectionInput(plane="ZZ", offset=0.0))
        assert result.status == "error"

    def test_explode_success(self) -> None:
        _seed()
        result = cad_view_explode(ViewExplodeInput(offset_x=0.5, dpi=72))
        assert result.status == "success"
        assert result.size_bytes > 1000

    def test_animation_success(self) -> None:
        _seed()
        result = cad_view_animation(ViewAnimationInput(frames=4, fps=5))
        assert result.status == "success"
        assert result.size_bytes > 100
        assert result.data_uri.startswith("data:image/gif;base64,")

    def test_animation_invalid_mode(self) -> None:
        _seed()
        result = cad_view_animation(ViewAnimationInput(mode="spiral", frames=4))
        assert result.status == "error"


class TestWebGLSync:
    """cad_webgl_sync tool behaviour."""

    def test_sync_delta(self) -> None:
        _seed()
        result = cad_webgl_sync(WebGLSyncInput(previous_ids=["nonexistent"]))
        assert result.status == "success"
        assert len(result.added) == 2
        assert result.updated == []

    def test_sync_removed(self) -> None:
        _seed()
        result = cad_webgl_sync(WebGLSyncInput(previous_ids=["gone"]))
        assert result.status == "success"
        assert result.object_count == 2
        result2 = cad_webgl_sync(
            WebGLSyncInput(previous_ids=[*result.added])
        )
        assert result2.added == []
        assert result2.updated == result.added

    def test_sync_include_full(self) -> None:
        _seed()
        result = cad_webgl_sync(WebGLSyncInput(previous_ids=[], include_full=True))
        assert result.status == "success"
        assert result.has_full
        assert result.full_data_uri.startswith("data:application/json;base64,")
