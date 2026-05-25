# HS-CAD Local Validation Operator Handoff Prompt

## Context

PR #62 completed:

- Branch: `local/post-merge-local-validation-execution-pack`
- PR URL: https://github.com/khs0927/HS-CAD/pull/62
- Base: `design/final-live-runner-safety-spec-gate`
- Target test: `4 passed`
- Compileall: passed
- Full pytest: passed
- Ruff: All checks passed
- CLI smoke: passed
- Local validation execution pack status: ready
- Final live runner implementation: not allowed; separate PR required

## Goal

Create a manual operator handoff package for Windows/ZWCAD local validation.

This does not execute CAD and does not run the PowerShell template.

## Branch

```powershell
git fetch origin local/post-merge-local-validation-execution-pack
git switch local/post-merge-local-validation-execution-pack
git pull --ff-only
git switch -c local/local-validation-operator-handoff
```

## Apply ZIP

Save ZIP:

```text
C:\Users\user\Downloads\HS-CAD-local-validation-operator-handoff-pr62.zip
```

Apply:

```powershell
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-local-validation-operator-handoff-pr62.zip" -DestinationPath ".\_local_validation_operator_handoff_patch" -Force
Copy-Item -Path ".\_local_validation_operator_handoff_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

```python
import src.app.local_validation_operator_handoff_cli  # noqa: F401,E402
```

## Validate

```powershell
python -X utf8 -m pytest -q tests/test_local_validation_operator_handoff.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

If CLI registered:

```powershell
python -X utf8 -m src.main hscad-local-validation-operator-handoff --out-dir outputs\local_validation_operator_handoff --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --xicad-root "C:/xicad"
```

## Expected outputs

```text
LOCAL_VALIDATION_OPERATOR_HANDOFF.json
LOCAL_VALIDATION_OPERATOR_HANDOFF.md
LOCAL_VALIDATION_OPERATOR_PROMPT.md
RESULT_FINALIZATION_COMMANDS.json
```

## Commit

```powershell
git add src/analysis/local_validation_operator_handoff.py
git add src/workers/local_validation_operator_handoff_worker.py
git add src/app/local_validation_operator_handoff_cli.py
git add tests/test_local_validation_operator_handoff.py
git add docs/132_local_validation_operator_handoff_prompt.md
git add docs/133_local_validation_operator_handoff_report.md
git add config/worker_manifest.local_validation_operator_handoff.patch.json
git add MAIN_IMPORT_LOCAL_VALIDATION_OPERATOR_HANDOFF_PATCH.txt
git add README_APPLY_LOCAL_VALIDATION_OPERATOR_HANDOFF.md
git add PROMPT_LOCAL_VALIDATION_OPERATOR_HANDOFF_PR62.txt

git commit -m "local: add local validation operator handoff"
git push -u origin local/local-validation-operator-handoff
```
