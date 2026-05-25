# HS-CAD PR55 Main-ready Review-only Integration Validation Prompt

## Context

PR #55 is complete and open:

- Branch: `integration/main-merge-readiness-decision`
- PR URL: https://github.com/khs0927/HS-CAD/pull/55
- Decision status: `ready_for_human_main_merge_review`
- Full pytest: `200 passed, 16 skipped`
- ruff: E9,F63,F7,F82,F821 all passed
- CLI smoke: `src.main --help` and `hscad-main-merge-readiness-decision` passed
- Safety: no SendCommand/CAD execution/original DWG mutation/final live runner

## Goal

Create a main-ready review-only validation branch that merges PR #55 into a main-based integration branch and validates it without pushing to main.

This patch adds a validator/report helper. It does not merge main and does not execute CAD.

## Branch flow

```powershell
cd C:\CODE\HS-CAD
git fetch origin
git switch main
git pull --ff-only
git switch -c integration/main-ready-review-only-pipeline
git merge --no-ff origin/integration/main-merge-readiness-decision
```

If merge conflicts occur, stop and report conflicts. Do not auto-resolve risky conflicts.

## Apply patch ZIP

Save ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-pr55-main-ready-review-only-validation.zip
```

Apply:

```powershell
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-pr55-main-ready-review-only-validation.zip" -DestinationPath ".\_pr55_main_ready_patch" -Force
Copy-Item -Path ".\_pr55_main_ready_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included:

```python
import src.app.pr55_main_ready_cli  # noqa: F401,E402
```

## Required validation

```powershell
python -X utf8 -m compileall -q src tests
python -X utf8 -m ruff check src tests --select E9,F63,F7,F82,F821
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
python -X utf8 -m src.main hscad-main-merge-readiness-decision --out-dir outputs\main_ready_review_only_verify
```

If CLI registration for this patch was added:

```powershell
python -X utf8 -m src.main hscad-pr55-main-ready-validation --repo-root . --out-dir outputs\pr55_main_ready_review_only_validation
```

Expected helper artifacts:

```text
PR55_MAIN_READY_REVIEW_ONLY_VALIDATION.json
PR55_MAIN_READY_REVIEW_ONLY_VALIDATION.md
PR55_MAIN_READY_CHECKLIST.json
```

## Safety checks

Confirm:

- no main push
- no CAD execution
- no ZWCAD COM SendCommand
- no XiCAD alias execution
- no Domain Rule command execution
- no original DWG mutation
- no final live runner implementation
- outputs/** not committed
- DWG/DXF not committed

## Commit

Commit only the helper/report files and the final validation report.

```powershell
git add src/analysis/pr55_main_ready_review_only_validator.py
git add src/workers/pr55_main_ready_review_only_validation_worker.py
git add src/app/pr55_main_ready_cli.py
git add tests/test_pr55_main_ready_review_only_validation.py
git add docs/101_main_ready_review_only_integration_prompt.md
git add docs/102_main_ready_review_only_integration_report.md
git add config/worker_manifest.pr55_main_ready.patch.json
git add MAIN_IMPORT_PR55_MAIN_READY_PATCH.txt
git add README_APPLY_PR55_MAIN_READY.md

git commit -m "chore: add PR55 main-ready review-only validation helper"
git push -u origin integration/main-ready-review-only-pipeline
```

## PR

Base:

```text
main
```

Head:

```text
integration/main-ready-review-only-pipeline
```

Title:

```text
Validate PR55 main-ready review-only integration
```
