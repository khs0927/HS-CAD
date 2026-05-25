# HS-CAD Final TODO Integration Readiness Bundle

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-final-todo-integration-readiness-bundle.zip
```

## Apply

From repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin feat/analysis-phase12-manual-live-execution-candidate
git switch feat/analysis-phase12-manual-live-execution-candidate
git switch -c integration/final-todo-readiness

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-final-todo-integration-readiness-bundle.zip" -DestinationPath ".\_final_todo_patch" -Force
Copy-Item -Path ".\_final_todo_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_final_todo_integration_readiness.py
python -X utf8 -m src.main --help
```

## Safety

This bundle does not execute CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases. It only creates final readiness reports.
