# HS-CAD Local Validation Recorder + Final Runner Safety Spec Prompt

## Context

PR #59 completed:

- Branch: `human/main-merge-review-gate`
- PR URL: https://github.com/khs0927/HS-CAD/pull/59
- Base: `planning/post-main-local-validation-live-runner-safety`
- Targeted test: `tests/test_human_main_merge_review_gate.py` -> `3 passed`
- Compileall: passed
- Full pytest: `227 passed, 16 skipped`
- CLI smoke: `hscad-human-main-merge-review-gate` passed
- Human review judgment: ready yes
- Remaining TODO:
  1. PR #55~#59 human approval and main merge decision
  2. post-main local-only validation
  3. C:/xicad allowlist validation
  4. safety spec review before live runner

## Goal

Create a local validation result recorder and final live runner safety spec seed docs.

This does not execute CAD and does not implement final live runner.

## Branch

```powershell
git fetch origin human/main-merge-review-gate
git switch human/main-merge-review-gate
git pull --ff-only
git switch -c local/post-main-validation-recorder-final-runner-spec
```

## Apply ZIP

Save ZIP:

```text
C:\Users\user\Downloads\HS-CAD-local-validation-recorder-final-runner-safety-spec-pr59.zip
```

Apply:

```powershell
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-local-validation-recorder-final-runner-safety-spec-pr59.zip" -DestinationPath ".\_local_validation_recorder_patch" -Force
Copy-Item -Path ".\_local_validation_recorder_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

```python
import src.app.local_validation_recorder_cli  # noqa: F401,E402
```

## Validate

```powershell
python -X utf8 -m pytest -q tests/test_local_validation_recorder_final_runner_safety.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

If CLI registered:

```powershell
python -X utf8 -m src.main hscad-local-validation-recorder --repo-root . --result-dir outputs\local_validation_results --out-dir outputs\local_validation_recorder --create-templates
```

## Expected outputs

```text
LOCAL_VALIDATION_RESULT_SUMMARY.json
LOCAL_VALIDATION_RESULT_SUMMARY.md
FINAL_LIVE_RUNNER_IMPLEMENTATION_GATE.json
PR59_CONTEXT_FOR_LOCAL_VALIDATION.json
LOCAL_01_COPIED_DWG_SCAN_RESULT.json
LOCAL_02_COPIED_DWG_SAVEAS_RESULT.json
LOCAL_03_XICAD_POLICY_CANDIDATES_RESULT.json
LOCAL_04_PHASE12_CANDIDATE_GUARD_RESULT.json
```

## Commit

```powershell
git add src/analysis/local_validation_recorder_final_runner_safety.py
git add src/workers/local_validation_recorder_final_runner_safety_worker.py
git add src/app/local_validation_recorder_cli.py
git add tests/test_local_validation_recorder_final_runner_safety.py
git add docs/118_final_live_runner_safety_spec.md
git add docs/119_final_live_runner_execution_policy.md
git add docs/120_final_live_runner_test_plan.md
git add docs/121_final_live_runner_risk_register.md
git add docs/122_final_live_runner_manual_copy_only_interface.md
git add docs/123_local_validation_recorder_prompt.md
git add docs/124_local_validation_recorder_result.md
git add config/worker_manifest.local_validation_recorder.patch.json
git add MAIN_IMPORT_LOCAL_VALIDATION_RECORDER_PATCH.txt
git add README_APPLY_LOCAL_VALIDATION_RECORDER.md

git commit -m "local: add validation recorder and final runner safety spec seed"
git push -u origin local/post-main-validation-recorder-final-runner-spec
```
