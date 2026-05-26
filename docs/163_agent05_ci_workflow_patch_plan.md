# 163. Agent 05 CI Workflow Patch Plan

Date: 2026-05-26

## Agent 05 role

Agent 05 handles CI/workflow readiness when GitHub workflow write permission may be unavailable.

Therefore Agent 05 must not directly push `.github/workflows/*.yml` unless workflow scope is explicitly available and approved.

## Current baseline

```text
main SHA: 70c8e4df3583fc9fcd8c01937dc7636444eafcf6
```

## Current task result

This is a docs-only workflow patch plan. It does not add or modify GitHub Actions workflow files.

## Why docs-only

Workflow edits require higher-risk repository permission and can trigger CI changes across every PR.

Until workflow scope is confirmed, keep workflow changes as reviewable patch documentation.

## CI checks required before any small registration PR

Every worker/CLI registration PR should prove at least:

```powershell
python -X utf8 -m compileall -q src tests
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

For PR82 CLI registration candidates:

```powershell
python -X utf8 -m pytest -q tests/test_worker_contracts.py tests/test_worker_run_log.py tests/test_worker_runner.py
```

For execution-candidate or live-runner-adjacent PRs:

```powershell
python -X utf8 -m pytest -q tests/test_execution_candidate_planner.py
python -X utf8 -m pytest -q tests/test_final_live_runner_preflight_guard.py
```

## Proposed workflow file, not applied

If workflow scope is later approved, create a narrow workflow such as:

```yaml
name: HS-CAD Review Only Safety Checks

on:
  pull_request:
    branches: [ main ]

jobs:
  review-only-safety:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install test dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt
          python -m pip install pytest
      - name: Compile
        run: python -X utf8 -m compileall -q src tests
      - name: CLI smoke
        run: python -X utf8 -m src.main --help
      - name: Full tests
        run: python -X utf8 -m pytest -q
```

## Safety assertions for CI policy

CI must reject or flag PRs that introduce runtime/binary artifacts:

```text
outputs/**
artifacts/**/*.zip
*.dwg
*.dxf
*.sqlite
*.sqlite3
__pycache__/**
.pytest_cache/**
```

CI should also flag high-risk file changes for manual review:

```text
src/main.py
config/worker_manifest.json
src/adapters/zwcad_com_adapter.py
src/converters/oda_file_converter.py
src/analysis/final_live_runner.py
src/app/zwcad_live_runner_cli.py
.github/workflows/*.yml
```

## Agent 05 next action

Do not create workflow files yet.

First resolve open docs-only cleanup:

```text
PR #99: already merged
PR #101: closed as superseded/no-op
PR #102: superseded by this clean docs-only contract plan
```

Then proceed only after local validation on latest main.

## Safety

This document does not approve:

```text
CAD execution
SendCommand
SaveAs
DXFOUT
XiCAD alias execution
original DWG mutation
live runner implementation
```
