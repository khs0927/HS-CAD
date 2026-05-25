# HS-CAD Phase 10~11 Domain Decision + Copied DWG Validation Patch

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-phase10-11-domain-copy-validation-bundle-patch.zip
```

## Apply

From repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin feat/analysis-phase7-9-review-pipeline-bundle
git switch feat/analysis-phase7-9-review-pipeline-bundle
git switch -c feat/analysis-phase10-11-domain-copy-validation

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase10-11-domain-copy-validation-bundle-patch.zip" -DestinationPath ".\_phase10_11_patch" -Force
Copy-Item -Path ".\_phase10_11_patch\*" -Destination "." -Recurse -Force
```

## Optional manual registration

See:

```text
MAIN_IMPORT_PHASE10_11_PATCH.txt
config/worker_manifest.phase10_11.patch.json
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase10_11_domain_copy_validation_bundle.py
python -X utf8 -m src.main --help
```

## Safety

This patch only reads/writes derived JSON/MD artifacts. It does not call CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases.
