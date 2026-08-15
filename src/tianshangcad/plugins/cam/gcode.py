"""G-code emission for the cam plugin."""

from __future__ import annotations

from tianshangcad.plugins.cam.toolpath import Toolpath


def _fmt(value: float) -> str:
    """Format a coordinate with fixed precision (trailing zeros trimmed)."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


def emit_gcode(
    toolpath: Toolpath,
    *,
    clearance: float = 5.0,
    feed: float = 200.0,
    plunge: float = 100.0,
    spindle: int = 2000,
) -> str:
    """Serialize a toolpath as a simple 2.5-axis G-code program.

    Emits ``G21`` (mm) / ``G90`` (absolute) / ``G17`` (XY plane), rapid
    moves (``G0``), linear cuts (``G1``), a drill cycle (``G0`` rapid, ``G1``
    plunge, ``G0`` retract) per drill site, and an ``M2`` program end.
    """
    lines = ["%", "G21", "G90", "G17", f"M3 S{spindle}", f"F{feed:.0f}"]

    for contour in toolpath.contours:
        for move in contour:
            code = "G0" if move.rapid else "G1"
            lines.append(f"{code} X{_fmt(move.x)} Y{_fmt(move.y)} Z{_fmt(move.z)}")

    for drill in toolpath.drills:
        lines.append(f"G0 X{_fmt(drill.x)} Y{_fmt(drill.y)} Z{_fmt(clearance)}")
        lines.append(f"G1 Z{_fmt(drill.depth)} F{plunge:.0f}")
        lines.append(f"G0 Z{_fmt(clearance)}")
        lines.append(f"F{feed:.0f}")

    lines.extend(["M5", "M2"])
    return "\n".join(lines) + "\n"
