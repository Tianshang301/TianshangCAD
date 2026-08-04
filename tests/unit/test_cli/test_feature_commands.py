"""CLI parametric feature command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from tianshangcad.cli.main import app
from tianshangcad.core.document import DocumentManager

runner = CliRunner()


def _setup() -> None:
    manager = DocumentManager()
    manager.create("features.json", unit="mm")


def _run(*args: str):
    return runner.invoke(app, [*args])


def _circle(center: str = "0,0") -> str:
    doc = DocumentManager().get_current()
    before = {r.id for r in doc.entities.list() if r.type == "circle"}
    assert _run("draw", "circle", center, "--radius", "5").exit_code == 0
    return next(
        r.id for r in doc.entities.list() if r.type == "circle" and r.id not in before
    )


def _box() -> str:
    assert _run("draw", "box", "0,0,0", "--dimensions", "2,2,2").exit_code == 0
    doc = DocumentManager().get_current()
    return next(record.id for record in doc.entities.list() if record.type == "box")


class TestFeatureCommands:
    """`feature` CLI group tests."""

    def test_sweep_circle(self) -> None:
        _setup()
        profile = _circle()
        result = _run("feature", "sweep", profile, "0,0,0 0,0,20")
        assert result.exit_code == 0, result.output
        assert "Sweep created" in result.output
        doc = DocumentManager().get_current()
        assert any(record.type == "cylinder" for record in doc.entities.list())

    def test_loft(self) -> None:
        _setup()
        c1 = _circle()
        c2 = _circle("0,0,10")
        result = _run("feature", "loft", f"{c1},{c2}")
        assert result.exit_code == 0, result.output
        doc = DocumentManager().get_current()
        assert any(record.type == "cone" for record in doc.entities.list())

    def test_pattern_linear(self) -> None:
        _setup()
        box = _box()
        doc = DocumentManager().get_current()
        result = _run(
            "feature", "pattern", box, "--kind", "linear",
            "--direction", "1,0,0", "--count", "3", "--spacing", "5",
        )
        assert result.exit_code == 0, result.output
        assert "3 instances" in result.output
        assert doc.entities.count() == 3

    def test_pattern_invalid_kind(self) -> None:
        _setup()
        result = _run("feature", "pattern", "x", "--kind", "bogus", "--direction", "1,0,0")
        assert result.exit_code != 0

    def test_fillet_error_message(self) -> None:
        _setup()
        box = _box()
        result = _run("feature", "fillet", box, "1")
        assert result.exit_code == 1
        assert "OCCT" in result.output
