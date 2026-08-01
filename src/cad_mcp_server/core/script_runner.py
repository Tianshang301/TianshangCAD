"""Sandboxed execution of user / AI-supplied batch scripts.

Three script types are supported:

- ``python``: executed in a separate subprocess in isolated mode after a
  static AST scan rejects dangerous imports and calls. A runtime guard also
  blanks ``sys.modules`` for dangerous modules, and a hard timeout force
  terminates the process.
- ``scr``: whitespace separated command lines of the form
  ``tool key=value key=value ...`` (values parsed as JSON when possible).
- ``batch``: a JSON document describing ``BatchCommand`` objects.

Nothing is ever executed in the CAD server process itself.
"""

from __future__ import annotations

import ast
import contextlib
import json
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from cad_mcp_server.utils.errors import CADValidationError, SchedulerError

SCRIPT_TYPES = ("python", "scr", "batch")

# Modules a batch script may import. Anything else is rejected.
ALLOWED_IMPORTS = frozenset(
    {
        "math",
        "json",
        "random",
        "datetime",
        "typing",
        "collections",
        "itertools",
        "functools",
        "re",
        "string",
        "decimal",
        "fractions",
        "statistics",
        "cmath",
        "numbers",
        "uuid",
        "time",
    }
)

# Modules that are never allowed (explicit list for clarity / messages).
BLOCKED_IMPORTS = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "importlib",
        "shutil",
        "ctypes",
        "winreg",
        "pathlib",
        "multiprocessing",
        "threading",
        "asyncio",
        "signal",
        "select",
        "pty",
        "platform",
        "gc",
        "builtins",
        "codecs",
    }
)

_BLOCKED_CALLS = frozenset({"exec", "eval", "compile", "__import__", "open", "input"})


def _check_module(name: str, *, from_import: bool) -> str | None:
    """Return a violation message if ``name`` is not importable in a script."""
    top = name.split(".")[0]
    if top in BLOCKED_IMPORTS:
        return f"module '{name}' is blocked"
    if top not in ALLOWED_IMPORTS:
        return f"module '{name}' is not in the allowed import whitelist"
    return None


def _scan_code(code: str) -> list[str]:
    """Return a list of policy violations found by static analysis."""
    violations: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise CADValidationError(f"Python syntax error: {exc.msg}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                message = _check_module(alias.name, from_import=False)
                if message:
                    violations.append(f"import {message}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                message = _check_module(node.module, from_import=True)
                if message:
                    violations.append(f"from {message}")
        elif isinstance(node, ast.Call):
            function = node.func
            name: str | None = None
            if isinstance(function, ast.Name):
                name = function.id
            elif isinstance(function, ast.Attribute) and function.attr in _BLOCKED_CALLS:
                name = function.attr
            if name in _BLOCKED_CALLS:
                violations.append(f"call to '{name}' is blocked")
    return list(dict.fromkeys(violations))


def _runtime_guard() -> str:
    """Return the prefix lines that blank dangerous modules at runtime."""
    blocked = sorted(BLOCKED_IMPORTS)
    lines = [
        "import sys",
        f"_BLOCKED = {blocked!r}",
        "for _name in _BLOCKED:",
        "    sys.modules[_name] = None",
        "",
    ]
    return "\n".join(lines)


def run_python(code: str, timeout: int, args: list[str] | None = None) -> dict[str, Any]:
    """Execute ``code`` in a sandboxed subprocess and return its result."""
    violations = _scan_code(code)
    if violations:
        return {
            "script_type": "python",
            "ok": False,
            "blocked_imports": violations,
            "stdout": "",
            "stderr": "",
            "exit_code": None,
            "duration_ms": 0,
            "timed_out": False,
            "error": "Script policy violation(s): " + "; ".join(violations),
        }
    started = time.perf_counter()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", encoding="utf-8", delete=False
        ) as handle:
            handle.write(_runtime_guard())
            handle.write(code)
            script_path = handle.name
        command = [sys.executable, "-I", script_path, *(args or [])]
        try:
            result = subprocess.run(  # noqa: S603 - isolation is the security boundary
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            timed_out = False
            exit_code = result.returncode
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            error = None
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = None
            stdout = ""
            stderr = f"Script exceeded the {timeout}s timeout"
            error = stderr
        finally:
            with contextlib.suppress(OSError):
                Path(script_path).unlink(missing_ok=True)
    except Exception as exc:
        return {
            "script_type": "python",
            "ok": False,
            "blocked_imports": [],
            "stdout": "",
            "stderr": str(exc),
            "exit_code": None,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "timed_out": False,
            "error": str(exc),
        }
    return {
        "script_type": "python",
        "ok": exit_code == 0 and not timed_out,
        "blocked_imports": [],
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "timed_out": timed_out,
        "error": error,
    }


def _parse_scr_line(line: str) -> dict[str, Any]:
    """Parse ``tool key=value key=value`` into a BatchCommand dict."""
    parts = shlex.split(line)
    if not parts:
        return {"tool": "", "arguments": {}}
    tool = parts[0]
    arguments: dict[str, Any] = {}
    for token in parts[1:]:
        if "=" not in token:
            continue
        key, raw = token.split("=", 1)
        try:
            arguments[key] = json.loads(raw)
        except json.JSONDecodeError:
            arguments[key] = raw
    return {"tool": tool, "arguments": arguments}


def _dispatch(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a registered MCP tool (lazy import to avoid cycles)."""
    from cad_mcp_server.mcp.tools.batch import _dispatch as dispatch

    return dispatch(tool, arguments)


def run_commands(commands: list[dict[str, Any]]) -> dict[str, Any]:
    """Execute a list of BatchCommand dicts through the MCP tool registry."""
    results = []
    success_count = 0
    failed_count = 0
    for index, command in enumerate(commands):
        tool = command.get("tool", "")
        try:
            output = _dispatch(tool, command.get("arguments", {}))
            success_count += 1
            results.append(
                {"tool": tool, "index": index, "success": True, "result": output, "error": None}
            )
        except Exception as exc:
            failed_count += 1
            results.append(
                {"tool": tool, "index": index, "success": False, "result": None, "error": str(exc)}
            )
    return {
        "script_type": "commands",
        "ok": failed_count == 0,
        "results": results,
        "success_count": success_count,
        "failed_count": failed_count,
        "error": None if failed_count == 0 else f"{failed_count} command(s) failed",
    }


def run_script(
    *,
    script: str,
    script_type: str = "python",
    timeout: int = 60,
    args: list[str] | None = None,
) -> dict[str, Any]:
    """Run a script according to its type and return a uniform result dict."""
    if script_type not in SCRIPT_TYPES:
        raise SchedulerError(f"Unsupported script_type: {script_type}")
    if script_type == "python":
        return run_python(script, timeout=max(timeout, 1), args=args)
    if script_type == "batch":
        try:
            data = json.loads(script)
        except json.JSONDecodeError as exc:
            raise SchedulerError(f"Invalid batch JSON: {exc}") from exc
        commands = data.get("commands", data) if isinstance(data, dict) else data
        if not isinstance(commands, list):
            message = "batch script must be a list of commands or an object with 'commands'"
            raise SchedulerError(message)
        return run_commands(commands)
    # script_type == "scr"
    commands = [
        command
        for line in script.splitlines()
        if (command := _parse_scr_line(line)) and command["tool"]
    ]
    return run_commands(commands)


def render_template(name: str, variables: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Render a batch command template into a list of command dicts."""
    from cad_mcp_server.core.batch_templates import render_template as render

    return render(name, variables or {})
