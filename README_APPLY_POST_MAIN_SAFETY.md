# HS-CAD Post-main Local Validation + Final Live Runner Safety Bundle

## Intended path

```text
C:\Users\user\Downloads\HS-CAD-post-main-local-validation-live-runner-safety.zip
```

## Apply

```powershell
cd C:\CODE\HS-CAD
git fetch origin integration/main-merge-operator-review
git switch integration/main-merge-operator-review
git switch -c planning/post-main-local-validation-live-runner-safety

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-post-main-local-validation-live-runner-safety.zip" -DestinationPath ".\_post_main_safety_patch" -Force
Copy-Item -Path ".\_post_main_safety_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_post_main_local_validation_live_runner_safety.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

## Safety

No CAD execution, no SendCommand, no XiCAD alias execution, no final live runner implementation.
