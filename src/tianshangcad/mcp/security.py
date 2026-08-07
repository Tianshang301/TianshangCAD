"""MCP tool permission whitelist.

Each tool is mapped to a permission level. Read-only tools are
auto-approved; write tools require confirmation; destructive tools must
always be confirmed; admin tools are reserved for operators.
"""

from enum import Enum


class PermissionLevel(Enum):
    """Permission levels for MCP tools."""

    READ_ONLY = "read_only"
    STANDARD = "standard"
    DESTRUCTIVE = "destructive"
    ADMIN = "admin"


TOOL_PERMISSIONS: dict[str, PermissionLevel] = {
    # Read tools - auto-approved
    "cad_file_list": PermissionLevel.READ_ONLY,
    "cad_object_read": PermissionLevel.READ_ONLY,
    "cad_object_list": PermissionLevel.READ_ONLY,
    "cad_layer_read": PermissionLevel.READ_ONLY,
    "cad_layer_list": PermissionLevel.READ_ONLY,
    "cad_status": PermissionLevel.READ_ONLY,
    "cad_logs": PermissionLevel.READ_ONLY,
    "cad_json": PermissionLevel.READ_ONLY,
    "cad_validate_geometry": PermissionLevel.READ_ONLY,
    "cad_validate_interference": PermissionLevel.READ_ONLY,
    "cad_validate_topology": PermissionLevel.READ_ONLY,
    "cad_metrics_get": PermissionLevel.READ_ONLY,
    "cad_measure_distance": PermissionLevel.READ_ONLY,
    "cad_measure_area": PermissionLevel.READ_ONLY,
    "cad_assembly_bom": PermissionLevel.READ_ONLY,
    "cad_assembly_explode": PermissionLevel.READ_ONLY,
    "cad_drawing_export": PermissionLevel.READ_ONLY,
    "cad_sim_mesh": PermissionLevel.READ_ONLY,
    "cad_sim_result": PermissionLevel.READ_ONLY,
    "cad_sim_list": PermissionLevel.READ_ONLY,
    "cad_collab_history": PermissionLevel.READ_ONLY,
    "cad_collab_permission": PermissionLevel.STANDARD,
    "cad_collab_presence": PermissionLevel.STANDARD,
    "cad_batch": PermissionLevel.ADMIN,
    "cad_version": PermissionLevel.STANDARD,
    "cad_nlp_command": PermissionLevel.READ_ONLY,
    "cad_nlp_chat": PermissionLevel.STANDARD,
    "cad_render": PermissionLevel.READ_ONLY,
    "cad_view_3d_read": PermissionLevel.READ_ONLY,
    "cad_view_3d_list": PermissionLevel.READ_ONLY,
    # Standard write tools - confirmation required
    "cad_view_3d_create": PermissionLevel.STANDARD,
    "cad_view_3d_update": PermissionLevel.STANDARD,
    "cad_file_create": PermissionLevel.STANDARD,
    "cad_file_open": PermissionLevel.STANDARD,
    "cad_file_save": PermissionLevel.STANDARD,
    "cad_file_close": PermissionLevel.STANDARD,
    "cad_file_io": PermissionLevel.STANDARD,
    "cad_object_create": PermissionLevel.STANDARD,
    "cad_object_update": PermissionLevel.STANDARD,
    "cad_object_copy": PermissionLevel.STANDARD,
    "cad_object_transform": PermissionLevel.STANDARD,
    "cad_object_boolean": PermissionLevel.STANDARD,
    "cad_layer_create": PermissionLevel.STANDARD,
    "cad_layer_update": PermissionLevel.STANDARD,
    "cad_variable": PermissionLevel.STANDARD,
    "cad_constraint": PermissionLevel.STANDARD,
    "cad_assembly_create": PermissionLevel.STANDARD,
    "cad_assembly_add_part": PermissionLevel.STANDARD,
    "cad_assembly_add_subasm": PermissionLevel.STANDARD,
    "cad_assembly_add_mate": PermissionLevel.STANDARD,
    "cad_assembly_remove_part": PermissionLevel.DESTRUCTIVE,
    "cad_assembly_solve": PermissionLevel.STANDARD,
    "cad_drawing_create": PermissionLevel.STANDARD,
    "cad_drawing_add_view": PermissionLevel.STANDARD,
    "cad_drawing_add_section": PermissionLevel.STANDARD,
    "cad_drawing_add_dimension": PermissionLevel.STANDARD,
    "cad_drawing_add_tolerance": PermissionLevel.STANDARD,
    "cad_drawing_delete": PermissionLevel.DESTRUCTIVE,
    "cad_feature_sweep": PermissionLevel.STANDARD,
    "cad_feature_loft": PermissionLevel.STANDARD,
    "cad_feature_fillet": PermissionLevel.STANDARD,
    "cad_feature_chamfer": PermissionLevel.STANDARD,
    "cad_feature_pattern_linear": PermissionLevel.STANDARD,
    "cad_feature_pattern_circular": PermissionLevel.STANDARD,
    "cad_feature_pattern_mirror": PermissionLevel.STANDARD,
    "cad_sim_setup": PermissionLevel.STANDARD,
    "cad_sim_run": PermissionLevel.STANDARD,
    "cad_sim_delete": PermissionLevel.DESTRUCTIVE,
    "cad_collab_session": PermissionLevel.STANDARD,
    "cad_collab_branch": PermissionLevel.STANDARD,
    "cad_collab_annotation": PermissionLevel.STANDARD,
    "cad_collab_resolve": PermissionLevel.STANDARD,
    "cad_collab_sync": PermissionLevel.STANDARD,
    # Destructive tools - must confirm
    "cad_file_delete": PermissionLevel.DESTRUCTIVE,
    "cad_object_delete": PermissionLevel.DESTRUCTIVE,
    "cad_layer_delete": PermissionLevel.DESTRUCTIVE,
    "cad_view_3d_delete": PermissionLevel.DESTRUCTIVE,
    # Admin tools
}


def check_permission(tool_name: str, auto_approve: set[str]) -> bool:
    """Return whether ``tool_name`` may auto-execute.

    Tools are allowed when they are listed in ``auto_approve`` or when
    their permission level is read-only. Unknown tools default to
    ``STANDARD`` (i.e. confirmation required).
    """
    if tool_name in auto_approve:
        return True
    level = TOOL_PERMISSIONS.get(tool_name, PermissionLevel.STANDARD)
    return level == PermissionLevel.READ_ONLY
