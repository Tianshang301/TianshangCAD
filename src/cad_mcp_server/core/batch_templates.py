"""Jinja2 rendering of batch command templates.

Templates live in ``src/cad_mcp_server/templates/`` and produce a JSON array
of ``{"tool": ..., "arguments": {...}}`` command dicts that can be scheduled
or executed directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError

from cad_mcp_server.utils.errors import SchedulerError

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=False,  # noqa: S701 - templates render JSON command data, not HTML
    trim_blocks=True,
    lstrip_blocks=True,
)


def list_templates() -> list[str]:
    """Return the names of all available batch templates."""
    return sorted(
        name.rsplit(".j2", 1)[0] for name in _env.list_templates() if name.endswith(".j2")
    )


def render_template(name: str, variables: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Render template ``name`` and return the list of command dicts."""
    template_name = name if name.endswith(".j2") else f"{name}.j2"
    try:
        template = _env.get_template(template_name)
        text = template.render(**(variables or {}))
    except (TemplateError, OSError) as exc:
        raise SchedulerError(f"Failed to render template '{name}': {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchedulerError(f"Template '{name}' did not produce valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise SchedulerError(f"Template '{name}' must render a JSON array of commands")
    return data
