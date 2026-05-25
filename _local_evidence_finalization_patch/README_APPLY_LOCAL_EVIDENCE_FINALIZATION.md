# HS-CAD Local Evidence Finalization + Safety Spec Approval

## Intended path

```text
C:\Users\user\Downloads\HS-CAD-local-evidence-finalization-safety-spec-approval.zip
```

## Apply

```powershell
cd C:\CODE\HS-CAD
git fetch origin local/local-validation-evidence-review
git switch local/local-validation-evidence-review
git pull --ff-only
git switch -c review/local-evidence-finalization-safety-spec-approval

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-local-evidence-finalization-safety-spec-approval.zip" -DestinationPath ".\_local_evidence_finalization_patch" -Force
Copy-Item -Path ".\_local_evidence_finalization_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_local_evidence_finalization_safety_spec_approval.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

## Safety

This package reviews evidence only. It does not execute CAD, PowerShell, SendCommand, XiCAD alias, or final live runner.
