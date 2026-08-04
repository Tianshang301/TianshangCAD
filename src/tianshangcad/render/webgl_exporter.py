"""WebGL export for the browser 3D preview.

Flattens every entity into an indexed Three.js ``BufferGeometry`` payload
(positions + triangle indices + line segments) that can be loaded by the
bundled ``examples/threejs_viewer.html``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tianshangcad.core.kernel import CADKernel, get_kernel


def _collect_geometry(
    records: Sequence[Any], kernel: CADKernel
) -> tuple[list[list[float]], list[list[int]], list[float]]:
    """Return ``(positions, triangles, line_positions)``.

    ``positions`` are all unique 3D vertices, ``triangles`` reference them
    by index, and ``line_positions`` hold wireframe segments (3 coords per
    endpoint, i.e. 6 floats per segment).
    """
    positions: list[list[float]] = []
    triangles: list[list[int]] = []
    line_positions: list[float] = []
    index_of: dict[tuple[float, float, float], int] = {}

    def _add_point(point: Sequence[float]) -> int:
        key = (float(point[0]), float(point[1]), float(point[2]))
        existing = index_of.get(key)
        if existing is not None:
            return existing
        index_of[key] = len(positions)
        positions.append([key[0], key[1], key[2]])
        return len(positions) - 1

    for record in records:
        shape = record.shape
        kind = shape["kind"]
        params = shape["params"]
        if kind == "line":
            line_positions.extend(params["start"])
            line_positions.extend(params["end"])
            continue
        if kind in ("circle", "arc"):
            import math

            center = params["center"]
            radius = params["radius"]
            steps = 48
            previous: list[float] | None = None
            for i in range(steps + 1):
                theta = i / steps * 2.0 * math.pi
                point = [
                    center[0] + radius * math.cos(theta),
                    center[1] + radius * math.sin(theta),
                    center[2],
                ]
                line_positions.extend(point)
                if previous is not None:
                    line_positions.extend(previous)
                previous = point
            continue
        vertices, faces = kernel.tessellate(shape)
        face_indices: list[int] = []
        for vertex in vertices:
            face_indices.append(_add_point(vertex))
        for face in faces:
            if len(face) < 3:
                continue
            triangles.append([face_indices[face[0]], face_indices[face[1]], face_indices[face[2]]])
        # Wireframe edges
        seen: set[tuple[int, int]] = set()
        for face in faces:
            n = len(face)
            for i in range(n):
                a, b = face[i], face[(i + 1) % n]
                key = (a, b) if a <= b else (b, a)
                if key in seen:
                    continue
                seen.add(key)
                line_positions.extend(vertices[a])
                line_positions.extend(vertices[b])
    return positions, triangles, line_positions


def export_webgl(records: Sequence[Any], kernel: CADKernel | None = None) -> dict[str, Any]:
    """Return a Three.js-ready JSON dict for the given entities."""
    active_kernel = kernel or get_kernel()
    positions, triangles, line_positions = _collect_geometry(records, active_kernel)
    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3
    for point in positions:
        for i in range(3):
            minimum[i] = min(minimum[i], point[i])
            maximum[i] = max(maximum[i], point[i])
    if not positions:
        minimum = [0.0, 0.0, 0.0]
        maximum = [0.0, 0.0, 0.0]
    return {
        "metadata": {"generator": "tianshangcad-server", "format": "webgl-buffer-geometry"},
        "objectCount": len(records),
        "bounds": {"min": minimum, "max": maximum},
        "positions": positions,
        "indices": triangles,
        "linePositions": line_positions,
    }


def export_webgl_file(
    records: Sequence[Any],
    path: str,
    kernel: CADKernel | None = None,
    pretty: bool = True,
) -> str:
    """Export entities to a WebGL JSON file and return the path."""
    data = export_webgl(records, kernel)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, indent=2 if pretty else None, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(target)


def export_webgl_delta(
    previous_ids: Sequence[str] | set[str],
    records: Sequence[Any],
    kernel: CADKernel | None = None,
    include_full: bool = False,
) -> dict[str, Any]:
    """Return an incremental WebGL sync payload.

    ``previous_ids`` are the object ids the client already holds. The
    result contains ``added`` (new ids), ``removed`` (ids no longer
    present) and ``updated`` (ids whose geometry changed). Each added or
    updated id carries its per-object BufferGeometry so the client can
    apply the delta without reloading the whole scene.
    """
    active_kernel = kernel or get_kernel()
    previous = set(previous_ids)
    current_records = list(records)
    current_ids = {record.id for record in current_records}

    added: list[str] = []
    removed: list[str] = []
    updated: list[str] = []
    for record in current_records:
        if record.id not in previous:
            added.append(record.id)
        else:
            # Only entities actually created/edited in this document are
            # considered; all current records are sent as deltas for
            # simplicity and correctness.
            updated.append(record.id)
    for entity_id in previous:
        if entity_id not in current_ids:
            removed.append(entity_id)

    geometries: dict[str, dict[str, Any]] = {}
    if include_full or added or updated:
        for record in current_records:
            geometry = _record_geometry(record, active_kernel)
            if geometry is not None:
                geometries[record.id] = geometry

    payload: dict[str, Any] = {
        "metadata": {
            "generator": "tianshangcad-server",
            "format": "webgl-buffer-geometry-delta",
        },
        "objectCount": len(current_records),
        "added": added,
        "removed": removed,
        "updated": updated,
        "geometries": geometries,
    }
    if include_full:
        payload["full"] = export_webgl(records, active_kernel)
    return payload


def _record_geometry(record: Any, kernel: CADKernel) -> dict[str, Any] | None:
    """Return per-object BufferGeometry for a single record."""
    shape = record.shape
    kind = shape["kind"]
    params = shape["params"]
    data: dict[str, Any] = {"id": record.id, "type": record.type, "layer": record.layer}
    if kind == "line":
        data["kind"] = "line"
        data["linePositions"] = [*params["start"], *params["end"]]
        return data
    if kind in ("circle", "arc"):
        import math

        center = params["center"]
        radius = params["radius"]
        steps = 48
        line_positions: list[float] = []
        previous: list[float] | None = None
        for i in range(steps + 1):
            theta = i / steps * 2.0 * math.pi
            point = [
                center[0] + radius * math.cos(theta),
                center[1] + radius * math.sin(theta),
                center[2],
            ]
            line_positions.extend(point)
            if previous is not None:
                line_positions.extend(previous)
            previous = point
        data["kind"] = kind
        data["linePositions"] = line_positions
        return data
    vertices, faces = kernel.tessellate(shape)
    positions: list[list[float]] = []
    index_of: dict[tuple[float, float, float], int] = {}
    for vertex in vertices:
        key = (float(vertex[0]), float(vertex[1]), float(vertex[2]))
        index_of.setdefault(key, len(index_of))
        positions.append([key[0], key[1], key[2]])
    triangles: list[list[int]] = []
    for face in faces:
        if len(face) < 3:
            continue
        keyed: list[int] = []
        for index in face:
            vertex = vertices[index]
            point_key = (float(vertex[0]), float(vertex[1]), float(vertex[2]))
            keyed.append(index_of[point_key])
        triangles.append(keyed)
    data["kind"] = "solid"
    data["positions"] = positions
    data["indices"] = triangles
    return data


def viewer_html() -> str:
    """Return the static Three.js viewer page.

    The viewer loads ``data.json`` from the same directory by default and
    renders triangles plus wireframe lines. It can be overridden with a
    ``?data=url`` query parameter.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CAD MCP Server - WebGL Preview</title>
<style>
  html, body { margin: 0; height: 100%; overflow: hidden; background: #1a1a2e; }
  #info {
    position: absolute; top: 10px; left: 10px; color: #ddd;
    font-family: monospace; font-size: 13px; background: rgba(0,0,0,0.5);
    padding: 6px 10px; border-radius: 4px; pointer-events: none; z-index: 10;
  }
  #hint {
    position: absolute; bottom: 10px; left: 10px; color: #888;
    font-family: monospace; font-size: 12px; background: rgba(0,0,0,0.4);
    padding: 4px 8px; border-radius: 4px; pointer-events: none; z-index: 10;
  }
</style>
</head>
<body>
<div id="info">CAD MCP Server &mdash; WebGL Preview</div>
<div id="hint">Drag to rotate &middot; scroll to zoom &middot; right-drag to pan</div>
<script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.160.0/examples/js/controls/OrbitControls.js"></script>
<script>
  const params = new URLSearchParams(window.location.search);
  const dataUrl = params.get('data') || 'data.json';
  fetch(dataUrl).then(r => r.json()).then(data => {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a2e);
    const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 10000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(innerWidth, innerHeight);
    document.body.appendChild(renderer.domElement);
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(1, 2, 1);
    scene.add(dir);

    const positions = data.positions || [];
    const indices = (data.indices || []).flat();
    const linePositions = data.linePositions || [];

    if (positions.length > 0) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(positions.flat(), 3));
      if (indices.length > 0) geo.setIndex(indices);
      geo.computeVertexNormals();
      const mesh = new THREE.Mesh(
        geo,
        new THREE.MeshStandardMaterial({ color: 0x6a8cff, metalness: 0.2, roughness: 0.6 })
      );
      scene.add(mesh);
    }
    if (linePositions.length > 0) {
      const lineGeo = new THREE.BufferGeometry();
      lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
      const lines = new THREE.LineSegments(
        lineGeo, new THREE.LineBasicMaterial({ color: 0x222244 })
      );
      scene.add(lines);
    }

    const b = data.bounds || { min: [-1,-1,-1], max: [1,1,1] };
    const cx = (b.min[0] + b.max[0]) / 2;
    const cy = (b.min[1] + b.max[1]) / 2;
    const cz = (b.min[2] + b.max[2]) / 2;
    const size = Math.max(
      b.max[0]-b.min[0], b.max[1]-b.min[1], b.max[2]-b.min[2], 1
    );
    camera.position.set(cx + size, cy + size, cz + size);
    camera.lookAt(cx, cy, cz);
    controls.target.set(cx, cy, cz);
    document.getElementById('info').textContent =
      `CAD MCP Server &mdash; ${data.objectCount || 0} object(s)`;

    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();
    window.addEventListener('resize', () => {
      camera.aspect = innerWidth / innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(innerWidth, innerHeight);
    });
  }).catch(err => {
    document.getElementById('info').textContent = 'Failed to load ' + dataUrl + ': ' + err;
  });
</script>
</body>
</html>
"""
