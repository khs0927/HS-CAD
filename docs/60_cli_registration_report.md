# 60. CLI Registration Report

## Branch

- `feat/pr43-worker-manifest-registration`

## Source Guide

- `hscad_feature_completion_framework_guides.zip`
- Applied guide: `04_CLI_REGISTRATION_FRAMEWORK.md`

## Scope

- Registered import-safe CLI modules in `src/main.py`.
- Verified PR38 analysis CLI registrations already present:
  - `src.app.analysis_shortcut_cli`
  - `src.app.analysis_shortcut_cli_v2`
  - `src.app.analysis_shortcut_cli_v3`
  - `src.app.analysis_pipeline_cli`
- Added missing worker runtime support needed by registered analysis shortcuts:
  - `src.workers.contracts`
  - `src.workers.registry`
  - `src.workers.runner`
  - `src.workers.provenance`

## Import Safety Result

- Checked `21` CLI modules under `src/app`.
- Failed imports before fix:
  - `src.app.analysis_shortcut_cli`: missing `src.workers.contracts`
- Failed imports after fix:
  - none

## Safety

- `config/worker_manifest.json` was not modified.
- CAD files were not opened or mutated.
- ZWCAD COM `SendCommand` was not executed.
- `outputs/**`, DWG/DXF, cache, and temp files are not part of this report scope.

## Validation Commands

```powershell
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q tests/test_worker_runtime_contracts.py
python -X utf8 -m pytest -q
```

## Next Step

- Keep worker manifest registration separate from this CLI registration branch.
- Run `05_WORKER_MANIFEST_REGISTRATION_FRAMEWORK.md` on a dedicated branch after review.
