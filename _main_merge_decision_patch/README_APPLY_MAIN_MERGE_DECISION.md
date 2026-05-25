# HS-CAD Main Merge Readiness Decision Package

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-main-merge-readiness-decision.zip
```

## Apply

From repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin integration/post-pr53-main-merge-local-validation
git switch integration/post-pr53-main-merge-local-validation
git switch -c integration/main-merge-readiness-decision

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-main-merge-readiness-decision.zip" -DestinationPath ".\_main_merge_decision_patch" -Force
Copy-Item -Path ".\_main_merge_decision_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_main_merge_readiness_decision.py
python -X utf8 -m src.main --help
```

## Safety

This patch does not merge main and does not execute CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases.
