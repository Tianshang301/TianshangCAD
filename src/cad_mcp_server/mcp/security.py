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
    "cad_file_info": PermissionLevel.READ_ONLY,
    "cad_object_read": PermissionLevel.READ_ONLY,
    "cad_object_list": PermissionLevel.READ_ONLY,
    "cad_layer_read": PermissionLevel.READ_ONLY,
    "cad_layer_list": PermissionLevel.READ_ONLY,
    "cad_status_check": PermissionLevel.READ_ONLY,
    "cad_status_file": PermissionLevel.READ_ONLY,
    "cad_status_object": PermissionLevel.READ_ONLY,
    "cad_status_layer": PermissionLevel.READ_ONLY,
    "cad_status_health": PermissionLevel.READ_ONLY,
    "cad_logs_get": PermissionLevel.READ_ONLY,
    "cad_json_load": PermissionLevel.READ_ONLY,
    "cad_json_parse": PermissionLevel.READ_ONLY,
    "cad_json_validate": PermissionLevel.READ_ONLY,
    "cad_json_export_geometry": PermissionLevel.READ_ONLY,
    "cad_json_export_scene": PermissionLevel.READ_ONLY,
    "cad_validate_geometry": PermissionLevel.READ_ONLY,
    "cad_validate_interference": PermissionLevel.READ_ONLY,
    "cad_validate_topology": PermissionLevel.READ_ONLY,
    "cad_metrics_get": PermissionLevel.READ_ONLY,
    "cad_variable_list": PermissionLevel.READ_ONLY,
    "cad_constraint_list": PermissionLevel.READ_ONLY,
    "cad_assembly_bom": PermissionLevel.READ_ONLY,
    "cad_assembly_explode": PermissionLevel.READ_ONLY,
    "cad_drawing_export": PermissionLevel.READ_ONLY,
    "cad_batch_templates": PermissionLevel.READ_ONLY,
    "cad_version_list": PermissionLevel.READ_ONLY,
    "cad_version_diff": PermissionLevel.READ_ONLY,
    "cad_nlp_command": PermissionLevel.READ_ONLY,
    "cad_nlp_chat": PermissionLevel.STANDARD,
    "cad_render_view": PermissionLevel.READ_ONLY,
    "cad_view_3d_read": PermissionLevel.READ_ONLY,
    "cad_view_3d_list": PermissionLevel.READ_ONLY,
    "cad_view_3d_render": PermissionLevel.READ_ONLY,
    "cad_view_section": PermissionLevel.READ_ONLY,
    "cad_view_explode": PermissionLevel.READ_ONLY,
    "cad_view_animation": PermissionLevel.READ_ONLY,
    "cad_webgl_sync": PermissionLevel.READ_ONLY,
    # Standard write tools - confirmation required
    "cad_view_3d_create": PermissionLevel.STANDARD,
    "cad_view_3d_update": PermissionLevel.STANDARD,
    "cad_file_create": PermissionLevel.STANDARD,
    "cad_file_open": PermissionLevel.STANDARD,
    "cad_file_save": PermissionLevel.STANDARD,
    "cad_file_close": PermissionLevel.STANDARD,
    "cad_file_export": PermissionLevel.STANDARD,
    "cad_file_import": PermissionLevel.STANDARD,
    "cad_object_create": PermissionLevel.STANDARD,
    "cad_object_update": PermissionLevel.STANDARD,
    "cad_object_copy": PermissionLevel.STANDARD,
    "cad_object_transform": PermissionLevel.STANDARD,
    "cad_boolean_union": PermissionLevel.STANDARD,
    "cad_boolean_subtract": PermissionLevel.STANDARD,
    "cad_boolean_intersect": PermissionLevel.STANDARD,
    "cad_object_boolean": PermissionLevel.STANDARD,
    "cad_layer_create": PermissionLevel.STANDARD,
    "cad_layer_update": PermissionLevel.STANDARD,
    "cad_json_import_geometry": PermissionLevel.STANDARD,
    "cad_json_import_scene": PermissionLevel.STANDARD,
    "cad_json_import_params": PermissionLevel.STANDARD,
    "cad_json_save": PermissionLevel.STANDARD,
    "cad_variable_set": PermissionLevel.STANDARD,
    "cad_constraint_add": PermissionLevel.STANDARD,
    "cad_constraint_remove": PermissionLevel.STANDARD,
    "cad_constraint_solve": PermissionLevel.STANDARD,
    "cad_assembly_create": PermissionLevel.STANDARD,
    "cad_assembly_add_part": PermissionLevel.STANDARD,
    "cad_assembly_add_subasm": PermissionLevel.STANDARD,
    "cad_assembly_add_mate": PermissionLevel.STANDARD,
    "cad_assembly_solve": PermissionLevel.STANDARD,
    "cad_drawing_create": PermissionLevel.STANDARD,
    "cad_drawing_add_view": PermissionLevel.STANDARD,
    "cad_drawing_add_section": PermissionLevel.STANDARD,
    "cad_drawing_add_dimension": PermissionLevel.STANDARD,
    "cad_drawing_add_tolerance": PermissionLevel.STANDARD,
    "cad_batch_execute": PermissionLevel.STANDARD,
    "cad_batch_run_script": PermissionLevel.STANDARD,
    # Destructive tools - must confirm
    "cad_file_delete": PermissionLevel.DESTRUCTIVE,
    "cad_object_delete": PermissionLevel.DESTRUCTIVE,
    "cad_layer_delete": PermissionLevel.DESTRUCTIVE,
    "cad_batch_cancel": PermissionLevel.DESTRUCTIVE,
    "cad_logs_clear": PermissionLevel.DESTRUCTIVE,
    "cad_view_3d_delete": PermissionLevel.DESTRUCTIVE,
    # Admin tools
    "cad_batch_schedule": PermissionLevel.ADMIN,
    "cad_version_save": PermissionLevel.ADMIN,
    "cad_version_restore": PermissionLevel.ADMIN,
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
