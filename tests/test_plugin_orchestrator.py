from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "run_plugin_orchestrator.py"
    spec = importlib.util.spec_from_file_location("run_plugin_orchestrator", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_safe_command_redacts_private_paths(tmp_path: Path) -> None:
    module = _load_module()
    fixture = str(tmp_path / "private-fixtures")
    command = [sys.executable, str(module.ROOT / "scripts" / "run.py"), fixture]

    safe = module._safe_command(command, fixture)

    assert safe[0] == "<python>"
    assert "<repo-root>" in safe[1]
    assert safe[2] == "<fixture-root>"
    assert fixture not in repr(safe)


def test_explicit_empty_profile_fails_closed(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_drawing_index_checks", lambda: [])

    with pytest.raises(ValueError, match="no runnable checks"):
        module.build_checks(["drawing-index"], None)


def test_auto_cannot_be_mixed_with_explicit_profile() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="cannot be combined"):
        module.build_checks(["auto", "core"], None)


def test_default_evidence_hashes_logs_without_including_them(monkeypatch) -> None:
    module = _load_module()
    secret = "PRIVATE-DRAWING-NAME-DO-NOT-STORE"
    monkeypatch.setenv("HSCAD_ORCHESTRATOR_TEST_SECRET", secret)
    check = module.Check(
        name="privacy-probe",
        command=(
            sys.executable,
            "-c",
            "import os; print(os.environ['HSCAD_ORCHESTRATOR_TEST_SECRET'])",
        ),
    )

    result = module.run_check(
        check,
        timeout=30,
        fixture_root=None,
        include_logs=False,
    )

    assert result.status == "passed"
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.stdout_sha256 != module._digest("")
    assert secret not in repr(result)


def test_logs_are_only_included_by_explicit_opt_in() -> None:
    module = _load_module()
    check = module.Check(
        name="log-probe",
        command=(sys.executable, "-c", "print('safe-log')"),
    )

    result = module.run_check(
        check,
        timeout=30,
        fixture_root=None,
        include_logs=True,
    )

    assert result.status == "passed"
    assert "safe-log" in result.stdout
