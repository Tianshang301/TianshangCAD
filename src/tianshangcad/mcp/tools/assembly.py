"""Assembly modelling tools: create, add parts, sub-assemblies, mates, solve, BOM and explode."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tianshangcad.core.assembly import AssemblyDocument
from tianshangcad.core.document import DocumentManager
from tianshangcad.utils.errors import AssemblyError, CADError


class AssemblyCreateInput(BaseModel):
    """Input for creating an assembly."""

    name: str = Field("assembly", description="Assembly name")


class AssemblyCreateOutput(BaseModel):
    """Output for creating an assembly."""

    assembly_id: str = Field(..., description="Assembly identifier")
    name: str = Field(..., description="Assembly name")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class AssemblyAddPartInput(BaseModel):
    """Input for adding a part to an assembly."""

    name: str = Field(..., description="Part name")
    entity_id: str | None = Field(None, description="Referenced document entity id")
    parent_id: str | None = Field(None, description="Parent node id (sub-assembly)")
    translation: list[float] | None = Field(None, description="Local translation [x, y, z]")
    euler: list[float] | None = Field(None, description="Local Euler angles [yaw, pitch, roll]")
    properties: dict[str, Any] | None = Field(None, description="Part properties")


class AssemblyAddPartOutput(BaseModel):
    """Output for adding a part."""

    node_id: str = Field(..., description="Assembly node identifier")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class AssemblyAddSubasmInput(BaseModel):
    """Input for adding a sub-assembly."""

    name: str = Field(..., description="Sub-assembly name")
    parent_id: str | None = Field(None, description="Parent node id")


class AssemblyAddSubasmOutput(BaseModel):
    """Output for adding a sub-assembly."""

    node_id: str = Field(..., description="Sub-assembly node identifier")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class AssemblyAddMateInput(BaseModel):
    """Input for adding a mate."""

    mate_type: str = Field(
        ...,
        description="Mate type: coincident, concentric, parallel, perpendicular, distance, angle",
    )
    node_a: str = Field(..., description="Anchor node id")
    node_b: str = Field(..., description="Target node id")
    distance: float | None = Field(None, description="Distance value (for distance/angle mates)")
    angle: float | None = Field(None, description="Angle in degrees (for angle mates)")
    axis: list[float] | None = Field(None, description="Axis direction [x, y, z]")


class AssemblyAddMateOutput(BaseModel):
    """Output for adding a mate."""

    mate_id: str = Field(..., description="Mate identifier")
    mate_type: str = Field(..., description="Mate type")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class AssemblySolveInput(BaseModel):
    """Input for solving the assembly."""


class AssemblySolveOutput(BaseModel):
    """Output for solving the assembly."""

    transforms: dict[str, dict[str, list[float]]] = Field(
        default_factory=dict, description="World transform of every node"
    )
    mate_count: int = Field(0, description="Number of mates solved")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class AssemblyBomInput(BaseModel):
    """Input for generating a bill of materials."""

    format: str = Field("json", description="Output format: json or csv")


class AssemblyBomOutput(BaseModel):
    """Output for generating a bill of materials."""

    bom: list[dict[str, Any]] = Field(default_factory=list, description="BOM rows")
    csv: str | None = Field(None, description="CSV text when requested")
    part_count: int = Field(0, description="Total number of parts")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class AssemblyExplodeInput(BaseModel):
    """Input for computing an exploded view."""

    spacing: float = Field(10.0, description="Offset per level of nesting", gt=0)
    direction: str = Field("x", description="Explode direction: x, y or z")


class AssemblyExplodeOutput(BaseModel):
    """Output for computing an exploded view."""

    records: list[dict[str, Any]] = Field(default_factory=list, description="Exploded positions")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _require_assembly() -> AssemblyDocument:
    return DocumentManager().get_current().assembly()


def _local_from_parts(
    translation: list[float] | None, euler: list[float] | None
) -> dict[str, list[float]]:
    return {
        "translation": list(translation or [0.0, 0.0, 0.0]),
        "euler": list(euler or [0.0, 0.0, 0.0]),
    }


def cad_assembly_create(input: AssemblyCreateInput) -> AssemblyCreateOutput:
    """Create an assembly in the current document.

    Initializes the document's assembly container. Returns an assembly
    identifier which is stable for the lifetime of the document.
    """
    try:
        assembly = DocumentManager().get_current().assembly(input.name)
        return AssemblyCreateOutput(
            assembly_id=assembly.name,
            name=assembly.name,
            status="success",
            message=f"Assembly {assembly.name} ready",
        )
    except CADError as exc:
        return AssemblyCreateOutput(
            assembly_id="", name=input.name, status="error", message=str(exc)
        )


def cad_assembly_add_part(input: AssemblyAddPartInput) -> AssemblyAddPartOutput:
    """Add a part to the assembly.

    Parts can reference an existing document entity (``entity_id``) or be
    placed purely by name. ``parent_id`` nests the part inside a
    sub-assembly.
    """
    try:
        assembly = _require_assembly()
        node_id = assembly.add_part(
            name=input.name,
            local=_local_from_parts(input.translation, input.euler),
            entity_id=input.entity_id,
            parent_id=input.parent_id,
            properties=input.properties,
        )
        return AssemblyAddPartOutput(
            node_id=node_id, status="success", message=f"Added part {input.name}"
        )
    except AssemblyError as exc:
        return AssemblyAddPartOutput(node_id="", status="error", message=str(exc))


def cad_assembly_add_subasm(input: AssemblyAddSubasmInput) -> AssemblyAddSubasmOutput:
    """Add a sub-assembly container to the assembly tree."""
    try:
        assembly = _require_assembly()
        node_id = assembly.add_subassembly(name=input.name, parent_id=input.parent_id)
        return AssemblyAddSubasmOutput(
            node_id=node_id, status="success", message=f"Added sub-assembly {input.name}"
        )
    except AssemblyError as exc:
        return AssemblyAddSubasmOutput(node_id="", status="error", message=str(exc))


def cad_assembly_add_mate(input: AssemblyAddMateInput) -> AssemblyAddMateOutput:
    """Add a mate between two assembly nodes.

    Supported mate types are coincident, concentric, parallel,
    perpendicular, distance and angle. Distance/angle mates accept their
    values via the ``distance`` / ``angle`` fields and an optional ``axis``
    for distance mates.
    """
    try:
        assembly = _require_assembly()
        params: dict[str, Any] = {}
        if input.distance is not None:
            params["distance"] = input.distance
        if input.angle is not None:
            params["angle"] = input.angle
        if input.axis is not None:
            params["axis"] = list(input.axis)
        mate_id = assembly.add_mate(
            input.mate_type, input.node_a, input.node_b, params
        )
        return AssemblyAddMateOutput(
            mate_id=mate_id,
            mate_type=input.mate_type,
            status="success",
            message=f"Added {input.mate_type} mate {mate_id}",
        )
    except AssemblyError as exc:
        return AssemblyAddMateOutput(
            mate_id="", mate_type=input.mate_type, status="error", message=str(exc)
        )


def cad_assembly_solve(input: AssemblySolveInput) -> AssemblySolveOutput:
    """Solve the assembly and return every node's world transform.

    Applies each mate in creation order, treating the first node as the
    anchor. Use after building parts and mates to obtain the final
    disposition.
    """
    del input
    try:
        assembly = _require_assembly()
        transforms = assembly.solve()
        return AssemblySolveOutput(
            transforms=transforms,
            mate_count=len(assembly.mates),
            status="success",
            message=f"Solved {len(assembly.mates)} mates",
        )
    except AssemblyError as exc:
        return AssemblySolveOutput(status="error", message=str(exc))


def cad_assembly_bom(input: AssemblyBomInput) -> AssemblyBomOutput:
    """Generate a bill of materials for the assembly.

    Flattens the tree, tallying unique part names into quantities. Use
    ``format="csv"`` to also receive comma-separated text.
    """
    try:
        assembly = _require_assembly()
        rows = assembly.bom()
        csv_text = assembly.bom_csv() if input.format.lower() == "csv" else None
        total = sum(int(row["quantity"]) for row in rows)
        return AssemblyBomOutput(
            bom=rows,
            csv=csv_text,
            part_count=total,
            status="success",
            message=f"{total} parts across {len(rows)} unique items",
        )
    except AssemblyError as exc:
        return AssemblyBomOutput(status="error", message=str(exc))


def cad_assembly_explode(input: AssemblyExplodeInput) -> AssemblyExplodeOutput:
    """Compute an exploded view of the assembly.

    Offsets every node radially along the given direction (``x``/``y``/``z``)
    by ``spacing`` per level of nesting. Mates are ignored - only the tree
    depth matters.
    """
    try:
        assembly = _require_assembly()
        records = assembly.explode(spacing=input.spacing, direction=input.direction)
        return AssemblyExplodeOutput(
            records=records,
            status="success",
            message=f"Exploded {len(records)} nodes",
        )
    except AssemblyError as exc:
        return AssemblyExplodeOutput(status="error", message=str(exc))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_assembly_create", cad_assembly_create),
    ("cad_assembly_add_part", cad_assembly_add_part),
    ("cad_assembly_add_subasm", cad_assembly_add_subasm),
    ("cad_assembly_add_mate", cad_assembly_add_mate),
    ("cad_assembly_solve", cad_assembly_solve),
    ("cad_assembly_bom", cad_assembly_bom),
    ("cad_assembly_explode", cad_assembly_explode),
]
