"""Natural language command parsing.

``cad_nlp_command`` maps free-form user requests (English or Chinese) to a
CAD MCP tool call. When a request is ambiguous, the tool returns the
candidate intents as suggestions instead of guessing.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
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


def _radius_of(text: str, default: float = 1.0) -> float:
    """Extract a radius following 'radius' / '半径'."""
    match = re.search(
        r"(?:radius|r)\s*[:=：]?\s*([-+]?\d*\.?\d+)|半径\s*[:=：]?\s*([-+]?\d*\.?\d+)",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return default
    value = match.group(1) or match.group(2)
    return float(value)


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
        regex=re.compile(
            r"(?:draw|make|create|add)\s*(?:a\s+|an\s+)?line|画(?:一条|一根)?线",
            re.IGNORECASE,
        ),
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
        regex=re.compile(
            r"(?:draw|make|create|add)\s*(?:a\s+|an\s+)?circle|画(?:个|一个)?圆",
            re.IGNORECASE,
        ),
        build=lambda match, text: {
            "type": "circle",
            "params": {"radius": _radius_of(text)},
            "layer": "0",
            "_parse": _points_of(text)[:1],
        },
    ),
    NLPRule(
        name="draw_box",
        tool="cad_object_create",
        description="Create a box / cuboid (长方体)",
        regex=re.compile(
            r"(?:draw|make|create|add)\s*(?:a\s+|an\s+)?(?:box|cuboid)|画(?:个|个)?(?:长方体|立方体)",
            re.IGNORECASE,
        ),
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
        name="move_object",
        tool="cad_object_update",
        description="Move an object to a new location (移动对象)",
        regex=re.compile(r"\bmove\b|移动|平移|搬到|挪到|移到", re.IGNORECASE),
        build=lambda match, text: {"_target": _points_of(text)[:1]},
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
        tool="cad_status",
        description="Check system health / status (状态)",
        regex=re.compile(
            r"^status$|^check status|^health$|^状态$|^健康检查$|^查看状态",
            re.IGNORECASE,
        ),
        build=lambda match, text: {"status": {"target": "health"}},
    ),
    NLPRule(
        name="render_view",
        tool="cad_render",
        description="Render an orthographic view (渲染视图)",
        regex=re.compile(r"render|渲染|预览", re.IGNORECASE),
        build=lambda match, text: {
            "render": {
                "mode": "ortho",
                "view": (
                    "side"
                    if re.search(r"\bside\b|侧", text)
                    else ("front" if re.search(r"\bfront\b|前|主视", text) else "top")
                ),
            }
        },
    ),
    NLPRule(
        name="save_version",
        tool="cad_version",
        description="Save a document version snapshot (保存版本)",
        regex=re.compile(r"save(?: a)? version|保存版本|创建快照", re.IGNORECASE),
        build=lambda match, text: {"version": {"action": "save"}},
    ),
    NLPRule(
        name="batch_execute",
        tool="cad_batch",
        description="Run a batch of commands (批量执行)",
        regex=re.compile(r"batch|批量|脚本", re.IGNORECASE),
        build=lambda match, text: {"batch": {"action": "execute", "commands": []}},
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
    target = result.pop("_target", None)
    if result.get("type") == "line" and isinstance(parsed, list) and len(parsed) >= 2:
        result["params"] = {"start": parsed[0], "end": parsed[1]}
    elif result.get("type") == "circle" and isinstance(parsed, list) and parsed:
        result["params"] = {"center": parsed[0], "radius": result["params"]["radius"]}
    elif result.get("type") == "box" and isinstance(parsed, list) and parsed:
        origin = parsed[0]
        if len(origin) < 3:
            origin = [*origin, 0.0]
        result["params"] = {"origin": origin, "dimensions": [1.0, 1.0, 1.0]}
    elif result.get("type") == "box":
        result["params"] = {"origin": [0.0, 0.0, 0.0], "dimensions": [1.0, 1.0, 1.0]}
    elif rule_name == "measure_distance" and isinstance(parsed, list):
        result["start"] = parsed[0] if parsed else [0.0, 0.0, 0.0]
        result["end"] = parsed[1] if len(parsed) > 1 else [0.0, 0.0, 0.0]
    elif rule_name == "move_object" and isinstance(target, list) and target:
        result["to"] = target[0]
    return result


# ---------------------------------------------------------------------------
# Multi-turn dialogue state (anaphora resolution)
# ---------------------------------------------------------------------------

#: Object-type anchors used to translate a moved entity to a new point.
_MOVE_ANCHOR: dict[str, str] = {
    "circle": "center",
    "rectangle": "origin",
    "box": "origin",
    "cylinder": "origin",
    "sphere": "center",
    "cone": "origin",
}

#: Words that refer back to a previously created object.
_ANAPHORA_RE = re.compile(
    r"\b(it|that|this)\b|the (?:last )?(?:circle|line|box|cuboid|rectangle|"
    r"polygon|polyline|sphere|cylinder|cone)(?: I (?:just )?(?:drew|created|made))?|"
    r"刚画的|刚刚画的|那个|这个|它",
    re.IGNORECASE,
)


@dataclass
class ChatState:
    """Per-session dialogue state for the chat tool."""

    session_id: str
    last_object_id: str | None = None
    last_object_type: str | None = None
    last_intent: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def record(self, text: str, intent: str, tool: str | None, arguments: dict[str, Any]) -> None:
        """Append a turn to the dialogue history."""
        self.last_intent = intent
        self.history.append(
            {
                "text": text,
                "intent": intent,
                "tool": tool,
                "arguments": dict(arguments),
            }
        )


#: In-memory session store keyed by ``session_id``.
_CHAT_SESSIONS: dict[str, ChatState] = {}


def get_chat_session(session_id: str | None = None) -> ChatState:
    """Return (creating if needed) the dialogue state for ``session_id``."""
    key = session_id or "default"
    if key not in _CHAT_SESSIONS:
        _CHAT_SESSIONS[key] = ChatState(session_id=key)
    return _CHAT_SESSIONS[key]


def clear_chat_session(session_id: str | None = None) -> None:
    """Drop the dialogue state for ``session_id`` (or all sessions)."""
    if session_id is None:
        _CHAT_SESSIONS.clear()
    else:
        _CHAT_SESSIONS.pop(session_id, None)


def _anaphora_type(text: str) -> str | None:
    """Extract the object type an anaphora refers to, if stated explicitly."""
    type_match = re.search(
        r"(?:the (?:last )?|刚画的|刚刚画的)(?:a |an |one )?"
        r"(circle|line|box|cuboid|rectangle|polygon|polyline|sphere|cylinder|cone)",
        text,
        re.IGNORECASE,
    )
    if type_match is None:
        return None
    alias = {"cuboid": "box"}
    return alias.get(type_match.group(1), type_match.group(1))


def _resolve_anaphora(text: str, state: ChatState) -> str | None:
    """Return the ``object_id`` a pronominal reference resolves to.

    Returns ``None`` when the text contains no anaphora, when no object has
    been created yet in this session, or when the referenced type does not
    match the last created object.
    """
    if _ANAPHORA_RE.search(text) is None:
        return None
    if state.last_object_id is None:
        return None
    expected = _anaphora_type(text)
    if expected is not None and state.last_object_type != expected:
        return None
    return state.last_object_id


def _move_params(entity_type: str, params: dict[str, Any], target: list[float]) -> dict[str, Any]:
    """Build update ``params`` moving ``entity_type`` so its anchor lands at ``target``."""
    target3 = _ensure_dims(target)
    if entity_type == "line":
        start = params.get("start")
        end = params.get("end")
        if not isinstance(start, list) or not isinstance(end, list):
            return {}
        delta = [target3[i] - start[i] for i in range(3)]
        return {"start": target3, "end": [end[0] + delta[0], end[1] + delta[1], end[2] + delta[2]]}
    anchor = _MOVE_ANCHOR.get(entity_type)
    if anchor is None:
        return {}
    new_params = dict(params)
    new_params[anchor] = target3
    return new_params


def _ensure_dims(point: list[float]) -> list[float]:
    """Pad a 2D point to 3D (z=0)."""
    if len(point) >= 3:
        return [point[0], point[1], point[2]]
    return [point[0], point[1], 0.0]


class ChatInput(BaseModel):
    """Input for the multi-turn natural language chat tool."""

    text: str = Field(..., description="Free-form user message")
    session_id: str = Field("default", description="Conversation session id")
    tool_whitelist: list[str] | None = Field(
        None, description="Restrict matched intents to these tool names"
    )


class ChatOutput(BaseModel):
    """Output for the multi-turn natural language chat tool."""

    session_id: str = Field(..., description="Conversation session id")
    turn: int = Field(..., description="1-based turn number within the session")
    intent: str = Field(..., description="Resolved intent name")
    tool: str | None = Field(None, description="Target MCP tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    object_id: str | None = Field(None, description="Object id referenced or created")
    resolved: bool = Field(False, description="Whether an anaphora was resolved")
    confidence: float = Field(..., description="Confidence in [0, 1]")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")
    history_length: int = Field(..., description="Number of recorded turns")


def cad_nlp_chat(input: ChatInput) -> ChatOutput:
    """Resolve a multi-turn request with anaphora support.

    支持多轮对话中的指代消解，例如先「画一个圆」再「把它移到 5,5」，
    「它」会解析为会话中最后一次创建的圆。Also supports explicit references
    like "the circle I just drew" / 「刚画的圆」. Create intents are executed
    against the current document so later turns can refer to the real object id.
    """
    text = input.text.strip()
    state = get_chat_session(input.session_id)
    turn = len(state.history) + 1

    parsed = cad_nlp_command(
        NLPCommandInput(text=text, tool_whitelist=input.tool_whitelist)
    )
    if parsed.status != "success":
        state.record(text, parsed.intent, parsed.tool, parsed.arguments)
        return ChatOutput(
            session_id=state.session_id,
            turn=turn,
            intent=parsed.intent,
            tool=parsed.tool,
            arguments=parsed.arguments,
            object_id=state.last_object_id,
            resolved=False,
            confidence=parsed.confidence,
            status=parsed.status,
            message=parsed.message,
            history_length=len(state.history),
        )

    arguments = dict(parsed.arguments)
    object_id: str | None = None
    resolved = False

    if parsed.intent in ("draw_line", "draw_circle", "draw_box"):
        created = _execute_create(arguments)
        object_id = created.get("object_id") or None
        if object_id is not None:
            state.last_object_id = object_id
            state.last_object_type = arguments.get("type")

    if parsed.intent in ("delete_object", "move_object"):
        object_id = _resolve_anaphora(text, state)
        resolved = object_id is not None
        if object_id is None:
            object_id = str(arguments.get("object_id") or "") or None
        if object_id is not None:
            arguments["object_id"] = object_id

    if parsed.intent == "move_object":
        target = arguments.pop("to", None)
        if isinstance(target, list) and target:
            entity_type, params = _read_params(object_id)
            move = _move_params(entity_type, params, target) if params else {}
            if move:
                arguments["params"] = move
            else:
                arguments["params"] = {}

    state.record(text, parsed.intent, parsed.tool, arguments)

    return ChatOutput(
        session_id=state.session_id,
        turn=turn,
        intent=parsed.intent,
        tool=parsed.tool,
        arguments=arguments,
        object_id=object_id,
        resolved=resolved,
        confidence=parsed.confidence,
        status=parsed.status,
        message=parsed.message,
        history_length=len(state.history),
    )


def _execute_create(arguments: dict[str, Any]) -> dict[str, Any]:
    """Best-effort execution of a create intent against the current document."""
    try:
        from tianshangcad.mcp.tools.crud import ObjectCreateInput, cad_object_create

        result = cad_object_create(
            ObjectCreateInput(
                type=str(arguments["type"]),
                params=dict(arguments["params"]),
                layer=str(arguments.get("layer", "0")),
                properties=dict(arguments.get("properties") or {}),
            )
        )
        return {"object_id": result.object_id, "status": result.status}
    except Exception:
        return {}


def _read_params(object_id: str | None) -> tuple[str, dict[str, Any]]:
    """Best-effort read of an entity's type and current shape params."""
    if not object_id:
        return "", {}
    try:
        from tianshangcad.core.document import DocumentManager

        doc = DocumentManager().get_current()
        record = doc.entities.read(object_id)
        shape = record.shape
        params = dict(shape.get("params", {})) if isinstance(shape, dict) else {}
        return record.type, params
    except Exception:
        return "", {}


def cad_nlp_command(input: NLPCommandInput) -> NLPCommandOutput:
    """Parse a natural language request into a CAD tool call.

    将自然语言请求解析为 CAD 工具调用。Supports 12 intent patterns in English
    and Chinese. Ambiguous requests are reported with candidate suggestions
    rather than an arbitrary guess. ``tool_whitelist`` restricts which tool
    the request may resolve to.

    When not to use: this tool only parses — it does NOT execute the
    matched call. To run the resolved tool you must dispatch the returned
    ``tool``/``arguments`` yourself; for multi-turn dialogue with memory
    use ``cad_nlp_chat`` instead.
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
    ("cad_nlp_chat", cad_nlp_chat),
]
