# HS-CAD Post-PR53 Main Merge & Local-only Validation Prompt

## Context

PR #53 completed:

- Branch: `integration/main-readiness-local-validation-plan`
- PR URL: https://github.com/khs0927/HS-CAD/pull/53
- Targeted test: `tests/test_main_readiness_local_validation_planner.py`: `3 passed`
- Full test: `194 passed, 16 skipped`
- CLI smoke: `src.main --help` and `hscad-main-readiness-plan` passed
- Main readiness status: `ready_for_main_readiness_review`
- Safety:
  - `final_live_runner_implemented = false`
  - `sendcommand_allowed_by_default = false`
  - `cad_execution_allowed_by_default = false`
  - `local_only_validation_required_before_live_runner = true`

## Goal

Add a Post-PR53 planning layer that prepares:

- main merge human checklist
- local-only validation runbook
- final live runner deferred gate
- PR53 context preservation

This does not execute CAD, ZWCAD COM, SendCommand, XiCAD aliases, or final live runner.

## Branch

```powershell
git fetch origin integration/main-readiness-local-validation-plan
git switch integration/main-readiness-local-validation-plan
git switch -c integration/post-pr53-main-merge-local-validation
```

## Apply patch ZIP

Save the ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-post-pr53-main-merge-local-validation.zip
```

Apply from repo root:

```powershell
cd C:\CODE\HS-CAD
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-post-pr53-main-merge-local-validation.zip" -DestinationPath ".\_post_pr53_patch" -Force
Copy-Item -Path ".\_post_pr53_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included in this PR:

```python
import src.app.post_pr53_main_readiness_cli  # noqa: F401,E402
```

## Targeted tests

```powershell
python -X utf8 -m pytest -q tests/test_post_pr53_main_merge_local_validation.py
python -X utf8 -m src.main --help
```

## Optional CLI smoke

If CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-post-pr53-main-readiness --repo-root . --main-readiness-workspace outputs\main_readiness_local_validation --out-dir outputs\post_pr53_main_merge_local_validation
```

Expected outputs:

```text
POST_PR53_MAIN_MERGE_LOCAL_VALIDATION_PLAN.json
POST_PR53_MAIN_MERGE_LOCAL_VALIDATION_PLAN.md
POST_PR53_LOCAL_ONLY_VALIDATION_STEPS.json
POST_PR53_MAIN_MERGE_HUMAN_CHECKLIST.json
```

## Commit

```powershell
git add src/analysis/post_pr53_main_merge_local_validation.py
git add src/workers/post_pr53_main_merge_local_validation_worker.py
git add src/app/post_pr53_main_readiness_cli.py
git add tests/test_post_pr53_main_merge_local_validation.py
git add docs/96_post_pr53_main_merge_local_validation_prompt.md
git add docs/97_post_pr53_main_merge_local_validation_report.md
git add docs/98_local_only_zwcad_xicad_validation_runbook.md
git add config/worker_manifest.post_pr53.patch.json
git add MAIN_IMPORT_POST_PR53_PATCH.txt
git add README_APPLY_POST_PR53.md

git commit -m "feat: add post PR53 main merge local validation planner"
git push -u origin integration/post-pr53-main-merge-local-validation
```

## PR

Base:

```text
integration/main-readiness-local-validation-plan
```

Head:

```text
integration/post-pr53-main-merge-local-validation
```

Title:

```text
Add post-PR53 main merge local validation planner
```
