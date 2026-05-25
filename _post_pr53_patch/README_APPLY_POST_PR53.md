# HS-CAD Post-PR53 Main Merge Local Validation Planner

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-post-pr53-main-merge-local-validation.zip
```

## Apply

From repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin integration/main-readiness-local-validation-plan
git switch integration/main-readiness-local-validation-plan
git switch -c integration/post-pr53-main-merge-local-validation

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-post-pr53-main-merge-local-validation.zip" -DestinationPath ".\_post_pr53_patch" -Force
Copy-Item -Path ".\_post_pr53_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_post_pr53_main_merge_local_validation.py
python -X utf8 -m src.main --help
```

## Safety

This patch does not execute CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases.
