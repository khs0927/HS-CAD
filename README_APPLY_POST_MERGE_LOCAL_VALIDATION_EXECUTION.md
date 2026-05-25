# HS-CAD Post-merge Local Validation Execution Pack

## Intended path

```text
C:\Users\user\Downloads\HS-CAD-post-merge-local-validation-execution-pack-pr61.zip
```

## Apply

```powershell
cd C:\CODE\HS-CAD
git fetch origin design/final-live-runner-safety-spec-gate
git switch design/final-live-runner-safety-spec-gate
git pull --ff-only
git switch -c local/post-merge-local-validation-execution-pack

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-post-merge-local-validation-execution-pack-pr61.zip" -DestinationPath ".\_post_merge_local_validation_pack_patch" -Force
Copy-Item -Path ".\_post_merge_local_validation_pack_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_post_merge_local_validation_execution_pack.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

## Safety

This package does not execute CAD, ZWCAD COM, SendCommand, XiCAD aliases, or final live runner.
