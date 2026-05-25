from __future__ import annotations

import pytest

from src.execution.xicad_safe_runner import XiCADSafeRunner, XiCADSafeRunnerBlocked


def test_safe_runner_records_allowed_dry_run():
    result = XiCADSafeRunner().dry_run_alias("xicad-safe-plan --alias WAL")

    assert result["status"] == "dry_run_recorded"
    assert result["executed"] is False
    assert result["would_send_command"] is False


def test_safe_runner_blocks_destructive_alias():
    result = XiCADSafeRunner().dry_run_alias("xicad-safe-plan --alias ERASE")

    assert result["status"] == "blocked"
    assert result["executed"] is False


def test_safe_runner_blocks_unknown_alias():
    result = XiCADSafeRunner().dry_run_alias("xicad-safe-plan --alias UNKNOWN_ABC")

    assert result["status"] == "blocked"
    assert result["executed"] is False


def test_safe_runner_execute_alias_is_disabled():
    with pytest.raises(XiCADSafeRunnerBlocked):
        XiCADSafeRunner().execute_alias("WAL")
