from __future__ import annotations

import subprocess
import sys


def _help_ok(path: str) -> str:
    result = subprocess.run([sys.executable, path, "--help"], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_verify_environment_tool_help():
    assert "Verify Python/ZWCAD" in _help_ok("tools/verify_zwcad_environment.py")
    assert "Verify Python/ZWCAD" in _help_ok("tools/verify_zwcad2025_environment.py")
    assert "Verify Python/ZWCAD" in _help_ok("tools/verify_zwcad2026_environment.py")


def test_run_test_plan_tool_help():
    assert "safe ZWCAD" in _help_ok("tools/run_zwcad_test_plan.py")
    assert "safe ZWCAD" in _help_ok("tools/run_zwcad2025_test_plan.py")
    assert "safe ZWCAD" in _help_ok("tools/run_zwcad2026_test_plan.py")
