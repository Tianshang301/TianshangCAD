"""STEP exporter (pure-Python AP203 faceted BREP).

The exporter tessellates solid entities and writes an AP203
``MANIFOLD_SOLID_BREP`` representation with ``POLY_LOOP`` faces. It requires
no OCCT / FreeCAD dependency and is fully reversible through
:class:`~tianshangcad.io.importers.step.STEPImporter`.
"""

from __future__ import annotations

from pathlib import Path

from tianshangcad.core.document import DocumentState
from tianshangcad.core.kernel import AnalyticKernel
from tianshangcad.utils.errors import CADExportError, CADNotImplementedError

_SCHEMA = "CONFIG_CONTROL_DESIGN"


class STEPExporter:
    """Export solid entities to an AP203 STEP file (faceted BREP)."""

    def __init__(self, kernel: AnalyticKernel | None = None) -> None:
        """Initialize with an analytic kernel (or create a default one)."""
        self._kernel = kernel or AnalyticKernel()

    def export_document(self, doc: DocumentState, filepath: str) -> None:
        """Write ``doc``'s solid entities to a STEP file."""
        bodies = self._collect_solids(doc)
        if not bodies:
            raise CADExportError(
                "No solid geometry to export to STEP", code="no_solid_geometry"
            )
        text = render_step(bodies, doc.filename)
        try:
            Path(filepath).write_text(text, encoding="utf-8")
        except OSError as exc:
            raise CADExportError(
                f"Failed to write STEP {filepath}: {exc}", code="write_failed"
            ) from exc

    def _collect_solids(self, doc: DocumentState) -> list[list[list[list[float]]]]:
        """Return per-face vertex lists for every tessellated solid."""
        bodies: list[list[list[list[float]]]] = []
        for record in doc.entities.list():
            try:
                vertices, faces = self._kernel.tessellate(record.shape)
            except CADNotImplementedError:
                continue
            if len(vertices) < 4 or len(faces) < 4:
                continue
            bodies.append(vertices_per_face(vertices, faces))
        return bodies


def vertices_per_face(
    vertices: list[list[float]], faces: list[list[int]]
) -> list[list[list[float]]]:
    """Expand indexed faces into per-face vertex lists."""
    face_vertices: list[list[list[float]]] = []
    for face in faces:
        points = [list(vertices[index]) for index in face]
        if len(points) >= 3:
            face_vertices.append(points)
    return face_vertices


class _StepBuilder:
    """Append-only STEP writer that tracks the next free instance id."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._next = 1

    def next_id(self) -> int:
        value = self._next
        self._next += 1
        return value

    def emit(self, instance_id: int, text: str) -> None:
        self._lines.append(f"#{instance_id}={text};")

    def cartesian_point(self, point: list[float]) -> int:
        coords = ",".join(f"{value:g}" for value in point)
        instance_id = self.next_id()
        self.emit(instance_id, f"CARTESIAN_POINT('',({coords}))")
        return instance_id

    def direction(self, vector: list[float]) -> int:
        values = ",".join(f"{value:g}" for value in vector)
        instance_id = self.next_id()
        self.emit(instance_id, f"DIRECTION('',({values}))")
        return instance_id

    def poly_loop(self, point_ids: list[int]) -> int:
        refs = ",".join(f"#{point_id}" for point_id in point_ids)
        instance_id = self.next_id()
        self.emit(instance_id, f"POLY_LOOP('',({refs}))")
        return instance_id

    def face_outer_bound(self, loop_id: int) -> int:
        instance_id = self.next_id()
        self.emit(instance_id, f"FACE_OUTER_BOUND('',#{loop_id},.T.)")
        return instance_id

    def advanced_face(self, bound_id: int, plane_id: int) -> int:
        instance_id = self.next_id()
        self.emit(instance_id, f"ADVANCED_FACE('',(#{bound_id}),#{plane_id},.T.)")
        return instance_id

    def plane(self, axis_id: int) -> int:
        instance_id = self.next_id()
        self.emit(instance_id, f"PLANE('',#{axis_id})")
        return instance_id

    def axis_placement(self, origin_id: int, z_id: int, x_id: int) -> int:
        instance_id = self.next_id()
        self.emit(
            instance_id,
            f"AXIS2_PLACEMENT_3D('',#{origin_id},#{z_id},#{x_id})",
        )
        return instance_id

    def closed_shell(self, face_ids: list[int]) -> int:
        refs = ",".join(f"#{face_id}" for face_id in face_ids)
        instance_id = self.next_id()
        self.emit(instance_id, f"CLOSED_SHELL('',({refs}))")
        return instance_id

    def manifold_solid(self, shell_id: int) -> int:
        instance_id = self.next_id()
        self.emit(instance_id, f"MANIFOLD_SOLID_BREP('',#{shell_id})")
        return instance_id

    def representation(self, solid_ids: list[int], context_id: int) -> int:
        refs = ",".join(f"#{solid_id}" for solid_id in solid_ids)
        instance_id = self.next_id()
        self.emit(
            instance_id,
            f"ADVANCED_BREP_SHAPE_REPRESENTATION('',({refs}),#{context_id})",
        )
        return instance_id

    def geometric_context(self) -> int:
        instance_id = self.next_id()
        self.emit(
            instance_id,
            "GEOMETRIC_REPRESENTATION_CONTEXT(3)"
            "GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#999999))"
            "REPRESENTATION_CONTEXT('','')",
        )
        return instance_id

    def product_definition(self) -> int:
        product_id = self.next_id()
        formation_id = self.next_id()
        definition_id = self.next_id()
        self.emit(
            product_id, f"PRODUCT('','','',(#{formation_id}))"
        )
        self.emit(formation_id, f"PRODUCT_DEFINITION_FORMATION('','',#{product_id})")
        context_id = 1000000
        self.emit(
            definition_id,
            f"PRODUCT_DEFINITION('','',#{formation_id},#{context_id})",
        )
        self.emit(context_id, "PRODUCT_DEFINITION_CONTEXT('part definition',#1000001,'design')")
        return definition_id

    def render(self, filename: str) -> str:
        header = [
            "ISO-10303-21;",
            "HEADER;",
            "FILE_DESCRIPTION((''),'2;1');",
            f"FILE_NAME('{filename}','2026-01-01T00:00:00',(''),(''),"
            "'tianshangcad-server','','');",
            f"FILE_SCHEMA(('{_SCHEMA}'));",
            "ENDSEC;",
            "DATA;",
        ]
        return "\n".join(header + self._lines + ["ENDSEC;", "END-ISO-10303-21;"])


def render_step(bodies: list[list[list[list[float]]]], filename: str) -> str:
    """Render all solid bodies into a single AP203 text."""
    builder = _StepBuilder()
    builder.product_definition()
    solid_ids: list[int] = []
    for body in bodies:
        face_ids: list[int] = []
        for points in body:
            point_ids = [builder.cartesian_point(point) for point in points]
            loop_id = builder.poly_loop(point_ids)
            bound_id = builder.face_outer_bound(loop_id)
            z_id = builder.direction([0.0, 0.0, 1.0])
            x_id = builder.direction([1.0, 0.0, 0.0])
            origin_id = builder.cartesian_point([0.0, 0.0, 0.0])
            axis_id = builder.axis_placement(origin_id, z_id, x_id)
            plane_id = builder.plane(axis_id)
            face_ids.append(builder.advanced_face(bound_id, plane_id))
        shell_id = builder.closed_shell(face_ids)
        solid_ids.append(builder.manifold_solid(shell_id))
    context_id = builder.geometric_context()
    builder.representation(solid_ids, context_id)
    return builder.render(filename)
