# Drawing Index Windows Integration Report

Date: 2026-07-18

Virtual validation is supporting evidence only. It is not a real Windows, COM, ZWCAD, DWG, corpus, or production acceptance pass.

The Drawing Index branch keeps its native-versus-fallback fixture comparison in `scripts/run_windows_drawing_index_full_validation.ps1`. That workflow runs hash-only manifest generation, strict ZWCAD/DWG acceptance, native validation, fallback-only validation, result comparison, and manual REVIEW/BLOCK inspection requirements.

Previously executed shared validation in an isolated non-Windows harness:

```text
compileall                                                       PASS
existing environment + virtual Windows + contract regressions    19 passed
real Windows acceptance collection                               5 tests collected
Ruff                                                             PASS
```

Still unexecuted: Windows PowerShell runtime, Windows dependency installation, real COM registration, actual DWG open/close, native-versus-fallback approved fixture comparison, manual entity inspection, and Supabase insertion/duplicate rejection.
