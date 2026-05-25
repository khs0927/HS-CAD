# HS-CAD Phase 4 Metrics / Decision Bridge Validation Prompt

## Goal

Validate Phase 4 bridge from Phase 3 artifact coverage into review-only metrics and decision package candidates.

This phase does not execute CAD commands and does not mutate drawings.

## Branch

```powershell
git fetch origin feat/analysis-phase3-real-data-binding
git switch feat/analysis-phase3-real-data-binding
git switch -c feat/analysis-phase4-metrics-decision-bridge
```

## Apply patch ZIP

Save the ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-phase4-metrics-decision-bridge-patch.zip
```

Apply from repo root:

```powershell
cd C:\CODE\HS-CAD
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase4-metrics-decision-bridge-patch.zip" -DestinationPath ".\_phase4_patch" -Force
Copy-Item -Path ".\_phase4_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included in this PR:

```python
import src.app.analysis_phase4_cli  # noqa: F401,E402
```

Otherwise keep CLI registration separate.

## Targeted tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase4_metrics_decision_bridge.py
python -X utf8 -m src.main --help
```

## Optional CLI smoke

If CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-analysis-phase4-bridge --workspace outputs\phase3_real_data_binding_verify --out-dir outputs\phase4_metrics_decision_bridge_verify
```

Expected outputs:

```text
PHASE4_METRICS_DECISION_BRIDGE.json
PHASE4_METRICS_DECISION_BRIDGE.md
PHASE4_DECISION_BRIDGE_PACKAGE.json
```

## Safety checks

Confirm:

- `source_mutation_allowed` is false
- `cad_execution_allowed` is false
- `zwcad_com_allowed` is false
- `sendcommand_allowed` is false
- `xicad_alias_execution_allowed` is false
- `decision_package_is_review_only` is true

## Full validation

```powershell
python -X utf8 -m pytest -q
```

If full pytest is too expensive, leave it as reviewer TODO.

## Commit

```powershell
git add src/analysis/phase4_metrics_decision_bridge.py
git add src/workers/analysis_phase4_metrics_decision_bridge_worker.py
git add src/app/analysis_phase4_cli.py
git add tests/test_analysis_phase4_metrics_decision_bridge.py
git add docs/76_analysis_phase4_metrics_decision_bridge_prompt.md
git add docs/77_analysis_phase4_metrics_decision_bridge_report.md
git add config/worker_manifest.phase4.patch.json
git add MAIN_IMPORT_PHASE4_PATCH.txt
git add README_APPLY_PHASE4.md

git commit -m "feat: add analysis phase4 metrics decision bridge"
git push -u origin feat/analysis-phase4-metrics-decision-bridge
```

## PR

Base:

```text
feat/analysis-phase3-real-data-binding
```

Head:

```text
feat/analysis-phase4-metrics-decision-bridge
```

Title:

```text
Implement analysis Phase 4 metrics decision bridge
```
