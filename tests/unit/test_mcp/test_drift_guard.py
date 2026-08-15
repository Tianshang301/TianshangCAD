"""Drift guard for the machine-consumed tool references.

The v0.12.0 aggregate-tool consolidation (77 -> 19 tools) removed dozens of
granular names (``cad_file_save``, ``cad_logs``, ``cad_json_load``, ...). The
batch templates and ``config/mcp.json`` ship as package data and are consumed
by clients, so a future rename/merge must not leave them dangling. These tests
lock every ``tool`` name in those artifacts to the live registry and validate
each command's ``arguments`` against the tool's Pydantic input model.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, get_type_hints

from pydantic import BaseModel

from tianshangcad.core.batch_templates import list_templates, render_template
from tianshangcad.mcp.tools._registry import get_registry

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MCP_CONFIG = _REPO_ROOT / "src" / "tianshangcad" / "config" / "mcp.json"
_GROUND_TRUTH = _REPO_ROOT / "datasets" / "cadgenbench" / "ground_truth.json"


def _tool_input_model(fn: Any) -> type[BaseModel]:
    """Return the single Pydantic input model of a registered tool."""
    parameters = list(inspect.signature(fn).parameters.values())
    assert len(parameters) == 1, f"expected single-parameter tool, got: {parameters}"
    model = get_type_hints(fn)[parameters[0].name]
    assert isinstance(model, type) and issubclass(model, BaseModel), (
        f"tool input is not a Pydantic model: {model!r}"
    )
    return model


def test_templates_only_reference_registered_tools() -> None:
    """Every rendered template command names a registered tool with valid args."""
    registry = get_registry()
    for name in list_templates():
        for command in render_template(name):
            tool = command["tool"]
            assert tool in registry, f"template '{name}' references unknown tool '{tool}'"
            # Constructing the input model validates the arguments shape, so a
            # template using an old flat/nested key scheme fails here.
            _tool_input_model(registry[tool])(**command["arguments"])


def test_mcp_config_auto_approve_is_registered() -> None:
    """``config/mcp.json`` autoApprove names must all exist in the registry."""
    registry = get_registry()
    data = json.loads(_MCP_CONFIG.read_text(encoding="utf-8"))
    for server in data.get("mcpServers", {}).values():
        for tool in server.get("autoApprove", []):
            assert tool in registry, f"autoApprove references unknown tool '{tool}'"


def test_cadgenbench_ground_truth_references_registered_tools() -> None:
    """Every CADGenBench ground-truth step names a registered tool with valid args."""
    registry = get_registry()
    data = json.loads(_GROUND_TRUTH.read_text(encoding="utf-8"))
    for fixture_id, steps in data.get("ground_truth", {}).items():
        for step in steps:
            tool = step["tool"]
            assert tool in registry, (
                f"fixture '{fixture_id}' references unknown tool '{tool}'"
            )
            # Sentinel ids (__0__, __1__) are plain strings and must still
            # validate against the aggregate input model.
            _tool_input_model(registry[tool])(**step["args"])
