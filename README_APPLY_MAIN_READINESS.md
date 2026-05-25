# HS-CAD Main Readiness Local Validation Planner

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-main-readiness-local-validation-planner.zip
```

## Apply

From repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin integration/final-review-pipeline-readiness
git switch integration/final-review-pipeline-readiness
git switch -c integration/main-readiness-local-validation-plan

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-main-readiness-local-validation-planner.zip" -DestinationPath ".\_main_readiness_patch" -Force
Copy-Item -Path ".\_main_readiness_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_main_readiness_local_validation_planner.py
python -X utf8 -m src.main --help
```

## Safety

This patch does not execute CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases.
