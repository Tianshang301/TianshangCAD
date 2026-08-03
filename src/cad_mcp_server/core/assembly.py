"""Assembly modelling.

An assembly document holds a hierarchical tree of parts and sub-assemblies
plus a set of mates (relationship constraints) that position one node
relative to another. :meth:`AssemblyDocument.solve` computes the world
transform of every node; :meth:`AssemblyDocument.bom` flattens the tree
into a bill of materials and :meth:`AssemblyDocument.explode` produces a
radially offset copy of each node for display or disassembly views.

This is the **interim** positioning implementation (Phase 7 Task A). It
solves mates deterministically by writing relative transforms directly.
Phase 7 integrates the Spike 1 planegcs backend (:mod:`planegcs_solver`)
as an optional solver for 2D line/circle geometry; the positioning path
below always stays available under ``pip install -e .`` (no extra).
"""

from __future__ import annotations

import builtins
import csv
import enum
import io
import math
import uuid
from typing import Any

from cad_mcp_server.utils.errors import AssemblyError

_X_AXIS = (1.0, 0.0, 0.0)
_Y_AXIS = (0.0, 1.0, 0.0)
_Z_AXIS = (0.0, 0.0, 1.0)


def new_node_id(prefix: str = "pt") -> str:
    """Generate a unique assembly node id."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def new_mate_id(prefix: str = "mate") -> str:
    """Generate a unique mate id."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class MateType(enum.StrEnum):
    """Supported assembly mate kinds."""

    COINCIDENT = "coincident"
    CONCENTRIC = "concentric"
    PARALLEL = "parallel"
    PERPENDICULAR = "perpendicular"
    DISTANCE = "distance"
    ANGLE = "angle"


def identity_transform() -> dict[str, list[float]]:
    """Return a fresh identity local transform."""
    return {"translation": [0.0, 0.0, 0.0], "euler": [0.0, 0.0, 0.0]}


# ---------------------------------------------------------------------------
# Vector / matrix helpers (pure Python, no numpy dependency).
# ---------------------------------------------------------------------------


def _add(a: list[float], b: list[float]) -> list[float]:
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _scale(v: list[float] | tuple[float, ...], c: float) -> list[float]:
    return [v[0] * c, v[1] * c, v[2] * c]


def _norm(v: list[float]) -> list[float]:
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length < 1e-12:
        return [0.0, 0.0, 1.0]
    return _scale(v, 1.0 / length)


def _axis(axis: Any) -> list[float]:
    if isinstance(axis, (list, tuple)):
        values = [float(x) for x in axis]
        if len(values) == 3 and any(abs(x) > 1e-12 for x in values):
            return _norm(values)
    return [0.0, 0.0, 1.0]


def _mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mat_apply(matrix: list[list[float]], v: list[float]) -> list[float]:
    return [
        matrix[0][0] * v[0] + matrix[0][1] * v[1] + matrix[0][2] * v[2],
        matrix[1][0] * v[0] + matrix[1][1] * v[1] + matrix[1][2] * v[2],
        matrix[2][0] * v[0] + matrix[2][1] * v[1] + matrix[2][2] * v[2],
    ]


def _euler_mat(euler: list[float]) -> list[list[float]]:
    """Return a 3x3 rotation from Euler angles (yaw, pitch, roll in radians)."""
    cy, sy = math.cos(euler[0]), math.sin(euler[0])
    cp, sp = math.cos(euler[1]), math.sin(euler[1])
    cr, sr = math.cos(euler[2]), math.sin(euler[2])
    rz = [[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]]
    ry = [[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]]
    rx = [[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]]
    return _mat_mul(rz, _mat_mul(ry, rx))


def _euler_from_matrix(matrix: list[list[float]]) -> list[float]:
    sy = -matrix[2][0]
    if abs(sy) > 1.0 - 1e-9:
        yaw = math.atan2(matrix[0][1], matrix[0][0])
        pitch = math.copysign(math.pi / 2.0, sy)
        roll = 0.0
    else:
        yaw = math.atan2(matrix[1][0], matrix[0][0])
        roll = math.atan2(matrix[2][1], matrix[2][2])
        pitch = math.asin(max(-1.0, min(1.0, sy)))
    return [yaw, pitch, roll]


def _compose(
    parent: dict[str, list[float]], local: dict[str, list[float]]
) -> dict[str, list[float]]:
    """Compose a parent transform with a child's local transform."""
    parent_rot = _euler_mat(parent["euler"])
    local_rot = _euler_mat(local["euler"])
    world_rot = _mat_mul(parent_rot, local_rot)
    world_trans = _add(
        _mat_apply(parent_rot, local["translation"]), parent["translation"]
    )
    return {"translation": world_trans, "euler": _euler_from_matrix(world_rot)}


class AssemblyNode:
    """A single node in the assembly tree (a part or a sub-assembly)."""

    def __init__(
        self,
        node_id: str,
        name: str,
        kind: str,
        local: dict[str, list[float]] | None = None,
        entity_id: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Initialize an assembly node."""
        self.id = node_id
        self.name = name
        self.kind = kind  # "part" | "subassembly"
        self.local: dict[str, list[float]] = identity_transform() if local is None else local
        self.entity_id = entity_id
        self.properties: dict[str, Any] = dict(properties or {})

    @property
    def is_part(self) -> bool:
        """Whether the node is an individual part."""
        return self.kind == "part"

    def to_dict(self) -> dict[str, Any]:
        """Serialize the node to a JSON-safe dict."""
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "local": self.local,
            "entity_id": self.entity_id,
            "properties": dict(self.properties),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssemblyNode:
        """Reconstruct an assembly node from a serialized dict."""
        return cls(
            node_id=str(data["id"]),
            name=str(data["name"]),
            kind=str(data["kind"]),
            local=dict(data.get("local") or {}),
            entity_id=data.get("entity_id"),
            properties=dict(data.get("properties") or {}),
        )


class Mate:
    """A relationship between two assembly nodes."""

    def __init__(
        self,
        mate_type: str,
        node_a: str,
        node_b: str,
        params: dict[str, Any] | None = None,
        mate_id: str | None = None,
    ) -> None:
        """Initialize a mate between two assembly nodes."""
        try:
            self.type = MateType(mate_type.lower())
        except ValueError as exc:
            supported = ", ".join(t.value for t in MateType)
            raise AssemblyError(
                f"Unsupported mate type {mate_type!r}. Supported: {supported}",
                code="unsupported_type",
            ) from exc
        self.id = mate_id or new_mate_id()
        if not node_a or not node_b:
            raise AssemblyError("Mate requires two nodes", code="invalid_arity")
        if node_a == node_b:
            raise AssemblyError("Mate nodes must be distinct", code="duplicate_node")
        self.node_a = node_a
        self.node_b = node_b
        self.params: dict[str, Any] = dict(params or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialize the mate to a JSON-safe dict."""
        return {
            "id": self.id,
            "type": self.type.value,
            "node_a": self.node_a,
            "node_b": self.node_b,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Mate:
        """Reconstruct a mate from a serialized dict."""
        return cls(
            mate_type=str(data["type"]),
            node_a=str(data["node_a"]),
            node_b=str(data["node_b"]),
            params=dict(data.get("params") or {}),
            mate_id=str(data["id"]),
        )


class AssemblyDocument:
    """A hierarchical assembly of parts, sub-assemblies and mates."""

    def __init__(self, name: str | None = None) -> None:
        """Initialize an empty assembly document."""
        self.name = name or "assembly"
        self._nodes: dict[str, AssemblyNode] = {}
        self._children: dict[str, list[str]] = {}  # parent "" = root
        self._mates: dict[str, Mate] = {}

    # ------------------------------------------------------------------
    # Read-only accessors
    # ------------------------------------------------------------------

    @property
    def nodes(self) -> builtins.list[AssemblyNode]:
        """Return all assembly nodes in insertion order."""
        return list(self._nodes.values())

    @property
    def mates(self) -> builtins.list[Mate]:
        """Return all mates in insertion order."""
        return list(self._mates.values())

    # ------------------------------------------------------------------
    # Tree building
    # ------------------------------------------------------------------

    def add_part(
        self,
        name: str,
        local: dict[str, list[float]] | None = None,
        entity_id: str | None = None,
        parent_id: str | None = None,
        node_id: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> str:
        """Add a part to the assembly, returning its node id."""
        if parent_id:
            self._get_node(parent_id)
        node = AssemblyNode(
            node_id or new_node_id("pt"),
            name,
            "part",
            local,
            entity_id,
            properties,
        )
        self._nodes[node.id] = node
        self._children.setdefault(parent_id or "", []).append(node.id)
        return node.id

    def add_subassembly(
        self, name: str, parent_id: str | None = None, node_id: str | None = None
    ) -> str:
        """Add a sub-assembly container, returning its node id."""
        if parent_id:
            self._get_node(parent_id)
        node = AssemblyNode(node_id or new_node_id("asm"), name, "subassembly")
        self._nodes[node.id] = node
        self._children.setdefault(parent_id or "", []).append(node.id)
        return node.id

    def add_mate(
        self,
        mate_type: str,
        node_a: str,
        node_b: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Add a mate between two nodes, returning its mate id."""
        self._get_node(node_a)
        self._get_node(node_b)
        mate = Mate(mate_type, node_a, node_b, params)
        self._mates[mate.id] = mate
        return mate.id

    def get_node(self, node_id: str) -> AssemblyNode:
        """Return an assembly node or raise ``AssemblyError``."""
        return self._get_node(node_id)

    def get_mate(self, mate_id: str) -> Mate:
        """Return a mate or raise ``AssemblyError``."""
        if mate_id not in self._mates:
            raise AssemblyError(f"Mate not found: {mate_id}", code="not_found")
        return self._mates[mate_id]

    def remove_node(self, node_id: str) -> None:
        """Remove a node and its subtree plus any touching mates."""
        self._get_node(node_id)
        removed = self._subtree(node_id)
        for rid in removed:
            self._nodes.pop(rid, None)
            self._children.pop(rid, None)
        for parent, children in list(self._children.items()):
            self._children[parent] = [c for c in children if c not in removed]
        self._remove_mates(removed)

    def remove_mate(self, mate_id: str) -> None:
        """Remove a single mate."""
        if mate_id not in self._mates:
            raise AssemblyError(f"Mate not found: {mate_id}", code="not_found")
        del self._mates[mate_id]

    def _subtree(self, node_id: str) -> set[str]:
        result: set[str] = set()
        stack = [node_id]
        while stack:
            current = stack.pop()
            if current in result:
                continue
            result.add(current)
            stack.extend(self._children.get(current, []))
        return result

    def _parent_map(self) -> dict[str, str]:
        parent_map: dict[str, str] = {}
        for parent, children in self._children.items():
            for child in children:
                if parent == "":
                    parent_map[child] = ""
                else:
                    parent_map[child] = parent
        return parent_map

    def _compose_ancestors(self, node_id: str) -> dict[str, list[float]]:
        parent_map = self._parent_map()
        chain: list[str] = []
        current: str | None = node_id
        while current is not None and current != "":
            chain.append(current)
            current = parent_map.get(current)
        world = identity_transform()
        for entry in reversed(chain):  # root first
            world = _compose(world, self._nodes[entry].local)
        return world

    def _world_transforms(self) -> dict[str, dict[str, list[float]]]:
        return {node_id: self._compose_ancestors(node_id) for node_id in self._nodes}

    def _get_node(self, node_id: str) -> AssemblyNode:
        node = self._nodes.get(node_id)
        if node is None:
            raise AssemblyError(
                f"Assembly node not found: {node_id}", code="node_not_found"
            )
        return node

    def _remove_mates(self, node_ids: set[str]) -> None:
        drop = [
            mid
            for mid, mate in self._mates.items()
            if mate.node_a in node_ids or mate.node_b in node_ids
        ]
        for mid in drop:
            del self._mates[mid]

    # ------------------------------------------------------------------
    # Solving
    # ------------------------------------------------------------------

    def solve(self) -> dict[str, dict[str, list[float]]]:
        """Solve mates and return the world transform of every node.

        Each mate treats ``node_a`` as the anchor and writes ``node_b``'s
        local transform to honour the relationship. Position-preserving
        mates (parallel / perpendicular / angle) keep ``node_b`` where it
        already is; placement mates (coincident / concentric / distance)
        move it relative to the anchor. Returns a mapping of node id to its
        absolute ``{"translation", "euler"}``.
        """
        for mate in self._mates.values():
            anchor = self._compose_ancestors(mate.node_a)
            target = self._nodes[mate.node_b]
            current_translation = target.local["translation"]
            target.local["translation"] = self._mate_translation(
                mate.type.value, anchor["translation"], current_translation, mate.params
            )
            if mate.type.value in (MateType.PARALLEL, MateType.PERPENDICULAR, MateType.ANGLE):
                target.local["euler"] = self._mate_euler(
                    mate.type.value, anchor["euler"], mate.params
                )
        return self._world_transforms()

    def _mate_translation(
        self,
        mate_type: str,
        anchor: list[float],
        current: list[float],
        params: dict[str, Any],
    ) -> list[float]:
        axis = _axis(params.get("axis"))
        if mate_type in ("coincident", "concentric"):
            return list(anchor)
        if mate_type in ("parallel", "perpendicular", "angle"):
            return list(current)
        if mate_type == "distance":
            offset = float(params.get("distance", params.get("offset", 0.0)))
            return _add(anchor, _scale(axis, offset))
        raise AssemblyError(
            f"Unsupported mate type {mate_type!r}", code="unsupported_type"
        )

    def _mate_euler(
        self,
        mate_type: str,
        anchor: list[float],
        params: dict[str, Any],
    ) -> list[float]:
        if mate_type == "angle":
            angle = math.radians(float(params.get("angle", 0.0)))
            return [anchor[0] + angle, anchor[1], anchor[2]]
        if mate_type == "perpendicular":
            return [anchor[0] + math.pi / 2.0, anchor[1], anchor[2]]
        return list(anchor)

    # ------------------------------------------------------------------
    # BOM
    # ------------------------------------------------------------------

    def bom(self) -> builtins.list[dict[str, Any]]:
        """Return a tallied bill of materials.

        Sub-assemblies are expanded; each unique part name is tallied into a
        single row with a ``quantity``. Entity ids are retained.
        """
        counts: dict[str, dict[str, Any]] = {}

        def visit(node_id: str) -> None:
            node = self._nodes[node_id]
            if node.kind == "part":
                entry = counts.get(node.name)
                if entry is None:
                    entry = {"name": node.name, "quantity": 0}
                    if node.entity_id:
                        entry["entity_id"] = node.entity_id
                    counts[node.name] = entry
                entry["quantity"] += 1
            for child in self._children.get(node_id, []):
                visit(child)

        for root in self._children.get("", []):
            visit(root)
        return list(counts.values())

    def bom_csv(self) -> str:
        """Return the BOM as a CSV string."""
        buffer = io.StringIO()
        rows = self.bom()
        writer = csv.DictWriter(buffer, fieldnames=["name", "quantity", "entity_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # Explode
    # ------------------------------------------------------------------

    def explode(
        self,
        spacing: float = 10.0,
        direction: str = "x",
    ) -> builtins.list[dict[str, Any]]:
        """Return radially offset world transforms for an exploded view.

        The ``direction`` is ``x``/``y``/``z``; each level of nesting offsets
        by :param:`spacing`. Mates are ignored - only tree depth matters.
        Returns records with ``node_id``, ``name``, ``depth`` and the
        exploded ``translation``.
        """
        axis = {"x": _X_AXIS, "y": _Y_AXIS, "z": _Z_AXIS}.get(direction, _Z_AXIS)
        output: builtins.list[dict[str, Any]] = []
        root_world = identity_transform()

        def walk(node_id: str, parent_world: dict[str, list[float]], depth: int) -> None:
            node = self._nodes[node_id]
            world = _compose(parent_world, node.local)
            exploded = _add(world["translation"], _scale(axis, float(depth) * spacing))
            output.append(
                {
                    "node_id": node.id,
                    "name": node.name,
                    "depth": depth,
                    "translation": exploded,
                }
            )
            for child in self._children.get(node_id, []):
                walk(child, world, depth + 1)

        for root in self._children.get("", []):
            walk(root, root_world, 1)
        return output

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the assembly document to a JSON-safe dict."""
        return {
            "name": self.name,
            "nodes": [node.to_dict() for node in self._nodes.values()],
            "children": {k: list(v) for k, v in self._children.items()},
            "mates": [mate.to_dict() for mate in self._mates.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssemblyDocument:
        """Reconstruct an assembly document from a serialized dict."""
        doc = cls(name=str(data.get("name", "assembly")))
        for node_data in data.get("nodes", []):
            node = AssemblyNode.from_dict(node_data)
            doc._nodes[node.id] = node
        doc._children = {
            str(k): [str(v) for v in list(val)] for k, val in data.get("children", {}).items()
        }
        for mate_data in data.get("mates", []):
            mate = Mate.from_dict(mate_data)
            doc._mates[mate.id] = mate
        return doc
