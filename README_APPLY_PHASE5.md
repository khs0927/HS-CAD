# HS-CAD Phase 5 Domain Rule Decision Bridge Patch

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-phase5-domain-rule-decision-bridge-patch.zip
```

## Apply

From repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin feat/analysis-phase4-metrics-decision-bridge
git switch feat/analysis-phase4-metrics-decision-bridge
git switch -c feat/analysis-phase5-domain-rule-decision-bridge

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase5-domain-rule-decision-bridge-patch.zip" -DestinationPath ".\_phase5_patch" -Force
Copy-Item -Path ".\_phase5_patch\*" -Destination "." -Recurse -Force
```

## Optional manual registration

See:

```text
MAIN_IMPORT_PHASE5_PATCH.txt
config/worker_manifest.phase5.patch.json
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase5_domain_rule_decision_bridge.py
python -X utf8 -m src.main --help
```

## Safety

This patch only reads/writes derived JSON/MD artifacts. It does not call CAD, ZWCAD COM, SendCommand, or XiCAD aliases.
