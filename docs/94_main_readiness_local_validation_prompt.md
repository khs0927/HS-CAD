# HS-CAD Main Readiness & Local-only Validation Planner Prompt

## Goal

Add a planner for the step after final CLI/worker registration and final review pipeline readiness.

This patch creates:

- main readiness checklist
- local-only validation TODO list
- final live runner deferral guard
- main merge readiness plan

This does not execute CAD, ZWCAD COM, SendCommand, XiCAD aliases, or live runner.

## Branch

```powershell
git fetch origin integration/final-review-pipeline-readiness
git switch integration/final-review-pipeline-readiness
git switch -c integration/main-readiness-local-validation-plan
```

If `integration/final-review-pipeline-readiness` does not exist yet, do not apply this patch. Report that final review pipeline readiness PR must be completed first.

## Apply patch ZIP

Save the ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-main-readiness-local-validation-planner.zip
```

Apply from repo root:

```powershell
cd C:\CODE\HS-CAD
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-main-readiness-local-validation-planner.zip" -DestinationPath ".\_main_readiness_patch" -Force
Copy-Item -Path ".\_main_readiness_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included in this PR:

```python
import src.app.main_readiness_cli  # noqa: F401,E402
```

## Targeted tests

```powershell
python -X utf8 -m pytest -q tests/test_main_readiness_local_validation_planner.py
python -X utf8 -m src.main --help
```

## Optional CLI smoke

If CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-main-readiness-plan --repo-root . --final-review-workspace outputs\final_review_pipeline_verify --out-dir outputs\main_readiness_local_validation
```

Expected outputs:

```text
MAIN_READINESS_LOCAL_VALIDATION_PLAN.json
MAIN_READINESS_LOCAL_VALIDATION_PLAN.md
LOCAL_ONLY_VALIDATION_TODO.json
```

## Commit

```powershell
git add src/analysis/main_readiness_local_validation_planner.py
git add src/workers/main_readiness_local_validation_planner_worker.py
git add src/app/main_readiness_cli.py
git add tests/test_main_readiness_local_validation_planner.py
git add docs/94_main_readiness_local_validation_prompt.md
git add docs/95_main_readiness_local_validation_report.md
git add config/worker_manifest.main_readiness.patch.json
git add MAIN_IMPORT_MAIN_READINESS_PATCH.txt
git add README_APPLY_MAIN_READINESS.md

git commit -m "feat: add main readiness local validation planner"
git push -u origin integration/main-readiness-local-validation-plan
```

## PR

Base:

```text
integration/final-review-pipeline-readiness
```

Head:

```text
integration/main-readiness-local-validation-plan
```

Title:

```text
Add main readiness local validation planner
```
