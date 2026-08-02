"""Central tool registry built from the per-module ``TOOLS`` lists."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def get_registry() -> dict[str, Callable[..., Any]]:
    """Build and return the mapping of tool name to callable.

    Imports are deferred to avoid circular imports between this module and
    the tool modules that depend on it (e.g. ``batch``).
    """
    from cad_mcp_server.mcp.tools import (
        batch,
        boolean,
        crud,
        file_io,
        json_ops,
        nlp,
        render,
        status,
        validate,
        versioning,
        view3d,
    )

    tools: list[tuple[str, Any]] = []
    for module in (
        crud,
        json_ops,
        status,
        validate,
        batch,
        render,
        versioning,
        nlp,
        view3d,
        boolean,
        file_io,
    ):
        tools.extend(module.TOOLS)
    return dict(tools)
