# HS-CAD Phase 12 Manual Live Execution Candidate Patch

## Intended local path

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-phase12-manual-live-execution-candidate-patch.zip
```

## Apply

From repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin feat/analysis-phase10-11-domain-copy-validation
git switch feat/analysis-phase10-11-domain-copy-validation
git switch -c feat/analysis-phase12-manual-live-execution-candidate

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase12-manual-live-execution-candidate-patch.zip" -DestinationPath ".\_phase12_patch" -Force
Copy-Item -Path ".\_phase12_patch\*" -Destination "." -Recurse -Force
```

## Optional manual registration

See:

```text
MAIN_IMPORT_PHASE12_PATCH.txt
config/worker_manifest.phase12.patch.json
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase12_manual_live_execution_candidate.py
python -X utf8 -m src.main --help
```

## Safety

This patch does not execute CAD, ZWCAD COM, SendCommand, Domain Rule command execution, or XiCAD aliases.
