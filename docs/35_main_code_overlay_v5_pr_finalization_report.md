# HS-CAD Main-Code Overlay v5 PR Finalization Report

## Purpose

v5 is the PR-finalization layer for the previously validated v1/v2/v3/v4 overlays.

It does not introduce CAD execution. It adds PR-readiness validation, PR body generation, and final hygiene checks so the feature branch can be reviewed safely.

## Added capabilities

- Validate changed files before commit.
- Block runtime artifacts:
  - `outputs/**`
  - `_incoming/**`
  - `*.zip`
  - `*.dwg`
  - runtime `*.dxf`
  - caches and bytecode
- Generate a PR body from current changed files.
- Add tests for PR readiness rules.

## Expected local baseline

After v1-v4, the reported local state was:

- v3 full pytest: `222 passed, 16 skipped`
- v4 pending local validation
- CAD execution: none
- ZWCAD COM: none
- SendCommand: none
- XiCAD alias: none
- original DWG mutation: none

v5 should be validated on the same branch:

```powershell
python -X utf8 -m pytest -q tests/test_pr_readiness_v5.py
python -X utf8 scripts\validate_hscad_pr_ready.py --repo-root .
python -X utf8 scripts\generate_hscad_pr_body.py --repo-root .
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m pytest -q
```

## Commit policy

Commit only source, tests, scripts, docs, and workflow files.

Do not commit:

- `_incoming/**`
- `outputs/**`
- `.pytest_cache/**`
- `__pycache__/**`
- `.ruff_cache/**`
- `*.zip`
- `*.dwg`
- runtime `*.dxf`
- `*.sqlite3`

## Recommended PR title

`Add review-only main-code pipeline and evidence bridge`

## Next follow-up after this PR

1. Connect existing analyzer/exporter outputs to evidence bridge with real golden artifact cases.
2. Strengthen ezdxf writer fidelity.
3. Expand domain-rule checks while keeping plan-only safety.
4. Add Windows CAD adapter boundary tests without live execution.
