# HS-CAD Main Merge Operator Review Package

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-main-merge-operator-review.zip
```

## Apply

```powershell
cd C:\CODE\HS-CAD
git fetch origin integration/main-ready-review-only-pipeline
git switch integration/main-ready-review-only-pipeline
git switch -c integration/main-merge-operator-review

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-main-merge-operator-review.zip" -DestinationPath ".\_main_merge_operator_review_patch" -Force
Copy-Item -Path ".\_main_merge_operator_review_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_main_merge_operator_review.py
python -X utf8 -m src.main --help
```

## Safety

This patch does not merge main and does not execute CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases.
