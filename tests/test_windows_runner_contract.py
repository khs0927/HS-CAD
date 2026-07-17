from __future__ import annotations

from pathlib import Path

from scripts.validate_windows_runner_contract import validate


def _write(root: Path, relative: str, content: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _complete_contract_tree(root: Path) -> None:
    _write(root, "pyproject.toml", '[project]\nrequires-python = ">=3.10,<3.13"\n')
    _write(
        root,
        "scripts/run_plugin_orchestrator.py",
        'if profile == "windows-cad":\n'
        '    script = "run_windows_drawing_index_fixture_matrix.ps1"\n'
        '    platforms=("Windows",)\n',
    )
    _write(root, "scripts/publish_orchestrator_evidence.py", "# hash-only publisher\n")
    _write(
        root,
        "scripts/windows-runner-preflight.ps1",
        'if ($env:OS -ne "Windows_NT") {}\n'
        '.venv-windows-runner\n'
        'validate_windows_runner_contract.py\n'
        'test_windows_runner_virtualization.py\n',
    )
    _write(
        root,
        "scripts/run_windows_drawing_index_fixture_matrix.ps1",
        'HSCAD_WINDOWS_CAD_ACCEPTANCE\n'
        'HSCAD_WINDOWS_STATIC_ONLY\n'
        'path_sha256\n'
        'test_windows_cad_acceptance.py\n'
        'At least one DWG fixture is required\n',
    )
    _write(
        root,
        "tests/test_windows_runner_virtualization.py",
        'monkeypatch\nmonkeypatch.setattr\n"system"\nGetActiveObject\nstatus == "blocked"\n',
    )
    _write(
        root,
        "tests/test_windows_cad_acceptance.py",
        'pytest.mark.windows\n'
        'pytest.mark.zwcad\n'
        'HSCAD_WINDOWS_CAD_ACCEPTANCE\n'
        'CoInitialize\n'
        'Documents.Open\n'
        'Close(False)\n',
    )


def test_complete_windows_runner_contract_passes(tmp_path: Path):
    _complete_contract_tree(tmp_path)

    payload = validate(tmp_path)

    assert payload["status"] == "passed"
    assert payload["passed"] == payload["total"]


def test_contract_fails_when_windows_platform_gate_is_removed(tmp_path: Path):
    _complete_contract_tree(tmp_path)
    _write(
        tmp_path,
        "scripts/run_plugin_orchestrator.py",
        'if profile == "windows-cad":\n'
        '    script = "run_windows_drawing_index_fixture_matrix.ps1"\n',
    )

    payload = validate(tmp_path)

    assert payload["status"] == "failed"
    failed = {item["name"] for item in payload["checks"] if not item["ok"]}
    assert "orchestrator-windows-contract" in failed


def test_contract_rejects_embedded_secret_patterns(tmp_path: Path):
    _complete_contract_tree(tmp_path)
    preflight = tmp_path / "scripts/windows-runner-preflight.ps1"
    preflight.write_text(
        preflight.read_text(encoding="utf-8") + '\nHSCAD_SUPABASE_SERVICE_ROLE_KEY="embedded"\n',
        encoding="utf-8",
    )

    payload = validate(tmp_path)

    assert payload["status"] == "failed"
    failed = {item["name"] for item in payload["checks"] if not item["ok"]}
    assert "no-forbidden-runner-content" in failed
