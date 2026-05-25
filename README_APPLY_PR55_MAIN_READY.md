# HS-CAD PR55 Main-ready Review-only Validation Helper

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-pr55-main-ready-review-only-validation.zip
```

## Apply

```powershell
cd C:\CODE\HS-CAD
git fetch origin
git switch main
git pull --ff-only
git switch -c integration/main-ready-review-only-pipeline
git merge --no-ff origin/integration/main-merge-readiness-decision

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-pr55-main-ready-review-only-validation.zip" -DestinationPath ".\_pr55_main_ready_patch" -Force
Copy-Item -Path ".\_pr55_main_ready_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m compileall -q src tests
python -X utf8 -m ruff check src tests --select E9,F63,F7,F82,F821
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

## Safety

This patch does not merge main and does not execute CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases.
