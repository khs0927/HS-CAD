from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path


def test_review_cli_registry_exports_expected_symbols() -> None:
    registry = importlib.import_module("hscad.app.review_cli_registry")
    assert registry.COMMAND_MAIN_CODE == "hscad-main-code-pipeline"
    assert registry.COMMAND_EVIDENCE_BRIDGE == "hscad-evidence-bridge"
    assert callable(registry.register_review_only_commands)


def test_standalone_review_cli_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "hscad.app.cli_review_only", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "main-code" in result.stdout
    assert "evidence-bridge" in result.stdout


def test_register_review_only_cli_dry_run_help() -> None:
    script = Path("scripts/register_review_only_cli.py")
    assert script.exists()
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(script), "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--apply" in result.stdout
