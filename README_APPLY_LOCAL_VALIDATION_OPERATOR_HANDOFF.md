# HS-CAD Local Validation Operator Handoff PR62

## Intended path

```text
C:\Users\user\Downloads\HS-CAD-local-validation-operator-handoff-pr62.zip
```

## Apply

```powershell
cd C:\CODE\HS-CAD
git fetch origin local/post-merge-local-validation-execution-pack
git switch local/post-merge-local-validation-execution-pack
git pull --ff-only
git switch -c local/local-validation-operator-handoff

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-local-validation-operator-handoff-pr62.zip" -DestinationPath ".\_local_validation_operator_handoff_patch" -Force
Copy-Item -Path ".\_local_validation_operator_handoff_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_local_validation_operator_handoff.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

## Safety

This package only creates operator handoff artifacts. It does not execute CAD or PowerShell.
