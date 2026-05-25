# HS-CAD Final Live Runner Safety Spec Gate Prompt

## Context

This step follows PR #59 and the local validation recorder branch.

It checks whether the project is ready for a final live runner safety spec review.

It does not implement final live runner.

## Branch

```powershell
git fetch origin local/post-main-validation-recorder-final-runner-spec
git switch local/post-main-validation-recorder-final-runner-spec
git pull --ff-only
git switch -c design/final-live-runner-safety-spec-gate
```

## Apply ZIP

Save ZIP:

```text
C:\Users\user\Downloads\HS-CAD-final-live-runner-safety-spec-gate.zip
```

Apply:

```powershell
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-final-live-runner-safety-spec-gate.zip" -DestinationPath ".\_final_live_runner_safety_gate_patch" -Force
Copy-Item -Path ".\_final_live_runner_safety_gate_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

```python
import src.app.final_live_runner_safety_spec_cli  # noqa: F401,E402
```

## Validate

```powershell
python -X utf8 -m pytest -q tests/test_final_live_runner_safety_spec_gate.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

If CLI registered:

```powershell
python -X utf8 -m src.main hscad-final-live-runner-safety-spec-gate --repo-root . --local-validation-summary-json outputs\local_validation_recorder\LOCAL_VALIDATION_RESULT_SUMMARY.json --out-dir outputs\final_live_runner_safety_spec_gate
```

## Expected outputs

```text
FINAL_LIVE_RUNNER_SAFETY_SPEC_GATE.json
FINAL_LIVE_RUNNER_SAFETY_SPEC_GATE.md
MINIMUM_IMPLEMENTATION_CONSTRAINTS.json
FINAL_LIVE_RUNNER_TEST_MATRIX.json
FINAL_LIVE_RUNNER_SAFETY_SPEC_REVIEW_PROMPT.md
```

## Commit

```powershell
git add src/analysis/final_live_runner_safety_spec_gate.py
git add src/workers/final_live_runner_safety_spec_gate_worker.py
git add src/app/final_live_runner_safety_spec_cli.py
git add tests/test_final_live_runner_safety_spec_gate.py
git add docs/126_final_live_runner_safety_spec_gate_prompt.md
git add docs/127_final_live_runner_safety_spec_gate_report.md
git add config/worker_manifest.final_live_runner_safety_gate.patch.json
git add MAIN_IMPORT_FINAL_LIVE_RUNNER_SAFETY_GATE_PATCH.txt
git add README_APPLY_FINAL_LIVE_RUNNER_SAFETY_GATE.md

git commit -m "design: add final live runner safety spec gate"
git push -u origin design/final-live-runner-safety-spec-gate
```
