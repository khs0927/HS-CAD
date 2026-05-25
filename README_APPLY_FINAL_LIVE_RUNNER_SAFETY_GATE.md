# HS-CAD Final Live Runner Safety Spec Gate

## Intended path

```text
C:\Users\user\Downloads\HS-CAD-final-live-runner-safety-spec-gate.zip
```

## Apply

```powershell
cd C:\CODE\HS-CAD
git fetch origin local/post-main-validation-recorder-final-runner-spec
git switch local/post-main-validation-recorder-final-runner-spec
git pull --ff-only
git switch -c design/final-live-runner-safety-spec-gate

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-final-live-runner-safety-spec-gate.zip" -DestinationPath ".\_final_live_runner_safety_gate_patch" -Force
Copy-Item -Path ".\_final_live_runner_safety_gate_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_final_live_runner_safety_spec_gate.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

## Safety

This package does not execute CAD, ZWCAD COM, SendCommand, XiCAD aliases, or final live runner.
