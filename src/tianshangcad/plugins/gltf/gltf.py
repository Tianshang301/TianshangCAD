"""glTF 2.0 export/import core for the gltf plugin.

The exporter tessellates each solid entity through the active CAD kernel,
packs every mesh into a single embedded (base64 data-URI) binary buffer and
maps each entity's ``color`` property onto a PBR ``baseColorFactor``. The
importer reads the JSON scene back and extracts per-mesh ``(vertices, faces)``
so it can round-trip through the analytic kernel's ``mesh`` shape.
"""

from __future__ import annotations

import base64
import json
import struct
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

from tianshangcad.core.kernel import CADKernel, get_kernel
from tianshangcad.utils.errors import CADExportError, CADImportError

# glTF componentType / dataType constants (glTF 2.0 spec).
_FLOAT = 5126
_UNSIGNED_INT = 5125
_ARRAY_BUFFER = 34962
_ELEMENT_ARRAY_BUFFER = 34963

#: Default neutral material colour when an entity carries no color.
_DEFAULT_COLOR = (0.6, 0.6, 0.6, 1.0)


def _parse_color(value: Any) -> tuple[float, float, float, float]:
    """Parse ``#RRGGBB`` (or ``#RRGGBBAA``) into an RGBA float tuple."""
    text = str(value or "")
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 6:
        r, g, b = text[0:2], text[2:4], text[4:6]
        a = "FF"
    elif len(text) == 8:
        r, g, b, a = text[0:2], text[2:4], text[4:6], text[6:8]
    else:
        return _DEFAULT_COLOR
    try:
        return (int(r, 16) / 255.0, int(g, 16) / 255.0, int(b, 16) / 255.0, int(a, 16) / 255.0)
    except ValueError:
        return _DEFAULT_COLOR


def export_gltf(records: Sequence[Any], kernel: CADKernel | None = None) -> dict[str, Any]:
    """Build a self-contained glTF 2.0 JSON document from solid entities.

    Wireframe entities (line / circle / arc) are skipped — glTF meshes carry
    triangle geometry. Returns the JSON-serialisable glTF document with the
    binary buffer embedded as a base64 data URI.
    """
    active = kernel or get_kernel()
    meshes: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = []
    material_of: dict[tuple[float, float, float, float], int] = {}

    all_positions: list[float] = []
    all_indices: list[int] = []
    accessors: list[dict[str, Any]] = []
    pos_offsets: list[int] = []
    idx_offsets: list[int] = []
    vertex_counts: list[int] = []
    index_counts: list[int] = []

    for record in records:
        shape = record.shape
        if shape["kind"] not in ("box", "cylinder", "sphere", "cone", "mesh"):
            continue
        vertices, faces = active.tessellate(shape)
        flat_faces = [index for face in faces for index in face if len(face) >= 3]
        if not vertices or not flat_faces:
            continue

        color = _parse_color((record.properties or {}).get("color"))
        material_index = material_of.get(color)
        if material_index is None:
            material_index = len(materials)
            material_of[color] = material_index
            materials.append(
                {
                    "name": f"material_{material_index}",
                    "pbrMetallicRoughness": {
                        "baseColorFactor": list(color),
                        "metallicFactor": 0.1,
                        "roughnessFactor": 0.7,
                    },
                }
            )

        pos_offsets.append(len(all_positions))
        idx_offsets.append(len(all_indices))
        vertex_counts.append(len(vertices))
        index_counts.append(len(flat_faces))
        for vertex in vertices:
            all_positions.extend((float(vertex[0]), float(vertex[1]), float(vertex[2])))
        all_indices.extend(flat_faces)

        meshes.append(
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": 2 * len(meshes)},
                        "indices": 2 * len(meshes) + 1,
                        "material": material_index,
                    }
                ]
            }
        )
        nodes.append({"mesh": len(nodes), "name": record.id})

    # Pack the binary buffer: float32 positions then uint32 indices.
    positions_bytes = np.asarray(all_positions, dtype="<f4").tobytes()
    indices_bytes = np.asarray(all_indices, dtype="<u4").tobytes()
    # 4-byte align the indices buffer after the positions buffer.
    positions_end = len(positions_bytes)
    indices_start = (positions_end + 3) & ~3
    buffer = bytearray(indices_start + len(indices_bytes))
    buffer[:positions_end] = positions_bytes
    buffer[indices_start : indices_start + len(indices_bytes)] = indices_bytes

    accessors = []
    for i in range(len(meshes)):
        accessors.append(
            {
                "bufferView": 0,
                "byteOffset": pos_offsets[i] * 4,
                "componentType": _FLOAT,
                "count": vertex_counts[i],
                "type": "VEC3",
                "min": _accessor_min(all_positions, pos_offsets[i], vertex_counts[i]),
                "max": _accessor_max(all_positions, pos_offsets[i], vertex_counts[i]),
            }
        )
        accessors.append(
            {
                "bufferView": 1,
                "byteOffset": idx_offsets[i] * 4,
                "componentType": _UNSIGNED_INT,
                "count": index_counts[i],
                "type": "SCALAR",
            }
        )

    buffer_views = [
        {"buffer": 0, "byteOffset": 0, "byteLength": positions_end, "target": _ARRAY_BUFFER},
        {
            "buffer": 0,
            "byteOffset": indices_start,
            "byteLength": len(indices_bytes),
            "target": _ELEMENT_ARRAY_BUFFER,
        },
    ]

    uri = "data:application/octet-stream;base64," + base64.b64encode(bytes(buffer)).decode("ascii")
    return {
        "asset": {"version": "2.0", "generator": "tianshangcad-server"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"uri": uri, "byteLength": len(buffer)}],
    }


def _accessor_min(positions: list[float], offset: int, count: int) -> list[float]:
    start = offset
    values = positions[start : start + count * 3]
    return [
        min(values[0::3]),
        min(values[1::3]),
        min(values[2::3]),
    ]


def _accessor_max(positions: list[float], offset: int, count: int) -> list[float]:
    start = offset
    values = positions[start : start + count * 3]
    return [
        max(values[0::3]),
        max(values[1::3]),
        max(values[2::3]),
    ]


def export_gltf_file(
    records: Sequence[Any], path: str, kernel: CADKernel | None = None, pretty: bool = True
) -> str:
    """Export solid entities to a glTF file and return the path."""
    data = export_gltf(records, kernel)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(
            json.dumps(data, indent=2 if pretty else None, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        raise CADExportError(f"Failed to write glTF {target}: {exc}", code="write_failed") from exc
    return str(target)


def _read_buffer(gltf: dict[str, Any]) -> bytes:
    """Return the binary payload of the first buffer (base64 data URI)."""
    buffers = gltf.get("buffers") or []
    if not buffers:
        raise CADImportError("glTF has no buffers", code="invalid_gltf")
    uri = buffers[0].get("uri", "")
    if uri.startswith("data:"):
        _, _, payload = uri.partition(",")
        try:
            return base64.b64decode(payload)
        except ValueError as exc:
            raise CADImportError(f"Invalid base64 buffer: {exc}", code="invalid_gltf") from exc
    raise CADImportError("external .bin buffers are not supported", code="unsupported_gltf")


def import_gltf(gltf: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract per-mesh ``(vertices, faces)`` from a glTF document.

    Returns a list of dicts with ``name`` and ``params`` (a ``mesh`` shape's
    ``vertices`` / ``faces``), ready to be turned into ``mesh`` entities.
    """
    buffer = _read_buffer(gltf)
    views = gltf.get("bufferViews", [])
    accessors = gltf.get("accessors", [])
    meshes: list[dict[str, Any]] = []
    for node in gltf.get("nodes", []):
        mesh_index = node.get("mesh")
        if mesh_index is None:
            continue
        mesh = gltf["meshes"][mesh_index]
        primitive = mesh["primitives"][0]
        position_accessor = accessors[primitive["attributes"]["POSITION"]]
        vertices = _read_vertices(buffer, views, position_accessor)
        faces: list[list[int]] = []
        if "indices" in primitive:
            index_accessor = accessors[primitive["indices"]]
            indices = _read_indices(buffer, views, index_accessor)
            faces = [indices[i : i + 3] for i in range(0, len(indices), 3)]
        meshes.append(
            {
                "name": node.get("name", f"mesh_{mesh_index}"),
                "vertices": vertices,
                "faces": faces,
            }
        )
    return meshes


def _read_vertices(
    buffer: bytes, views: list[dict[str, Any]], accessor: dict[str, Any]
) -> list[list[float]]:
    view = views[accessor["bufferView"]]
    offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    count = accessor["count"]
    raw = buffer[offset : offset + count * 3 * 4]
    floats = struct.unpack(f"<{count * 3}f", raw)
    return [[floats[i], floats[i + 1], floats[i + 2]] for i in range(0, len(floats), 3)]


def _read_indices(
    buffer: bytes, views: list[dict[str, Any]], accessor: dict[str, Any]
) -> list[int]:
    view = views[accessor["bufferView"]]
    offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    count = accessor["count"]
    component_type = accessor.get("componentType", _UNSIGNED_INT)
    if component_type == 5123:  # UNSIGNED_SHORT
        raw = buffer[offset : offset + count * 2]
        return list(struct.unpack(f"<{count}H", raw))
    raw = buffer[offset : offset + count * 4]
    return list(struct.unpack(f"<{count}I", raw))


def load_gltf(path: str) -> dict[str, Any]:
    """Load a ``.gltf`` file into a parsed document dict."""
    target = Path(path)
    if not target.is_file():
        raise CADImportError(f"File does not exist: {path}", code="file_not_found")
    try:
        return cast(dict[str, Any], json.loads(target.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise CADImportError(f"Failed to read glTF {path}: {exc}", code="read_failed") from exc
