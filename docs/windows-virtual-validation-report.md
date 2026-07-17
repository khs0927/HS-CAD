# Windows Virtual Validation Report

Date: 2026-07-18

## Scope

Virtual validation is supporting evidence only. It is not a real Windows, COM, ZWCAD, DWG, corpus, or production acceptance pass.

## Context7 basis

- pytest `/pytest-dev/pytest`: monkeypatch, temporary directories, markers, skip behavior, and subprocess isolation;
- pywin32 `/mhammond/pywin32`: `CoInitialize()`, `CoUninitialize()`, and `GetActiveObject`;
- comtypes `/enthought/comtypes`: active-object lookup, object creation, and adapter isolation.

## Corrected defects

- COM objects were converted to strings before `ActiveDocument.Name` was read.
- COM initialization and release were not explicitly balanced.
- package version was hard-coded.
- the fixture gate had no dedicated acceptance tests.
- strict mode did not require a DWG fixture.
- fixture manifests exposed relative paths.
- Windows PowerShell 5.1 path compatibility was incomplete.
- missing contract files could stop validation instead of returning a failed check.

## Drawing Index integration

The Drawing Index branch keeps its native-versus-fallback fixture comparison. The unified script now runs:

1. hash-only manifest generation;
2. static DXF/PDF or strict ZWCAD/DWG acceptance;
3. native Drawing Index validation;
4. fallback-only validation;
5. comparison report generation; and
6. manual REVIEW/BLOCK inspection requirements.

## Previously executed portable results

On an isolated non-Windows harness for the shared Windows validation implementation:

```text
compileall                                                       PASS
existing environment + virtual Windows + contract regressions    19 passed
real Windows acceptance collection                               5 tests collected
Ruff                                                             PASS
```

The integrated Drawing Index branch still requires its own full repository and real Windows execution after merge.

## Explicitly not passed

- Windows PowerShell runtime execution;
- Windows virtual-environment installation;
- real pywin32/comtypes imports;
- ZWCAD process and COM registration;
- actual DWG open/close;
- native-versus-fallback corpus comparison on approved fixtures;
- manual entity inspection;
- Supabase insert and duplicate rejection; and
- GitHub Actions, which are not used as the execution path.
