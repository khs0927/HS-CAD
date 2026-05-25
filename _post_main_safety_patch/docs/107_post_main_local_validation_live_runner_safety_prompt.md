# HS-CAD Post-main Local Validation + Final Live Runner Safety Bundle Prompt

## Context

This step follows PR #56 and the main merge operator review package.

The goal is to merge multiple next-step planning tasks:

1. Main merge operator prompt
2. Post-main Windows/ZWCAD local validation runbook
3. C:/xicad allowlist validation runbook
4. Final live runner safety requirements
5. Final live runner risk register
6. Safety spec PR prompt

This step does not merge main, does not execute CAD, and does not implement final live runner.

## Branch

```powershell
git fetch origin integration/main-merge-operator-review
git switch integration/main-merge-operator-review
git switch -c planning/post-main-local-validation-live-runner-safety
```

If `integration/main-merge-operator-review` does not exist, use `integration/main-ready-review-only-pipeline` as base and record the reason.

## Apply ZIP

Save ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-post-main-local-validation-live-runner-safety.zip
```

Apply:

```powershell
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-post-main-local-validation-live-runner-safety.zip" -DestinationPath ".\_post_main_safety_patch" -Force
Copy-Item -Path ".\_post_main_safety_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` if desired:

```python
import src.app.post_main_local_validation_cli  # noqa: F401,E402
```

## Validation

```powershell
python -X utf8 -m pytest -q tests/test_post_main_local_validation_live_runner_safety.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

If CLI was registered:

```powershell
python -X utf8 -m src.main hscad-post-main-local-validation-plan --repo-root . --operator-review-workspace outputs\main_merge_operator_review --out-dir outputs\post_main_local_validation_live_runner_safety
```

## Expected outputs

```text
POST_MAIN_LOCAL_VALIDATION_LIVE_RUNNER_SAFETY_BUNDLE.json
POST_MAIN_LOCAL_VALIDATION_LIVE_RUNNER_SAFETY_BUNDLE.md
POST_MAIN_LOCAL_VALIDATION_COMMANDS.json
FINAL_LIVE_RUNNER_SAFETY_REQUIREMENTS.json
FINAL_LIVE_RUNNER_RISK_REGISTER.json
MAIN_MERGE_OPERATOR_PROMPT.md
POST_MAIN_LOCAL_VALIDATION_PROMPT.md
FINAL_LIVE_RUNNER_SAFETY_SPEC_PROMPT.md
```

## Commit

```powershell
git add src/analysis/post_main_local_validation_live_runner_safety.py
git add src/workers/post_main_local_validation_live_runner_safety_worker.py
git add src/app/post_main_local_validation_cli.py
git add tests/test_post_main_local_validation_live_runner_safety.py
git add docs/107_post_main_local_validation_live_runner_safety_prompt.md
git add docs/108_post_main_local_validation_live_runner_safety_report.md
git add docs/109_post_main_local_validation_runbook.md
git add docs/110_final_live_runner_safety_spec_seed.md
git add docs/111_final_live_runner_risk_register_seed.md
git add config/worker_manifest.post_main_safety.patch.json
git add MAIN_IMPORT_POST_MAIN_SAFETY_PATCH.txt
git add README_APPLY_POST_MAIN_SAFETY.md

git commit -m "planning: add post-main local validation and live runner safety bundle"
git push -u origin planning/post-main-local-validation-live-runner-safety
```

## PR

Base:

```text
integration/main-merge-operator-review
```

Head:

```text
planning/post-main-local-validation-live-runner-safety
```

Title:

```text
Plan post-main local validation and final live runner safety
```
