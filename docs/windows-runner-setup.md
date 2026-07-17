# HS-CAD Windows Runner Setup

This runner is the final local execution layer for Windows 11, ZWCAD, and real drawing fixtures. GitHub Actions is not required.

## 1. Prerequisites

- Windows 11
- Python 3.10, 3.11, or 3.12 (64-bit)
- PowerShell 5.1 or newer
- ZWCAD 2024-2026 for CAD acceptance tests
- A local checkout of this repository

The project explicitly rejects Python 3.13 and newer because `pyproject.toml` requires `>=3.10,<3.13`.

## 2. Install and preflight

Open PowerShell in the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows-runner-preflight.ps1 -Install -RunPortable
```

This creates `.venv-windows-runner`, installs the project and development dependencies, checks Windows-only imports, verifies required orchestrator files, and runs the portable core profile.

Expected output:

- Windows platform: PASS
- Supported Python: PASS
- Virtual environment: PASS
- Windows dependencies: PASS
- Required files: PASS
- Portable orchestrator: PASS

ZWCAD may be reported as `BLOCKED` during portable-only validation. That is not a pass and is expected until the real CAD gate is run.

## 3. Run the real Windows/ZWCAD fixture gate

Start ZWCAD first. Prepare a fixture directory containing approved DWG, DXF, or PDF files. Then run:

```powershell
.\scripts\run_windows_drawing_index_fixture_matrix.ps1 `
  -Root "C:\HS-CAD-Fixtures" `
  -Workspace "outputs/orchestrator/windows-fixture-matrix"
```

The script refuses to run when:

- the operating system is not Windows;
- ZWCAD is not running;
- the fixture directory is missing;
- no supported fixture files exist;
- the dedicated virtual environment is missing; or
- Windows/ZWCAD tests fail.

A fixture manifest is written to the workspace. It contains relative paths, extensions, file counts, and file sizes. It does not contain drawing contents.

## 4. Run through the orchestrator

```powershell
.\.venv-windows-runner\Scripts\python.exe scripts\run_plugin_orchestrator.py `
  --profile windows-cad `
  --fixture-root "C:\HS-CAD-Fixtures" `
  --continue-on-error `
  --output "outputs\orchestrator\windows-cad.json"
```

Do not publish evidence unless the generated JSON has been reviewed and contains no local paths or sensitive drawing data.

## 5. Evidence publishing

Required environment variables:

```text
HSCAD_REPOSITORY_REF
HSCAD_BRANCH_REF
HSCAD_COMMIT_SHA
HSCAD_ORCHESTRATOR_NAMESPACE
HSCAD_SUPABASE_URL
HSCAD_SUPABASE_SERVICE_ROLE_KEY
```

First run a dry-run:

```powershell
.\.venv-windows-runner\Scripts\python.exe scripts\publish_orchestrator_evidence.py --dry-run
```

Only after the dry-run output is reviewed should the same command be run without `--dry-run`.

## Completion rule

Windows readiness is complete only when all of the following exist:

1. portable preflight JSON;
2. a successful Windows/ZWCAD fixture matrix;
3. sanitized orchestrator evidence JSON;
4. a successful dry-run privacy review;
5. a Supabase insert with an evidence SHA; and
6. verified duplicate rejection.

Until then, the Windows gate must remain `blocked` or `failed`, never `passed`.
