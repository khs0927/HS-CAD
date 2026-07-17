from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ContractCheck:
    name: str
    ok: bool
    detail: str


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _contains(path: Path, *needles: str, root: Path = ROOT) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing:{_display_path(path, root)}"
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        return False, "missing tokens:" + ",".join(missing)
    return True, "ok"


def validate(root: Path = ROOT) -> dict[str, object]:
    root = root.resolve()
    checks: list[ContractCheck] = []

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        match = re.search(r'requires-python\s*=\s*"([^"]+)"', text)
        ok = bool(match and match.group(1) == ">=3.10,<3.13")
        detail = match.group(1) if match else "missing requires-python"
    else:
        ok, detail = False, "missing:pyproject.toml"
    checks.append(ContractCheck("python-version-contract", ok, detail))

    required_files = [
        "scripts/run_plugin_orchestrator.py",
        "scripts/publish_orchestrator_evidence.py",
        "scripts/windows-runner-preflight.ps1",
        "scripts/run_windows_drawing_index_fixture_matrix.ps1",
        "tests/test_windows_runner_virtualization.py",
        "tests/test_windows_runner_contract.py",
        "tests/test_windows_cad_acceptance.py",
    ]
    for relative in required_files:
        path = root / relative
        checks.append(ContractCheck(f"file:{relative}", path.exists(), "present" if path.exists() else "missing"))

    preflight = root / "scripts/windows-runner-preflight.ps1"
    ok, detail = _contains(
        preflight,
        'if ($env:OS -ne "Windows_NT")',
        ".venv-windows-runner",
        "validate_windows_runner_contract.py",
        "test_windows_runner_virtualization.py",
        "test_windows_runner_contract.py",
        root=root,
    )
    checks.append(ContractCheck("preflight-contract", ok, detail))

    matrix = root / "scripts/run_windows_drawing_index_fixture_matrix.ps1"
    ok, detail = _contains(
        matrix,
        "HSCAD_WINDOWS_CAD_ACCEPTANCE",
        "HSCAD_WINDOWS_STATIC_ONLY",
        "path_sha256",
        "test_windows_cad_acceptance.py",
        "At least one DWG fixture is required",
        "[IO.Path]::IsPathRooted",
        ".Substring($fixturePrefix.Length)",
        root=root,
    )
    checks.append(ContractCheck("fixture-matrix-contract", ok, detail))

    if matrix.exists():
        matrix_text = matrix.read_text(encoding="utf-8")
        compatible = "[IO.Path]::GetRelativePath" not in matrix_text
        compatibility_detail = "ok" if compatible else "unsupported Path.GetRelativePath dependency"
    else:
        compatible = False
        compatibility_detail = f"missing:{_display_path(matrix, root)}"
    checks.append(ContractCheck("powershell-5-path-contract", compatible, compatibility_detail))

    orchestrator = root / "scripts/run_plugin_orchestrator.py"
    ok, detail = _contains(
        orchestrator,
        'profile == "windows-cad"',
        "run_windows_drawing_index_fixture_matrix.ps1",
        'platforms=("Windows",)',
        root=root,
    )
    checks.append(ContractCheck("orchestrator-windows-contract", ok, detail))

    virtual_test = root / "tests/test_windows_runner_virtualization.py"
    ok, detail = _contains(
        virtual_test,
        "monkeypatch",
        "monkeypatch.setattr",
        '"system"',
        "GetActiveObject",
        'status == "blocked"',
        root=root,
    )
    checks.append(ContractCheck("virtual-test-contract", ok, detail))

    acceptance_test = root / "tests/test_windows_cad_acceptance.py"
    ok, detail = _contains(
        acceptance_test,
        "pytest.mark.windows",
        "pytest.mark.zwcad",
        "HSCAD_WINDOWS_CAD_ACCEPTANCE",
        "CoInitialize",
        "Documents.Open",
        "Close(False)",
        root=root,
    )
    checks.append(ContractCheck("acceptance-test-contract", ok, detail))

    forbidden_patterns = [
        ("workflow-path", re.compile(re.escape(".github/workflows"), re.IGNORECASE)),
        ("github-token-assignment", re.compile(r"GITHUB_TOKEN\s*=", re.IGNORECASE)),
        (
            "service-role-assignment",
            re.compile(r"HSCAD_SUPABASE_SERVICE_ROLE_KEY\s*=", re.IGNORECASE),
        ),
        ("openai-secret-prefix", re.compile(r"sk-proj-", re.IGNORECASE)),
    ]
    inspected = [preflight, matrix, virtual_test, acceptance_test]
    leaks: list[str] = []
    for path in inspected:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in forbidden_patterns:
            if pattern.search(text):
                leaks.append(f"{_display_path(path, root)}:{label}")
    checks.append(ContractCheck("no-forbidden-runner-content", not leaks, "none" if not leaks else ",".join(leaks)))

    passed = sum(1 for check in checks if check.ok)
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "status": "passed" if passed == len(checks) else "failed",
        "passed": passed,
        "total": len(checks),
        "checks": [asdict(check) for check in checks],
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the portable Windows runner contract.")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    payload = validate()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
