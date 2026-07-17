# HS-CAD Windows Runner Setup

This runner is the final local execution layer for Windows 11, ZWCAD, and approved drawing fixtures. GitHub Actions is not required.

## 1. Prerequisites

- Windows 11
- Python 3.10, 3.11, or 3.12 (64-bit)
- Windows PowerShell 5.1 or newer
- ZWCAD 2024-2026 for native CAD acceptance
- A local checkout of this repository

The project requires Python `>=3.10,<3.13`.

## 2. Install, contract, virtual, and portable validation

Open PowerShell in the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows-runner-preflight.ps1 -Install -RunVirtualWindows -RunPortable
```

This command:

- creates `.venv-windows-runner`;
- installs project and development dependencies;
- checks Windows-only imports;
- validates the runner contract;
- runs virtual Windows/COM regression tests; and
- runs the portable core orchestrator profile.

A missing ZWCAD process remains `BLOCKED`; it is never converted into a pass.

## 3. Static-only DXF/PDF validation

This validates approved DXF/PDF fixtures without claiming native CAD acceptance:

```powershell
.\scripts\run_windows_drawing_index_fixture_matrix.ps1 `
  -Root "C:\HS-CAD-Fixtures" `
  -Workspace "outputs\orchestrator\windows-static" `
  -AllowStaticOnly
```

## 4. Strict Windows/ZWCAD/DWG acceptance

Start ZWCAD first. The fixture directory must contain at least one approved DWG:

```powershell
.\scripts\run_windows_drawing_index_fixture_matrix.ps1 `
  -Root "C:\HS-CAD-Fixtures" `
  -Workspace "outputs\orchestrator\windows-fixture-matrix"
```

Strict mode refuses to pass when Windows, the dedicated virtual environment, a running ZWCAD process, a DWG fixture, dependency imports, COM access, or fixture tests are unavailable.

The generated fixture manifest contains only:

- SHA-256 of each normalized relative fixture path;
- extension;
- size; and
- aggregate counts.

It does not store filenames, relative paths, drawing contents, extracted text, commands, or local working paths.

## 5. Run through the orchestrator

```powershell
.\.venv-windows-runner\Scripts\python.exe scripts\run_plugin_orchestrator.py `
  --profile windows-cad `
  --fixture-root "C:\HS-CAD-Fixtures" `
  --continue-on-error `
  --output "outputs\orchestrator\windows-cad.json"
```

Review the JSON locally before evidence publishing.

## 6. Evidence publishing

Required environment variables:

```text
HSCAD_REPOSITORY_REF
HSCAD_BRANCH_REF
HSCAD_COMMIT_SHA
HSCAD_ORCHESTRATOR_NAMESPACE
HSCAD_SUPABASE_URL
HSCAD_SUPABASE_SERVICE_ROLE_KEY
```

First run:

```powershell
.\.venv-windows-runner\Scripts\python.exe scripts\publish_orchestrator_evidence.py --dry-run
```

Only publish after privacy review.

## Completion rule

Windows readiness is complete only when all of the following exist:

1. successful preflight and virtual regression results;
2. a successful strict Windows/ZWCAD fixture matrix;
3. sanitized orchestrator evidence JSON;
4. a successful dry-run privacy review;
5. a Supabase insert with an evidence SHA; and
6. verified duplicate rejection.

Until then, native Windows/ZWCAD acceptance remains `blocked` or `failed`, never `passed`.
