"""Natural language command parsing.

``cad_nlp_command`` maps free-form user requests (English or Chinese) to a
CAD MCP tool call. When a request is ambiguous, the tool returns the
candidate intents as suggestions instead of guessing.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

ArgumentBuilder = Callable[[re.Match[str], str], dict[str, Any]]


@dataclass(frozen=True)
class NLPRule:
    """A single natural language intent rule."""

    name: str
    tool: str
    description: str
    regex: re.Pattern[str]
    build: ArgumentBuilder


def _first_float(text: str, default: float = 0.0) -> float:
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if match is None:
        return default
    return float(match.group())


def _delete_object_id(text: str) -> str:
    """Extract the object id referenced after a delete verb."""
    match = re.search(r"obj_[A-Za-z0-9_]+", text)
    if match:
        return match.group(0)
    match = re.search(r"(?:delete|remove|删除|移除)[\s:：]+(\S+)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def _points_of(text: str) -> list[list[float]]:
    """Extract coordinate pairs like ``1,2 3,4`` or ``(1,2)-(3,4)``."""
    pairs = re.findall(r"[-+]?\d*\.?\d+\s*[,，]\s*[-+]?\d*\.?\d+", text)
    points: list[list[float]] = []
    for pair in pairs:
        parts = re.findall(r"[-+]?\d*\.?\d+", pair)
        if len(parts) >= 2:
            points.append([float(parts[0]), float(parts[1]), 0.0])
    return points


_RULES: tuple[NLPRule, ...] = (
    NLPRule(
        name="create_file",
        tool="cad_file_create",
        description="Create a new CAD file (新建文件)",
        regex=re.compile(
            r"^(?:new|create)(?:\s+a)?(?:\s+drawing)?\s+file\s+(?P<name>[^\s]+)"
            r"|^新建(?:文件|图纸)?[：: ]?\s*(?P<name2>[^\s]+)",
            re.IGNORECASE,
        ),
        build=lambda match, text: {"filename": match.group("name") or match.group("name2")},
    ),
    NLPRule(
        name="open_file",
        tool="cad_file_open",
        description="Open an existing CAD file (打开文件)",
        regex=re.compile(
            r"^open\s+(?P<path>\S+)|^打开(?:文件|图纸)?[：: ]?\s*(?P<path2>\S+)",
            re.IGNORECASE,
        ),
        build=lambda match, text: {"path": match.group("path") or match.group("path2")},
    ),
    NLPRule(
        name="draw_line",
        tool="cad_object_create",
        description="Draw a line between two points (画线)",
        regex=re.compile(r"line|线|画线", re.IGNORECASE),
        build=lambda match, text: {
            "type": "line",
            "params": {},
            "layer": "0",
            "_parse": _points_of(text)[:2],
        },
    ),
    NLPRule(
        name="draw_circle",
        tool="cad_object_create",
        description="Draw a circle with a centre and radius (画圆)",
        regex=re.compile(r"circle|圆", re.IGNORECASE),
        build=lambda match, text: {
            "type": "circle",
            "params": {"radius": _first_float(text, 1.0)},
            "layer": "0",
            "_parse": _points_of(text)[:1],
        },
    ),
    NLPRule(
        name="draw_box",
        tool="cad_object_create",
        description="Create a box / cuboid (长方体)",
        regex=re.compile(r"box|cuboid|长方体|立方体", re.IGNORECASE),
        build=lambda match, text: {
            "type": "box",
            "params": {"dimensions": [1.0, 1.0, 1.0]},
            "layer": "0",
            "_parse": _points_of(text)[:1],
        },
    ),
    NLPRule(
        name="delete_object",
        tool="cad_object_delete",
        description="Delete an object (删除对象)",
        regex=re.compile(r"delete|remove|删除|移除", re.IGNORECASE),
        build=lambda match, text: {"object_id": _delete_object_id(text)},
    ),
    NLPRule(
        name="list_objects",
        tool="cad_object_list",
        description="List objects in the document (列出对象)",
        regex=re.compile(
            r"^list (?:all |the )?objects?$|^列出对象|^对象列表|^what objects",
            re.IGNORECASE,
        ),
        build=lambda match, text: {},
    ),
    NLPRule(
        name="measure_distance",
        tool="cad_measure_distance",
        description="Measure distance between two points (测量距离)",
        regex=re.compile(r"distance|measure|距离|测量", re.IGNORECASE),
        build=lambda match, text: {"_parse": _points_of(text)[:2]},
    ),
    NLPRule(
        name="check_status",
        tool="cad_status_health",
        description="Check system health / status (状态)",
        regex=re.compile(
            r"^status$|^check status|^health$|^状态$|^健康检查$|^查看状态",
            re.IGNORECASE,
        ),
        build=lambda match, text: {},
    ),
    NLPRule(
        name="render_view",
        tool="cad_render_view",
        description="Render an orthographic view (渲染视图)",
        regex=re.compile(r"render|渲染|预览", re.IGNORECASE),
        build=lambda match, text: {
            "view": (
                "side"
                if re.search(r"\bside\b|侧", text)
                else ("front" if re.search(r"\bfront\b|前|主视", text) else "top")
            )
        },
    ),
    NLPRule(
        name="save_version",
        tool="cad_version_save",
        description="Save a document version snapshot (保存版本)",
        regex=re.compile(r"save(?: a)? version|保存版本|创建快照", re.IGNORECASE),
        build=lambda match, text: {},
    ),
    NLPRule(
        name="batch_execute",
        tool="cad_batch_execute",
        description="Run a batch of commands (批量执行)",
        regex=re.compile(r"batch|批量|脚本", re.IGNORECASE),
        build=lambda match, text: {"commands": []},
    ),
)


class NLPCommandInput(BaseModel):
    """Input for natural language command parsing."""

    text: str = Field(..., description="Free-form natural language request")
    tool_whitelist: list[str] | None = Field(
        None, description="Restrict matches to these tool names"
    )


class NLPCommandOutput(BaseModel):
    """Output for natural language command parsing."""

    intent: str = Field(..., description="Matched intent name")
    tool: str | None = Field(None, description="Target MCP tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    confidence: float = Field(..., description="Confidence in [0, 1]")
    ambiguous: bool = Field(..., description="Whether multiple intents matched")
    suggestions: list[str] = Field(
        default_factory=list, description="Candidate intent descriptions"
    )
    original_text: str = Field(..., description="The original request text")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _clean_arguments(rule_name: str, arguments: dict[str, Any], text: str) -> dict[str, Any]:
    """Materialize parsed coordinates into concrete arguments."""
    result = dict(arguments)
    parsed = result.pop("_parse", None)
    if result.get("type") == "line" and isinstance(parsed, list) and len(parsed) >= 2:
        result["params"] = {"start": parsed[0], "end": parsed[1]}
    elif result.get("type") == "circle" and isinstance(parsed, list) and parsed:
        result["params"] = {"center": parsed[0], "radius": result["params"]["radius"]}
    elif result.get("type") == "box" and isinstance(parsed, list) and parsed:
        origin = parsed[0]
        if len(origin) < 3:
            origin = [*origin, 0.0]
        result["params"] = {"origin": origin, "dimensions": [1.0, 1.0, 1.0]}
    elif rule_name == "measure_distance" and isinstance(parsed, list):
        result["start"] = parsed[0] if parsed else [0.0, 0.0, 0.0]
        result["end"] = parsed[1] if len(parsed) > 1 else [0.0, 0.0, 0.0]
    return result


def cad_nlp_command(input: NLPCommandInput) -> NLPCommandOutput:
    """Parse a natural language request into a CAD tool call.

    将自然语言请求解析为 CAD 工具调用。Supports 12 intent patterns in English
    and Chinese. Ambiguous requests are reported with candidate suggestions
    rather than an arbitrary guess.
    """
    text = input.text.strip()
    whitelist = set(input.tool_whitelist or [])
    matches: list[tuple[NLPRule, re.Match[str]]] = []
    for rule in _RULES:
        if whitelist and rule.tool not in whitelist:
            continue
        search = rule.regex.search(text)
        if search is not None:
            matches.append((rule, search))

    if not matches:
        return NLPCommandOutput(
            intent="unknown",
            tool=None,
            arguments={},
            confidence=0.0,
            ambiguous=False,
            suggestions=[],
            original_text=text,
            status="error",
            message="No matching intent found",
        )

    if len(matches) > 1:
        return NLPCommandOutput(
            intent="ambiguous",
            tool=None,
            arguments={},
            confidence=0.5,
            ambiguous=True,
            suggestions=[rule.description for rule, _ in matches],
            original_text=text,
            status="error",
            message=f"{len(matches)} possible intents; please clarify",
        )

    rule, search = matches[0]
    try:
        raw = rule.build(search, text)
    except Exception:  # pragma: no cover - defensive
        raw = {}
    arguments = _clean_arguments(rule.name, raw, text)
    return NLPCommandOutput(
        intent=rule.name,
        tool=rule.tool,
        arguments=arguments,
        confidence=0.9,
        ambiguous=False,
        suggestions=[rule.description],
        original_text=text,
        status="success",
        message=f"Parsed intent {rule.name}",
    )


TOOLS: list[tuple[str, Any]] = [
    ("cad_nlp_command", cad_nlp_command),
]
