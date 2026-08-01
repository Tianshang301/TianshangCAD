"""CLI batch command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from cad_mcp_server.cli.main import app

runner = CliRunner()


class TestBatchCommands:
    """`cad-cli batch` command tests."""

    def test_list_empty(self) -> None:
        result = runner.invoke(app, ["batch", "list"])
        assert result.exit_code == 0
        assert "No batch jobs" in result.stdout

    def test_templates(self) -> None:
        result = runner.invoke(app, ["batch", "templates"])
        assert result.exit_code == 0
        assert "cleanup" in result.stdout
        assert "export_all" in result.stdout
        assert "backup_json" in result.stdout

    def test_schedule_and_logs(self, tmp_path) -> None:
        commands_file = tmp_path / "commands.json"
        commands_file.write_text(
            '[{"tool": "cad_metrics_get", "arguments": {}}]', encoding="utf-8"
        )
        scheduled = runner.invoke(
            app, ["batch", "schedule", str(commands_file), "--name", "cli-test"]
        )
        assert scheduled.exit_code == 0
        assert "Scheduled" in scheduled.stdout

        listed = runner.invoke(app, ["batch", "list"])
        assert "cli-test" in listed.stdout

        job_id = scheduled.stdout.split()[1].rstrip(":")
        status = runner.invoke(app, ["batch", "status", job_id])
        assert status.exit_code == 0

        logs = runner.invoke(app, ["batch", "logs", "--source", "batch", "--limit", "5"])
        assert logs.exit_code == 0

    def test_run_script_python(self, tmp_path) -> None:
        script = tmp_path / "hello.py"
        script.write_text("import math\nprint(math.pi)\n", encoding="utf-8")
        result = runner.invoke(app, ["batch", "run-script", str(script)])
        assert result.exit_code == 0
        assert "3.141592653589793" in result.stdout

    def test_run_script_blocks_os(self, tmp_path) -> None:
        script = tmp_path / "bad.py"
        script.write_text("import os\nprint('nope')\n", encoding="utf-8")
        result = runner.invoke(app, ["batch", "run-script", str(script)])
        assert result.exit_code == 1
        assert "policy violation" in result.stderr or "Script failed" in result.stderr
