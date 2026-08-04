"""Real-time collaboration: CRDT sessions, branches, annotations, RBAC.

Phase 9 (v0.9.0) Task A builds collaborative document editing on top of the
Spike 3 LWW-Map CRDT (``core.backends.crdt``). A :class:`CollabSession`
holds a shared CRDT state (geometry / layers / variables / constraints /
assembly as keyed registers), together with membership (RBAC), presence,
document branches (fork / merge / conflict resolution) and annotations.
``CollabManager`` is the singleton registry, and :func:`has_permission`
implements the 4-role x 4-scope authorization matrix.

The optional ``[collab]`` extra adds ``websockets``; the transport helper
lives in ``mcp.transport.run_ws`` and is gated so the default install stays
dependency-free.
"""

from __future__ import annotations

import builtins
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar

from tianshangcad.core.backends.crdt import LWWMap
from tianshangcad.utils.errors import DocumentError


def _now_iso() -> str:
    """Return the current UTC timestamp as ISO-8601."""
    return datetime.now(UTC).isoformat()


def _new_id(prefix: str) -> str:
    """Return a prefixed random identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class CollaborationRole(StrEnum):
    """Permission roles in a collaboration session."""

    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"
    OWNER = "owner"


class ResourceScope(StrEnum):
    """Resource scopes guarded by RBAC."""

    DOCUMENT = "document"
    SCENE = "scene"
    ASSEMBLY = "assembly"
    SETTINGS = "settings"


class CollabAction(StrEnum):
    """Authorizable operations within a scope."""

    READ = "read"
    WRITE = "write"
    MANAGE = "manage"
    DELETE = "delete"


#: Role rank used by the permission matrix.
_ROLE_RANK: dict[CollaborationRole, int] = {
    CollaborationRole.VIEWER: 0,
    CollaborationRole.EDITOR: 1,
    CollaborationRole.ADMIN: 2,
    CollaborationRole.OWNER: 3,
}

_ACTION_NEEDED: dict[ResourceScope, dict[CollabAction, int]] = {
    ResourceScope.DOCUMENT: {
        CollabAction.READ: 0,
        CollabAction.WRITE: 1,
        CollabAction.MANAGE: 2,
        CollabAction.DELETE: 3,
    },
    ResourceScope.SCENE: {
        CollabAction.READ: 0,
        CollabAction.WRITE: 1,
        CollabAction.MANAGE: 2,
        CollabAction.DELETE: 3,
    },
    ResourceScope.ASSEMBLY: {
        CollabAction.READ: 0,
        CollabAction.WRITE: 1,
        CollabAction.MANAGE: 2,
        CollabAction.DELETE: 3,
    },
    ResourceScope.SETTINGS: {
        CollabAction.READ: 0,
        CollabAction.WRITE: 2,
        CollabAction.MANAGE: 3,
        CollabAction.DELETE: 3,
    },
}


def can_act(role: CollaborationRole, scope: ResourceScope, action: CollabAction) -> bool:
    """Return whether ``role`` may perform ``action`` on ``scope``."""
    rank = _ROLE_RANK.get(role, _ROLE_RANK[CollaborationRole.VIEWER])
    need = _ACTION_NEEDED[scope][action]
    return rank >= need


def _resolve_role(role: str | CollaborationRole) -> CollaborationRole:
    try:
        return CollaborationRole(role)
    except ValueError:
        raise DocumentError(
            f"Unknown role '{role}'; expected viewer|editor|admin|owner",
            code="invalid_role",
        ) from None


class CollabSession:
    """An in-memory collaborative editing session over one document."""

    def __init__(
        self,
        session_id: str,
        document_id: str,
        name: str,
        owner: str,
        crdt: LWWMap | None = None,
    ) -> None:
        """Initialize a session with ``owner`` as session owner."""
        self.session_id = session_id
        self.document_id = document_id
        self.name = name
        self.owner = owner
        self.created_at = _now_iso()
        self.crdt = crdt or LWWMap(replica_id=f"session_{session_id}")
        self.members: dict[str, CollaborationRole] = {owner: CollaborationRole.OWNER}
        self.presence: dict[str, dict[str, Any]] = {}
        self.branches: dict[str, dict[str, Any]] = {}
        self.annotations: dict[str, dict[str, Any]] = {}
        self.conflicts: dict[str, dict[str, Any]] = {}
        self.operations: list[dict[str, Any]] = []
        self._op_seq = 0

    # ------------------------------------------------------------------
    # Membership / presence
    # ------------------------------------------------------------------

    def role_of(self, user_id: str) -> CollaborationRole:
        """Return the role of ``user_id`` or raise ``DocumentError``."""
        role = self.members.get(user_id)
        if role is None:
            raise DocumentError(
                f"User '{user_id}' is not a member of session {self.session_id}",
                code="not_a_member",
            )
        return role

    def add_member(self, user_id: str, role: str | CollaborationRole) -> None:
        """Add or update a member with the given role."""
        self.members[user_id] = _resolve_role(role)

    def set_role(self, user_id: str, role: str | CollaborationRole) -> None:
        """Set a member's role (caller must hold manage permission)."""
        self.add_member(user_id, role)

    def set_presence(self, user_id: str, **details: Any) -> None:
        """Record a member's presence heartbeat with a fresh timestamp."""
        entry = dict(self.presence.get(user_id, {}))
        entry.update(details)
        entry["user_id"] = user_id
        entry["last_seen"] = _now_iso()
        self.presence[user_id] = entry
        if user_id not in self.members:
            self.members[user_id] = CollaborationRole.VIEWER

    def member_count(self) -> int:
        """Return the number of members."""
        return len(self.members)

    def require(self, user_id: str, scope: ResourceScope, action: CollabAction) -> None:
        """Raise ``DocumentError`` if ``user_id`` lacks the permission."""
        role = self.role_of(user_id)
        if not can_act(role, scope, action):
            raise DocumentError(
                f"User '{user_id}' (role {role.value}) lacks {action.value} "
                f"permission on {scope.value}",
                code="permission_denied",
            )

    # ------------------------------------------------------------------ #
    # Operations (document / scene / assembly register writes)
    # ------------------------------------------------------------------ #

    def apply_op(
        self, user_id: str, op: dict[str, Any], scope: ResourceScope = ResourceScope.DOCUMENT
    ) -> dict[str, Any]:
        """Apply one CRDT operation after an RBAC write check.

        ``op`` is ``{"key": ..., "value": ...}`` for a write or
        ``{"key": ..., "delete": true}`` for a delete. Returns a record of
        the applied operation.
        """
        self.require(user_id, scope, CollabAction.WRITE)
        key = op.get("key")
        if not key:
            raise DocumentError("Op is missing 'key'", code="invalid_op")
        if op.get("delete"):
            removed = self.crdt.delete(key)
            if not removed:
                raise DocumentError(f"Key not present: {key}", code="key_missing")
        else:
            value = op.get("value")
            if value is None:
                raise DocumentError("Op is missing 'value'", code="invalid_op")
            self.crdt.set(key, value)
        self._op_seq += 1
        record = {
            "seq": self._op_seq,
            "user": user_id,
            "key": key,
            "delete": bool(op.get("delete")),
            "value": None if op.get("delete") else op.get("value"),
            "at": _now_iso(),
        }
        self.operations.append(record)
        return record

    def operations_since(self, after_seq: int) -> list[dict[str, Any]]:
        """Return operations applied after ``after_seq``."""
        return [op for op in self.operations if op["seq"] > after_seq]

    # ------------------------------------------------------------------ #
    # Branches
    # ------------------------------------------------------------------ #

    def fork_branch(self, user_id: str, name: str = "branch") -> dict[str, Any]:
        """Snapshot the current CRDT into a new immutable branch."""
        self.require(user_id, ResourceScope.DOCUMENT, CollabAction.WRITE)
        branch_id = _new_id("br")
        self.branches[branch_id] = {
            "branch_id": branch_id,
            "name": name,
            "created_by": user_id,
            "created_at": _now_iso(),
            "snapshot": self.crdt.snapshot(),
            "operations": [],
        }
        return self.branches[branch_id]

    def edit_branch(
        self, user_id: str, branch_id: str, op: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply an op to a branch's CRDT (independent of the parent)."""
        self.require(user_id, ResourceScope.DOCUMENT, CollabAction.WRITE)
        branch = self.branches.get(branch_id)
        if branch is None:
            raise DocumentError(f"Unknown branch: {branch_id}", code="unknown_branch")
        crdt = LWWMap()
        crdt.load(branch["snapshot"])
        if op.get("delete"):
            crdt.delete(op["key"])
        else:
            crdt.set(op["key"], op["value"])
        branch["snapshot"] = crdt.snapshot()
        record = {
            "user": user_id,
            "key": op["key"],
            "delete": bool(op.get("delete")),
            "at": _now_iso(),
        }
        branch["operations"].append(record)
        return record

    def list_branches(self) -> list[dict[str, Any]]:
        """Return a summary of every branch."""
        return [
            {
                "branch_id": branch["branch_id"],
                "name": branch["name"],
                "created_by": branch["created_by"],
                "created_at": branch["created_at"],
                "operation_count": len(branch["operations"]),
            }
            for branch in self.branches.values()
        ]

    def merge_branch(self, user_id: str, branch_id: str) -> list[dict[str, Any]]:
        """Merge a branch's CRDT into the parent and list conflicts.

        Concurrently-modified keys (a key present in either parent or branch
        with a differing value) are emitted as pending conflicts with a
        stable ``conflict_id``; the LWW merge picks a winner, and
        :meth:`resolve_conflict` records an explicit decision.
        """
        self.require(user_id, ResourceScope.DOCUMENT, CollabAction.MANAGE)
        branch = self.branches.get(branch_id)
        if branch is None:
            raise DocumentError(f"Unknown branch: {branch_id}", code="branch_not_found")
        branch_crdt = LWWMap()
        branch_crdt.load(branch["snapshot"])
        parent_keys: builtins.set[str] = self.crdt.keys()
        branch_keys: builtins.set[str] = branch_crdt.keys()
        conflicts: list[dict[str, Any]] = []

        def _conflict(key: str, ours: Any, theirs: Any) -> None:
            conflict_id = _new_id("cf")
            self.conflicts[conflict_id] = {
                "conflict_id": conflict_id,
                "key": key,
                "ours": ours,
                "theirs": theirs,
                "resolved": False,
                "resolution": None,
            }
            conflicts.append(self.conflicts[conflict_id])

        for key in sorted(parent_keys - branch_keys):
            _conflict(key, self.crdt.get(key), None)
        for key in sorted(branch_keys - parent_keys):
            _conflict(key, None, branch_crdt.get(key))
        for key in sorted(parent_keys & branch_keys):
            ours = self.crdt.get(key)
            theirs = branch_crdt.get(key)
            if ours != theirs:
                _conflict(key, ours, theirs)
        # Bring the branch state in via a convergent CRDT merge.
        branch_crdt.merge(self.crdt)
        self.crdt = branch_crdt
        branch["merged_at"] = _now_iso()
        return conflicts

    # ------------------------------------------------------------------ #
    # Annotations
    # ------------------------------------------------------------------ #

    def add_annotation(
        self, user_id: str, text: str, scope: str = "scene", ref: str | None = None
    ) -> dict[str, Any]:
        """Add an annotation pinned to a ``scope`` (and optional ``ref``)."""
        self.require(user_id, ResourceScope.SCENE, CollabAction.WRITE)
        annotation_id = _new_id("ann")
        self.annotations[annotation_id] = {
            "annotation_id": annotation_id,
            "author": user_id,
            "text": text,
            "scope": scope,
            "ref": ref,
            "created_at": _now_iso(),
            "resolved": False,
        }
        return self.annotations[annotation_id]

    def list_annotations(self) -> list[dict[str, Any]]:
        """Return all annotations, newest first."""
        return sorted(self.annotations.values(), key=lambda a: a["created_at"], reverse=True)

    def close_annotation(self, user_id: str, annotation_id: str) -> dict[str, Any]:
        """Mark an annotation resolved (SCENE manage)."""
        self.require(user_id, ResourceScope.SCENE, CollabAction.MANAGE)
        annotation = self.annotations.get(annotation_id)
        if annotation is None:
            raise DocumentError(f"Unknown annotation: {annotation_id}", code="annotation_not_found")
        annotation["resolved"] = True
        annotation["resolved_by"] = user_id
        annotation["resolved_at"] = _now_iso()
        return annotation

    # ------------------------------------------------------------------ #
    # Conflicts
    # ------------------------------------------------------------------ #

    def pending_conflicts(self) -> list[dict[str, Any]]:
        """Return the unresolved merge conflicts."""
        return [entry for entry in self.conflicts.values() if not entry["resolved"]]

    def resolve_conflict(
        self, user_id: str, conflict_id: str, resolution: str
    ) -> dict[str, Any]:
        """Resolve a merge conflict explicitly (``ours`` / ``theirs`` / ``latest``)."""
        self.require(user_id, ResourceScope.DOCUMENT, CollabAction.MANAGE)
        conflict = self.conflicts.get(conflict_id)
        if conflict is None:
            raise DocumentError(f"Unknown conflict: {conflict_id}", code="conflict_not_found")
        if conflict["resolved"]:
            raise DocumentError(
                f"Conflict already resolved: {conflict_id}", code="already_resolved"
            )
        if resolution not in ("ours", "theirs", "latest"):
            raise DocumentError(
                f"Invalid resolution '{resolution}'; expected ours, theirs or latest",
                code="invalid_resolution",
            )
        if resolution == "ours":
            self.crdt.set(conflict["key"], conflict["ours"])
        elif resolution == "theirs":
            self.crdt.set(conflict["key"], conflict["theirs"])
        # "latest" keeps the CRDT state as merged (LWW already decided).
        conflict["resolved"] = True
        conflict["resolution"] = resolution
        conflict["resolved_by"] = user_id
        return conflict

    # ------------------------------------------------------------------ #
    # Sync snapshot
    # ------------------------------------------------------------------ #

    def state_dict(self) -> dict[str, Any]:
        """Return the live CRDT register map (values only)."""
        return self.crdt.items()

    def crdt_snapshot(self) -> dict[str, Any]:
        """Return the full CRDT snapshot for replication."""
        return self.crdt.snapshot()


class CollabManager:
    """Singleton registry of collaboration sessions."""

    _instance: CollabManager | None = None
    _sessions: ClassVar[builtins.dict[str, CollabSession]] = {}

    def __new__(cls) -> CollabManager:
        """Return the singleton instance, creating it on first use."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create_session(
        self,
        document_id: str,
        name: str = "session",
        owner: str = "owner",
        seed: dict[str, Any] | None = None,
    ) -> CollabSession:
        """Create a collaboration session seeded with ``seed``."""
        session_id = _new_id("collab")
        crdt = LWWMap(replica_id=f"session_{session_id}")
        for key, value in (seed or {}).items():
            crdt.set(key, value)
        session = CollabSession(
            session_id=session_id,
            document_id=document_id,
            name=name,
            owner=owner,
            crdt=crdt,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> CollabSession:
        """Return a session by id or raise ``DocumentError``."""
        session = self._sessions.get(session_id)
        if session is None:
            raise DocumentError(
                f"Unknown collaboration session: {session_id}", code="session_not_found"
            )
        return session

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return a summary of every active session."""
        return [
            {
                "session_id": session.session_id,
                "name": session.name,
                "document_id": session.document_id,
                "owner": session.owner,
                "member_count": session.member_count(),
                "branch_count": len(session.branches),
                "created_at": session.created_at,
            }
            for session in self._sessions.values()
        ]

    def join_session(self, session_id: str, user_id: str) -> CollabSession:
        """Add ``user_id`` as a viewer and record presence."""
        session = self.get_session(session_id)
        session.add_member(user_id, CollaborationRole.VIEWER)
        session.set_presence(user_id, status="online")
        return session

    def close_session(self, session_id: str, user_id: str) -> None:
        """Close a session (owner only) and drop it from the registry."""
        session = self.get_session(session_id)
        session.require(user_id, ResourceScope.SETTINGS, CollabAction.DELETE)
        self._sessions.pop(session_id, None)

    def reset(self) -> None:
        """Drop all sessions (test helper)."""
        self._sessions.clear()


def build_seed(doc: Any) -> dict[str, Any]:
    """Build a CRDT register seed from a document's collections."""
    seed: dict[str, Any] = {}
    for record in doc.entities.list():
        seed[f"entity:{record.id}"] = record.to_dict()
    for layer in doc.layers.list():
        seed[f"layer:{layer.name}"] = layer.to_dict()
    for variable in doc.variables.list():
        seed[f"variable:{variable.name}"] = variable.to_dict()
    for constraint in doc.constraints.list():
        seed[f"constraint:{constraint.id}"] = constraint.to_dict()
    assembly = getattr(doc, "_assembly", None)
    if assembly is not None:
        seed["assembly"] = assembly.to_dict()
    return seed
