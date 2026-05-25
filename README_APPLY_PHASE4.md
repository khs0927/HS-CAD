# HS-CAD Phase 4 Metrics / Decision Bridge Patch

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-phase4-metrics-decision-bridge-patch.zip
```

## Apply

From repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin feat/analysis-phase3-real-data-binding
git switch feat/analysis-phase3-real-data-binding
git switch -c feat/analysis-phase4-metrics-decision-bridge

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase4-metrics-decision-bridge-patch.zip" -DestinationPath ".\_phase4_patch" -Force
Copy-Item -Path ".\_phase4_patch\*" -Destination "." -Recurse -Force
```

## Optional manual registration

See:

```text
MAIN_IMPORT_PHASE4_PATCH.txt
config/worker_manifest.phase4.patch.json
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase4_metrics_decision_bridge.py
python -X utf8 -m src.main --help
```

## Safety

This patch only reads/writes derived JSON/MD artifacts. It does not call CAD, ZWCAD COM, SendCommand, or XiCAD aliases.
