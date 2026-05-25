# HS-CAD Phase 6 Domain Rule Workflow Adapter Patch

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-phase6-domain-rule-workflow-adapter-patch.zip
```

## Apply

From repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin feat/analysis-phase5-domain-rule-decision-bridge
git switch feat/analysis-phase5-domain-rule-decision-bridge
git switch -c feat/analysis-phase6-domain-rule-workflow-adapter

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase6-domain-rule-workflow-adapter-patch.zip" -DestinationPath ".\_phase6_patch" -Force
Copy-Item -Path ".\_phase6_patch\*" -Destination "." -Recurse -Force
```

## Optional manual registration

See:

```text
MAIN_IMPORT_PHASE6_PATCH.txt
config/worker_manifest.phase6.patch.json
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase6_domain_rule_workflow_adapter.py
python -X utf8 -m src.main --help
```

## Safety

This patch only reads/writes derived JSON/MD artifacts. It does not call CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases.
