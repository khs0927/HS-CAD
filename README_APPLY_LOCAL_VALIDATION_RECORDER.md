# HS-CAD Local Validation Recorder + Final Runner Safety Spec

## Intended path

```text
C:\Users\user\Downloads\HS-CAD-local-validation-recorder-final-runner-safety-spec-pr59.zip
```

## Apply

```powershell
cd C:\CODE\HS-CAD
git fetch origin human/main-merge-review-gate
git switch human/main-merge-review-gate
git pull --ff-only
git switch -c local/post-main-validation-recorder-final-runner-spec

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-local-validation-recorder-final-runner-safety-spec-pr59.zip" -DestinationPath ".\_local_validation_recorder_patch" -Force
Copy-Item -Path ".\_local_validation_recorder_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_local_validation_recorder_final_runner_safety.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

## Safety

This package records validation results only. It does not execute CAD, ZWCAD COM, SendCommand, XiCAD aliases, or final live runner.
