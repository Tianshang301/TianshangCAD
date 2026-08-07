"""Unit tests for the sandboxed batch script runner."""

from __future__ import annotations

import pytest

from tianshangcad.core.script_runner import (
    SCRIPT_TYPES,
    _scan_code,
    run_script,
)
from tianshangcad.utils.errors import CADValidationError, SchedulerError


class TestPythonSandbox:
    """Sandboxed python execution."""

    def test_allowed_script_succeeds(self) -> None:
        result = run_script(script="import math\nprint(math.sqrt(16))", script_type="python")
        assert result["ok"] is True
        assert result["stdout"].strip() == "4.0"
        assert result["exit_code"] == 0

    def test_from_import_allowed(self) -> None:
        result = run_script(
            script="from math import sqrt\nprint(sqrt(9))", script_type="python"
        )
        assert result["ok"] is True
        assert result["stdout"].strip() == "3.0"

    def test_blocked_import_os(self) -> None:
        result = run_script(script="import os\nprint(os.getcwd())", script_type="python")
        assert result["ok"] is False
        assert any("os" in violation for violation in result["blocked_imports"])

    def test_blocked_import_subprocess(self) -> None:
        result = run_script(script="import subprocess", script_type="python")
        assert result["ok"] is False
        assert any("subprocess" in violation for violation in result["blocked_imports"])

    def test_blocked_import_socket(self) -> None:
        result = run_script(script="import socket", script_type="python")
        assert result["ok"] is False

    def test_blocked_non_whitelisted_module(self) -> None:
        result = run_script(script="import numpy", script_type="python")
        assert result["ok"] is False
        assert any("numpy" in violation for violation in result["blocked_imports"])

    def test_blocked_exec_eval_compile(self) -> None:
        for call in ("exec", "eval", "compile"):
            result = run_script(script=f"{call}('1+1')", script_type="python")
            assert result["ok"] is False, call
            assert any(call in violation for violation in result["blocked_imports"])

    def test_blocked_open(self) -> None:
        result = run_script(script="open('/etc/passwd')", script_type="python")
        assert result["ok"] is False
        assert any("open" in violation for violation in result["blocked_imports"])

    def test_syntax_error_reported(self) -> None:
        with pytest.raises(CADValidationError):
            _scan_code("def broken(:")

    def test_timeout_force_terminates(self) -> None:
        result = run_script(
            script="import time\nwhile True: time.sleep(1)", script_type="python", timeout=1
        )
        assert result["timed_out"] is True
        assert result["ok"] is False

    def test_sys_module_blocked(self) -> None:
        result = run_script(script="import sys\nprint('x')", script_type="python")
        assert result["ok"] is False
        assert any("sys" in violation for violation in result["blocked_imports"])


class TestScrAndBatch:
    """SCR command lists and batch JSON scripts."""

    def test_scr_commands_execute(self) -> None:
        result = run_script(
            script="cad_metrics_get\ncad_status", script_type="scr"
        )
        assert result["ok"] is True
        assert result["success_count"] == 2
        assert result["results"][0]["tool"] == "cad_metrics_get"

    def test_scr_failure_flagged(self) -> None:
        result = run_script(
            script="cad_metrics_get\ncad_does_not_exist x=1", script_type="scr"
        )
        assert result["ok"] is False
        assert result["failed_count"] == 1
        assert "Unknown tool" in result["results"][1]["error"]

    def test_scr_arguments_parsed(self) -> None:
        result = run_script(script="cad_file_create filename=scr.json unit=mm", script_type="scr")
        assert result["ok"] is True
        assert result["results"][0]["result"]["file_id"].startswith("file_")

    def test_batch_json_commands(self) -> None:
        script = '{"commands":[{"tool":"cad_metrics_get","arguments":{}}]}'
        result = run_script(script=script, script_type="batch")
        assert result["ok"] is True
        assert result["success_count"] == 1

    def test_batch_json_array(self) -> None:
        script = '[{"tool":"cad_metrics_get","arguments":{}}]'
        result = run_script(script=script, script_type="batch")
        assert result["ok"] is True

    def test_batch_invalid_json_rejected(self) -> None:
        with pytest.raises(SchedulerError):
            run_script(script="{not json", script_type="batch")

    def test_unsupported_script_type_rejected(self) -> None:
        with pytest.raises(SchedulerError):
            run_script(script="x", script_type="powershell")

    def test_script_types_enum(self) -> None:
        assert set(SCRIPT_TYPES) == {"python", "scr", "batch"}
