"""STEP importer (pure-Python AP203 faceted BREP reader).

Parses the ``MANIFOLD_SOLID_BREP`` / ``CLOSED_SHELL`` / ``ADVANCED_FACE`` /
``FACE_OUTER_BOUND`` / ``POLY_LOOP`` / ``CARTESIAN_POINT`` structures emitted
by the STEP exporter and rebuilds each solid as a ``mesh`` entity with a
shared vertex pool and per-face index lists.
"""

from __future__ import annotations

import re
from pathlib import Path

from cad_mcp_server.core.document import DocumentState
from cad_mcp_server.utils.errors import CADImportError

_ENTITY_RE = re.compile(r"#(\d+)\s*=\s*([A-Z_]+)\s*\((.*)\)\s*;")
_EPSILON = 1e-9


class STEPImporter:
    """Import AP203 faceted BREP STEP files into a document."""

    def import_file(self, filepath: str) -> DocumentState:
        """Read a STEP file and build a new document."""
        path = Path(filepath)
        if not path.is_file():
            raise CADImportError(f"File does not exist: {filepath}", code="file_not_found")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise CADImportError(
                f"Failed to read STEP {filepath}: {exc}", code="read_failed"
            ) from exc

        entities = _parse_entities(text)
        solids = _extract_solids(entities)
        if not solids:
            raise CADImportError(
                f"No MANIFOLD_SOLID_BREP geometry found in {filepath}",
                code="no_geometry",
            )

        doc = DocumentState(
            file_id=f"file_{path.stem}",
            filename=path.name,
            unit="mm",
            path=path,
        )
        for vertices, faces in solids:
            doc.entities.create("mesh", {"vertices": vertices, "faces": faces})
        doc.is_dirty = False
        return doc


def _parse_entities(text: str) -> dict[int, tuple[str, str]]:
    """Return ``{instance_id: (entity_name, raw_args)}`` for the DATA section."""
    data = text.split("DATA;", 1)[-1]
    data = data.split("ENDSEC;", 1)[0]
    entities: dict[int, tuple[str, str]] = {}
    for match in _ENTITY_RE.finditer(data):
        instance_id = int(match.group(1))
        entities[instance_id] = (match.group(2), match.group(3))
    return entities


def _extract_solids(
    entities: dict[int, tuple[str, str]]
) -> list[tuple[list[list[float]], list[list[int]]]]:
    """Extract ``(vertices, faces)`` for every MANIFOLD_SOLID_BREP."""
    solids: list[tuple[list[list[float]], list[list[int]]]] = []
    for _instance_id, (name, args) in entities.items():
        if name != "MANIFOLD_SOLID_BREP":
            continue
        shell_id = _first_ref(args)
        result = _collect_shell(entities, shell_id)
        if result is not None and len(result[1]) >= 4:
            solids.append(result)
    return solids


def _collect_shell(
    entities: dict[int, tuple[str, str]], shell_id: int
) -> tuple[list[list[float]], list[list[int]]] | None:
    """Collect a shared vertex pool and per-face index lists from a shell."""
    shell_entry = entities.get(shell_id)
    if shell_entry is None or shell_entry[0] != "CLOSED_SHELL":
        return None
    pool: list[list[float]] = []
    index_by_key: dict[tuple[float, float, float], int] = {}
    faces: list[list[int]] = []

    def _vertex(point: list[float]) -> int:
        x, y, z = point[0], point[1], point[2]
        key = (round(x / _EPSILON), round(y / _EPSILON), round(z / _EPSILON))
        index = index_by_key.get(key)
        if index is not None:
            return index
        index = len(pool)
        pool.append(point)
        index_by_key[key] = index
        return index

    for face_id in _parse_refs(shell_entry[1]):
        face_entry = entities.get(face_id)
        if face_entry is None or face_entry[0] != "ADVANCED_FACE":
            continue
        bound_ids = _parse_refs(face_entry[1])
        for bound_id in bound_ids:
            bound_entry = entities.get(bound_id)
            if bound_entry is None or bound_entry[0] != "FACE_OUTER_BOUND":
                continue
            loop_id = _first_ref(bound_entry[1])
            loop_entry = entities.get(loop_id)
            if loop_entry is None or loop_entry[0] != "POLY_LOOP":
                continue
            face: list[int] = []
            for point_id in _parse_refs(loop_entry[1]):
                point_entry = entities.get(point_id)
                if point_entry is None or point_entry[0] != "CARTESIAN_POINT":
                    continue
                point = _parse_point(point_entry[1])
                if point is None:
                    continue
                face.append(_vertex(point))
            if len(face) >= 3:
                faces.append(face)
    if not faces:
        return None
    return pool, faces


def _parse_point(args: str) -> list[float] | None:
    """Parse a CARTESIAN_POINT arg list like ``(1.,2.,3.)``."""
    match = re.search(r"\((.*?)\)", args, flags=re.DOTALL)
    if match is None:
        return None
    try:
        values = [float(value) for value in re.split(r"[,\s]+", match.group(1).strip())]
    except ValueError:
        return None
    return values[:3]


def _parse_refs(args: str) -> list[int]:
    """Parse all ``#123`` references inside an argument string."""
    return [int(value) for value in re.findall(r"#(\d+)", args)]


def _first_ref(args: str) -> int:
    """Return the first ``#123`` reference, or ``-1`` when absent."""
    refs = _parse_refs(args)
    return refs[0] if refs else -1
