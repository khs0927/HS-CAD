# HS-CAD Post-merge Local Validation Execution Pack Prompt

## Context

PR #61 completed:

- Branch: `design/final-live-runner-safety-spec-gate`
- PR URL: https://github.com/khs0927/HS-CAD/pull/61
- Base: `local/post-main-validation-recorder-final-runner-spec`
- Target test: `4 passed`
- Full pytest: `235 passed, 16 skipped`
- Ruff: `All checks passed`
- CLI smoke: passed
- Gate status: `blocked`, which is expected because local validation summary is missing or not all passed.
- Final live runner decision:
  - safety spec PR can be reviewed = true
  - implementation PR can start = false
  - implementation requires separate PR = true

## Goal

Create a post-merge local validation execution pack.

This pack does not execute CAD. It creates commands, result templates, and a guarded PowerShell template for local Windows/ZWCAD validation.

## Branch

```powershell
git fetch origin design/final-live-runner-safety-spec-gate
git switch design/final-live-runner-safety-spec-gate
git pull --ff-only
git switch -c local/post-merge-local-validation-execution-pack
```

## Apply ZIP

Save ZIP:

```text
C:\Users\user\Downloads\HS-CAD-post-merge-local-validation-execution-pack-pr61.zip
```

Apply:

```powershell
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-post-merge-local-validation-execution-pack-pr61.zip" -DestinationPath ".\_post_merge_local_validation_pack_patch" -Force
Copy-Item -Path ".\_post_merge_local_validation_pack_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

```python
import src.app.post_merge_local_validation_execution_cli  # noqa: F401,E402
```

## Validate

```powershell
python -X utf8 -m pytest -q tests/test_post_merge_local_validation_execution_pack.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

If CLI registered:

```powershell
python -X utf8 -m src.main hscad-post-merge-local-validation-pack --out-dir outputs\post_merge_local_validation_execution_pack --result-template-dir outputs\local_validation_results --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --xicad-root "C:/xicad" --phase12-workspace outputs\phase10_11_domain_copy_verify --alias WAL
```

## Expected outputs

```text
POST_MERGE_LOCAL_VALIDATION_EXECUTION_PACK.json
POST_MERGE_LOCAL_VALIDATION_EXECUTION_PACK.md
RUN_LOCAL_VALIDATION_COMMANDS.template.ps1
LOCAL_VALIDATION_RESULT_SCHEMA.json
LOCAL_01_COPIED_DWG_SCAN_RESULT.json
LOCAL_02_COPIED_DWG_SAVEAS_RESULT.json
LOCAL_03_XICAD_POLICY_CANDIDATES_RESULT.json
LOCAL_04_PHASE12_CANDIDATE_GUARD_RESULT.json
```

## Important

Outputs are generated under `outputs/**`; do not commit them.

The PowerShell script refuses to run unless `-ConfirmRun` is passed. Before running it, manually verify:

- original_dwg is the real original and must not be mutated
- working_copy_dwg is a copy
- save_as_target is distinct
- ZWCAD is installed
- C:/xicad exists if policy validation is required

## Commit

```powershell
git add src/analysis/post_merge_local_validation_execution_pack.py
git add src/workers/post_merge_local_validation_execution_worker.py
git add src/app/post_merge_local_validation_execution_cli.py
git add tests/test_post_merge_local_validation_execution_pack.py
git add docs/129_post_merge_local_validation_execution_prompt.md
git add docs/130_post_merge_local_validation_execution_report.md
git add config/worker_manifest.post_merge_local_validation_execution.patch.json
git add MAIN_IMPORT_POST_MERGE_LOCAL_VALIDATION_EXECUTION_PATCH.txt
git add README_APPLY_POST_MERGE_LOCAL_VALIDATION_EXECUTION.md
git add PROMPT_POST_MERGE_LOCAL_VALIDATION_EXECUTION_PR61.txt

git commit -m "local: add post-merge local validation execution pack"
git push -u origin local/post-merge-local-validation-execution-pack
```
