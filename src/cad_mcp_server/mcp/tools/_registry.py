"""Central tool registry built from the per-module ``TOOLS`` lists."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def get_registry() -> dict[str, Callable[..., Any]]:
    """Build and return the mapping of tool name to callable.

    Imports are deferred to avoid circular imports between this module and
    the tool modules that depend on it (e.g. ``batch``).
    """
    from cad_mcp_server.mcp.tools import batch, crud, json_ops, status, validate

    tools: list[tuple[str, Any]] = []
    for module in (crud, json_ops, status, validate, batch):
        tools.extend(module.TOOLS)
    return dict(tools)
