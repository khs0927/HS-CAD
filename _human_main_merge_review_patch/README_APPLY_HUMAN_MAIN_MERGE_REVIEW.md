# HS-CAD Human Main Merge Review Gate

## Intended path

```text
C:\Users\user\Downloads\HS-CAD-human-main-merge-review-gate.zip
```

## Apply

```powershell
cd C:\CODE\HS-CAD
git fetch origin planning/post-main-local-validation-live-runner-safety
git switch planning/post-main-local-validation-live-runner-safety
git switch -c human/main-merge-review-gate

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-human-main-merge-review-gate.zip" -DestinationPath ".\_human_main_merge_review_patch" -Force
Copy-Item -Path ".\_human_main_merge_review_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_human_main_merge_review_gate.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

## Safety

This package does not merge main and does not execute CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases.
