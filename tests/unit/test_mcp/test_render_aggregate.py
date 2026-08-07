"""Tests for the aggregate cad_render MCP tool."""

from __future__ import annotations

from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from tianshangcad.mcp.tools.render import (
    RenderAnimationParams,
    RenderExplodeParams,
    RenderInput,
    RenderOrthoParams,
    RenderSectionParams,
    RenderView3DParams,
    RenderWebglParams,
    cad_render,
)


def _seed_box() -> str:
    cad_file_create(FileCreateInput(filename="render.json"))
    return cad_object_create(
        ObjectCreateInput(
            type="box",
            params={"origin": [0, 0, 0], "dimensions": [10, 5, 2]},
            layer="0",
        )
    ).object_id


class TestRenderOrtho:
    """cad_render mode=ortho behaviour."""

    def test_ortho_success(self) -> None:
        _seed_box()
        result = cad_render(RenderInput(render=RenderOrthoParams(mode="ortho", view="top", dpi=96)))
        assert result.status == "success"
        assert result.mode == "ortho"
        assert result.size_bytes > 1000
        assert result.data_uri.startswith("data:image/png;base64,")

    def test_ortho_invalid_view(self) -> None:
        _seed_box()
        result = cad_render(
            RenderInput(render=RenderOrthoParams(mode="ortho", view="isometric"))
        )
        assert result.status == "error"

    def test_no_document(self) -> None:
        from tianshangcad.core.session import SessionManager

        SessionManager().reset()
        result = cad_render(RenderInput(render=RenderOrthoParams(mode="ortho", view="top")))
        assert result.status == "error"


class TestRenderView3D:
    """cad_render mode=view_3d behaviour."""

    def _setup_view(self) -> None:
        _seed_box()
        from tianshangcad.mcp.tools.view3d import (
            ViewCreateInput,
            cad_view_3d_create,
        )

        result = cad_view_3d_create(ViewCreateInput(name="my_view"))
        assert result.status == "success"

    def test_view_3d_success(self) -> None:
        self._setup_view()
        result = cad_render(
            RenderInput(render=RenderView3DParams(mode="view_3d", view_id="my_view", dpi=72))
        )
        assert result.status == "success"
        assert result.data_uri.startswith("data:image/png;base64,")

    def test_view_3d_missing_view(self) -> None:
        _seed_box()
        result = cad_render(
            RenderInput(render=RenderView3DParams(mode="view_3d", view_id="missing"))
        )
        assert result.status == "error"


class TestRenderSectionExplodeAnimation:
    """cad_render section / explode / animation modes."""

    def test_section_success(self) -> None:
        _seed_box()
        result = cad_render(
            RenderInput(
                render=RenderSectionParams(mode="section", plane="XY", offset=1.0, dpi=72)
            )
        )
        assert result.status == "success"
        assert result.data_uri.startswith("data:image/png;base64,")

    def test_section_invalid_plane(self) -> None:
        _seed_box()
        result = cad_render(
            RenderInput(render=RenderSectionParams(mode="section", plane="ZZ"))
        )
        assert result.status == "error"

    def test_explode_success(self) -> None:
        _seed_box()
        result = cad_render(
            RenderInput(
                render=RenderExplodeParams(mode="explode", offset_x=0.5, offset_y=0.5, dpi=72)
            )
        )
        assert result.status == "success"
        assert result.data_uri.startswith("data:image/png;base64,")

    def test_animation_success(self) -> None:
        _seed_box()
        result = cad_render(
            RenderInput(render=RenderAnimationParams(mode="animation", frames=4, fps=5))
        )
        assert result.status == "success"
        assert result.data_uri.startswith("data:image/gif;base64,")

    def test_animation_invalid_mode(self) -> None:
        _seed_box()
        result = cad_render(
            RenderInput(
                render=RenderAnimationParams(
                    mode="animation", anim_mode="spiral", frames=4
                )
            )
        )
        assert result.status == "error"


class TestRenderWebgl:
    """cad_render mode=webgl behaviour."""

    def test_webgl_delta(self) -> None:
        _seed_box()
        result = cad_render(
            RenderInput(render=RenderWebglParams(mode="webgl", previous_ids=["nonexistent"]))
        )
        assert result.status == "success"
        assert result.mode == "webgl"
        assert "added" in result.payload
        assert result.payload["object_count"] == 1

    def test_webgl_full_snapshot(self) -> None:
        _seed_box()
        result = cad_render(
            RenderInput(render=RenderWebglParams(mode="webgl", include_full=True))
        )
        assert result.status == "success"
        assert result.data_uri.startswith("data:application/json;base64,")
