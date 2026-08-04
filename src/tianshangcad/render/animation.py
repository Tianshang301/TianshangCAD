"""Orbit / turntable GIF animation rendering.

Renders a sequence of camera poses around the model and assembles them
into an animated GIF using ``imageio``.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from tianshangcad.core.kernel import CADKernel
from tianshangcad.render.renderer_3d import render_3d
from tianshangcad.schemas.view3d import AnimationSpec, CameraPose
from tianshangcad.utils.errors import CADValidationError

GIF_MIN_FRAMES = 2
GIF_MAX_FRAMES = 96


def _frame_poses(
    camera: CameraPose,
    spec: AnimationSpec,
) -> list[CameraPose]:
    """Return the camera pose for each animation frame."""
    poses: list[CameraPose] = []
    if spec.mode == "turntable":
        for i in range(spec.frames):
            angle = spec.total_degrees * i / spec.frames
            poses.append(
                camera.model_copy(
                    update={"azimuth": camera.azimuth + angle}
                )
            )
        return poses
    # orbit: full revolution around the target
    for i in range(spec.frames):
        angle = spec.total_degrees * i / spec.frames
        poses.append(
            camera.model_copy(
                update={
                    "azimuth": camera.azimuth + angle,
                    "elevation": camera.elevation,
                }
            )
        )
    return poses


def render_orbit_gif(
    records: Sequence[Any],
    frames: int = 48,
    fps: int = 10,
    output: str | None = None,
    kernel: CADKernel | None = None,
    camera: CameraPose | None = None,
    spec: AnimationSpec | None = None,
    title: str | None = None,
    duration_s: float | None = None,
) -> bytes:
    """Render an orbiting animation of ``records`` as GIF bytes.

    ``frames`` must be within ``[2, 96]``. When ``output`` is given the
    bytes are also written to that path. Returns GIF bytes.
    """
    if not GIF_MIN_FRAMES <= frames <= GIF_MAX_FRAMES:
        raise CADValidationError(
            f"frames must be within [{GIF_MIN_FRAMES}, {GIF_MAX_FRAMES}]",
            code="invalid_frames",
        )
    if fps < 1 or fps > 30:
        raise CADValidationError("fps must be within [1, 30]", code="invalid_fps")
    if camera is None:
        camera = CameraPose(azimuth=45.0, elevation=35.264, distance=10.0)
    active_spec = spec or AnimationSpec(frames=frames, fps=fps)
    poses = _frame_poses(camera, active_spec)
    images: list[Any] = []
    for pose in poses:
        png = render_3d(
            records,
            dpi=96,
            kernel=kernel,
            camera=pose,
            title=title,
        )
        import matplotlib.image as mpimg

        frame = np.asarray(mpimg.imread(io.BytesIO(png)))
        frame = (frame * 255.0).clip(0, 255).astype(np.uint8)
        images.append(frame)

    import imageio.v2 as imageio

    duration = duration_s if duration_s is not None else 1.0 / fps
    buffer = io.BytesIO()
    imageio.mimsave(
        buffer,  # type: ignore[call-overload]
        images,
        format="GIF",
        duration=duration,
        loop=0,
    )
    gif_bytes = buffer.getvalue()
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gif_bytes)
    return gif_bytes
