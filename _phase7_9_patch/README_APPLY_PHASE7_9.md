# HS-CAD Phase 7~9 Review Pipeline Bundle Patch

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-phase7-9-review-pipeline-bundle-patch.zip
```

## Apply

From repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin feat/analysis-phase6-domain-rule-workflow-adapter
git switch feat/analysis-phase6-domain-rule-workflow-adapter
git switch -c feat/analysis-phase7-9-review-pipeline-bundle

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase7-9-review-pipeline-bundle-patch.zip" -DestinationPath ".\_phase7_9_patch" -Force
Copy-Item -Path ".\_phase7_9_patch\*" -Destination "." -Recurse -Force
```

## Optional manual registration

See:

```text
MAIN_IMPORT_PHASE7_9_PATCH.txt
config/worker_manifest.phase7_9.patch.json
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase7_9_review_pipeline_bundle.py
python -X utf8 -m src.main --help
```

## Safety

This patch only reads/writes derived JSON/MD artifacts. It does not call CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases.
