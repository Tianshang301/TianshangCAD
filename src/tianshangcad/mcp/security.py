"""MCP tool permission whitelist.

Each registered tool is an aggregate of the form ``cad_<domain>`` whose
``action`` (or ``tool`` / ``target``) discriminator selects a sub-operation.
``ACTION_PERMISSIONS`` maps each aggregate to the permission level of every
sub-operation; ``TOOL_PERMISSIONS`` holds a single level for aggregates that
are uniform (read-only aggregates, batch, etc.).

Read-only sub-actions are auto-approved; write sub-actions require
confirmation; destructive sub-actions must always be confirmed; admin
sub-actions are reserved for operators.
"""

from __future__ import annotations

from enum import Enum


class PermissionLevel(Enum):
    """Permission levels for MCP tools."""

    READ_ONLY = "read_only"
    STANDARD = "standard"
    DESTRUCTIVE = "destructive"
    ADMIN = "admin"


#: Uniform-level aggregates (all sub-actions share the same level).
TOOL_PERMISSIONS: dict[str, PermissionLevel] = {
    "cad_json": PermissionLevel.READ_ONLY,
    "cad_render": PermissionLevel.READ_ONLY,
    "cad_measure": PermissionLevel.READ_ONLY,
    "cad_validate": PermissionLevel.READ_ONLY,
    "cad_variable": PermissionLevel.STANDARD,
    "cad_version": PermissionLevel.STANDARD,
    "cad_constraint": PermissionLevel.STANDARD,
    "cad_batch": PermissionLevel.ADMIN,
}

#: Per-sub-action permission levels for mixed aggregates.
ACTION_PERMISSIONS: dict[str, dict[str, PermissionLevel]] = {
    "cad_file": {
        "create": PermissionLevel.STANDARD,
        "open": PermissionLevel.STANDARD,
        "save": PermissionLevel.STANDARD,
        "close": PermissionLevel.STANDARD,
        "delete": PermissionLevel.DESTRUCTIVE,
        "list": PermissionLevel.READ_ONLY,
        "import": PermissionLevel.STANDARD,
        "export": PermissionLevel.READ_ONLY,
    },
    "cad_object": {
        "create": PermissionLevel.STANDARD,
        "read": PermissionLevel.READ_ONLY,
        "update": PermissionLevel.STANDARD,
        "delete": PermissionLevel.DESTRUCTIVE,
        "copy": PermissionLevel.STANDARD,
        "transform": PermissionLevel.STANDARD,
        "list": PermissionLevel.READ_ONLY,
        "boolean": PermissionLevel.STANDARD,
    },
    "cad_layer": {
        "create": PermissionLevel.STANDARD,
        "read": PermissionLevel.READ_ONLY,
        "update": PermissionLevel.STANDARD,
        "delete": PermissionLevel.DESTRUCTIVE,
        "list": PermissionLevel.READ_ONLY,
    },
    "cad_view": {
        "create": PermissionLevel.STANDARD,
        "read": PermissionLevel.READ_ONLY,
        "list": PermissionLevel.READ_ONLY,
        "update": PermissionLevel.STANDARD,
        "delete": PermissionLevel.DESTRUCTIVE,
    },
    "cad_nlp": {
        "command": PermissionLevel.READ_ONLY,
        "chat": PermissionLevel.STANDARD,
    },
    "cad_assembly": {
        "create": PermissionLevel.STANDARD,
        "add_part": PermissionLevel.STANDARD,
        "add_subasm": PermissionLevel.STANDARD,
        "add_mate": PermissionLevel.STANDARD,
        "remove_part": PermissionLevel.DESTRUCTIVE,
        "solve": PermissionLevel.STANDARD,
        "bom": PermissionLevel.READ_ONLY,
        "explode": PermissionLevel.READ_ONLY,
    },
    "cad_drawing": {
        "create": PermissionLevel.STANDARD,
        "add_view": PermissionLevel.STANDARD,
        "add_section": PermissionLevel.STANDARD,
        "add_dimension": PermissionLevel.STANDARD,
        "add_tolerance": PermissionLevel.STANDARD,
        "delete": PermissionLevel.DESTRUCTIVE,
        "export": PermissionLevel.READ_ONLY,
    },
    "cad_feature": {
        "sweep": PermissionLevel.STANDARD,
        "loft": PermissionLevel.STANDARD,
        "fillet": PermissionLevel.STANDARD,
        "chamfer": PermissionLevel.STANDARD,
        "pattern_linear": PermissionLevel.STANDARD,
        "pattern_circular": PermissionLevel.STANDARD,
        "pattern_mirror": PermissionLevel.STANDARD,
    },
    "cad_sim": {
        "mesh": PermissionLevel.READ_ONLY,
        "setup": PermissionLevel.STANDARD,
        "run": PermissionLevel.STANDARD,
        "result": PermissionLevel.READ_ONLY,
        "list": PermissionLevel.READ_ONLY,
        "delete": PermissionLevel.DESTRUCTIVE,
    },
    "cad_collab": {
        "session": PermissionLevel.STANDARD,
        "branch": PermissionLevel.STANDARD,
        "annotation": PermissionLevel.STANDARD,
        "presence": PermissionLevel.STANDARD,
        "history": PermissionLevel.READ_ONLY,
        "resolve": PermissionLevel.STANDARD,
        "permission": PermissionLevel.STANDARD,
        "sync": PermissionLevel.STANDARD,
    },
    "cad_status": {
        "check": PermissionLevel.READ_ONLY,
        "file": PermissionLevel.READ_ONLY,
        "object": PermissionLevel.READ_ONLY,
        "layer": PermissionLevel.READ_ONLY,
        "health": PermissionLevel.READ_ONLY,
        "logs_get": PermissionLevel.READ_ONLY,
        "logs_clear": PermissionLevel.DESTRUCTIVE,
    },
}


def levels_for(tool_name: str) -> set[PermissionLevel]:
    """Return the set of permission levels the tool may exercise.

    Aggregates with a per-action table return every distinct level used by
    their sub-actions; uniform aggregates return their single level. Unknown
    tools default to ``STANDARD``.
    """
    actions = ACTION_PERMISSIONS.get(tool_name)
    if actions:
        return set(actions.values())
    return {TOOL_PERMISSIONS.get(tool_name, PermissionLevel.STANDARD)}


def is_read_only(tool_name: str) -> bool:
    """Return whether every sub-action of the tool is read-only."""
    return levels_for(tool_name) == {PermissionLevel.READ_ONLY}


def is_destructive(tool_name: str) -> bool:
    """Return whether any sub-action of the tool is destructive."""
    return PermissionLevel.DESTRUCTIVE in levels_for(tool_name)


def check_permission(tool_name: str, auto_approve: set[str]) -> bool:
    """Return whether ``tool_name`` may auto-execute.

    Tools are allowed when they are listed in ``auto_approve`` or when
    every sub-action is read-only. Unknown tools default to
    ``STANDARD`` (i.e. confirmation required).
    """
    if tool_name in auto_approve:
        return True
    return is_read_only(tool_name)
