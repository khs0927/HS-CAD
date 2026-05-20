from __future__ import annotations

from typer.testing import CliRunner

from src.app.cli import app


def test_run_command_dry_run_does_not_connect_to_zwcad() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run-command", "--dwg", "C:/cad/missing.dwg", "--command", "examples/commands/move_layer.json", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "Preview/dry-run" in result.output
    assert "move_layer" in result.output
