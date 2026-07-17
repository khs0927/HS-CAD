# Windows Virtual Validation Report

Date: 2026-07-18
Branch: `chore/windows-virtual-validation`

## Scope

This report records what was actually validated before connecting a real Windows/ZWCAD runner. Virtual validation is supporting evidence only. It must not be described as a real Windows, COM, ZWCAD, DWG, or production acceptance pass.

## Documentation basis

The implementation was checked against current Context7 documentation for:

- pytest `/pytest-dev/pytest`: `monkeypatch`, per-test temporary directories, platform markers, skip behavior, and subprocess isolation;
- pywin32 `/mhammond/pywin32`: `pythoncom.CoInitialize()`, `CoUninitialize()`, and `GetActiveObject`;
- comtypes `/enthought/comtypes`: `GetActiveObject`, `CreateObject`, and isolated COM adapters.

## Defects found and corrected

1. `src/testing/environment_check.py` converted COM objects to strings inside `_safe_attr()`. This prevented `ActiveDocument.Name` from being read correctly.
2. The environment report hard-coded package version `0.1.0` even though package metadata is authoritative.
3. The Windows fixture script had no dedicated test module consuming its acceptance environment variables.
4. Strict CAD acceptance did not require a DWG fixture.
5. The fixture manifest exposed relative fixture paths.
6. The preflight assumed the `py` launcher and did not robustly support a direct Python executable.
7. COM initialization and release were not explicitly balanced by the environment probe.

## Implemented validation layers

### Portable contract validation

`scripts/validate_windows_runner_contract.py` checks:

- Python requirement `>=3.10,<3.13`;
- required runner, publisher, test, and fixture files;
- Windows platform gating;
- strict fixture and hash-only manifest contracts;
- virtual Windows test coverage tokens;
- real acceptance test coverage tokens;
- forbidden embedded workflow, token, service-role assignment, and OpenAI key patterns.

### Virtual Windows simulation

`tests/test_windows_runner_virtualization.py` covers:

- simulated Windows active COM connection;
- COM initialization/uninitialization balance;
- failed COM connection without a false pass;
- active-object-first ZWCAD adapter behavior;
- object creation fallback;
- spawn refusal when disabled;
- non-Windows orchestrator blocking without subprocess execution;
- simulated Windows command success;
- strict `windows-cad` profile selection.

### Contract validator regression

`tests/test_windows_runner_contract.py` proves that the validator:

- passes a complete synthetic contract;
- fails when Windows platform gating is removed;
- fails when a service-role secret assignment pattern is embedded.

### Real Windows/ZWCAD acceptance definition

`tests/test_windows_cad_acceptance.py` is collected only as a definition outside Windows. On an authorized Windows runner it checks:

- Windows dependencies;
- hash-only fixture manifest;
- every DXF fixture through ezdxf;
- every PDF fixture through PyMuPDF;
- every DWG fixture opened read-only in a running ZWCAD instance;
- document close without save;
- balanced `CoInitialize()` / `CoUninitialize()`.

## Executed results

Executed in an isolated non-Windows harness:

```text
python -m compileall -q scripts src tests                         PASS
pytest virtual Windows + contract regression                     12 passed
pytest --collect-only real Windows acceptance                    5 tests collected
ruff check modified Python validation files                      PASS
```

The isolated harness intentionally contains only the minimum modules needed for virtual tests. It is not a substitute for the full repository core profile.

## Evidence registry re-verification

Static re-verification confirmed:

- result-field allowlisting;
- namespaced repository/branch SHA-256 tokens;
- lowercase commit and digest validation;
- finite duration and count checks;
- profile/status allowlists;
- HTTPS-only Supabase endpoint;
- service-role value read from environment only;
- sanitized error output;
- RLS enabled;
- `anon` and `authenticated` revoked;
- unique evidence digest.

The separate Evidence Registry pytest files were inspected. A fresh execution was not counted because the isolated harness did not contain the full publisher implementation.

## Explicitly not passed

The following remain unexecuted and must not be marked passed:

- Windows PowerShell preflight on Windows;
- creation and dependency installation of `.venv-windows-runner` on Windows;
- real `pythoncom` and `comtypes` imports on Windows;
- real ZWCAD process detection;
- real ZWCAD COM registration and `GetActiveObject`;
- actual DWG read-only open/close loop;
- full Drawing Index fixture comparison and manual entity checks;
- full repository core/drawing-index/semantic/mobile profiles after feature integration;
- Supabase evidence insertion and duplicate rejection on a trusted runner;
- iPhone/iPad mobile acceptance;
- GitHub Actions. GitHub Actions are not used as the execution path.

## Windows commands

Virtual and portable preparation:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows-runner-preflight.ps1 -Install -RunVirtualWindows -RunPortable
```

Static-only DXF/PDF fixture validation:

```powershell
.\scripts\run_windows_drawing_index_fixture_matrix.ps1 `
  -Root "C:\HS-CAD-Fixtures" `
  -Workspace "outputs\orchestrator\windows-static" `
  -AllowStaticOnly
```

Strict ZWCAD/DWG acceptance:

```powershell
.\scripts\run_windows_drawing_index_fixture_matrix.ps1 `
  -Root "C:\HS-CAD-Fixtures" `
  -Workspace "outputs\orchestrator\windows-fixture-matrix"
```

## Completion rule

Virtual results may change the status from `not prepared` to `prepared for Windows execution`. Only evidence produced by a real authorized Windows runner with ZWCAD and approved fixtures may change native CAD acceptance to `passed`.
