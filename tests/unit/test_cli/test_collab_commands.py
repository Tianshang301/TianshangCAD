"""CLI collaboration command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from tianshangcad.cli.main import app
from tianshangcad.core.collab import CollabManager
from tianshangcad.core.document import DocumentManager

runner = CliRunner()


def _setup() -> None:
    manager = DocumentManager()
    manager.create("collab.json", unit="mm")


def _run(*args: str):
    return runner.invoke(app, [*args])


class TestCollabCommands:
    """`collab` CLI group tests."""

    def test_create_and_list(self) -> None:
        _setup()
        created = _run("collab", "create", "--name", "review")
        assert created.exit_code == 0, created.output
        assert "Session collab_" in created.output

        listed = _run("collab", "list")
        assert listed.exit_code == 0, listed.output
        assert "review" in listed.output

    def test_annotate(self) -> None:
        _setup()
        _run("collab", "create", "--name", "review")
        session_id = CollabManager().list_sessions()[0]["session_id"]
        result = _run("collab", "annotate", session_id, "check hole")
        assert result.exit_code == 0, result.output
        assert "Annotation ann_" in result.output

    def test_sync_prints_state(self) -> None:
        _setup()
        _run("collab", "create", "--name", "review")
        session_id = CollabManager().list_sessions()[0]["session_id"]
        result = _run("collab", "sync", session_id)
        assert result.exit_code == 0, result.output
        assert '"layer:0"' in result.output

    def test_perm_grant(self) -> None:
        _setup()
        _run("collab", "create", "--name", "review")
        session_id = CollabManager().list_sessions()[0]["session_id"]
        result = _run("collab", "perm", session_id, "bob", "--role", "editor")
        assert result.exit_code == 0, result.output
        assert "bob granted editor" in result.output
