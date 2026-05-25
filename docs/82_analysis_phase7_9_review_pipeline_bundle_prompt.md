# HS-CAD Phase 7~9 Review Pipeline Bundle Validation Prompt

## Goal

Apply a bundled Phase 7~9 review-only pipeline:

- Phase 7: Domain decision package bridge
- Phase 8: Review gate / signoff / safe execution dry-run stub
- Phase 9: Pipeline readiness summary

This bundle does not execute CAD, ZWCAD COM, SendCommand, XiCAD alias, or Domain Rule Command Plan.

## Branch

```powershell
git fetch origin feat/analysis-phase6-domain-rule-workflow-adapter
git switch feat/analysis-phase6-domain-rule-workflow-adapter
git switch -c feat/analysis-phase7-9-review-pipeline-bundle
```

## Apply patch ZIP

Save the ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-phase7-9-review-pipeline-bundle-patch.zip
```

Apply from repo root:

```powershell
cd C:\CODE\HS-CAD
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase7-9-review-pipeline-bundle-patch.zip" -DestinationPath ".\_phase7_9_patch" -Force
Copy-Item -Path ".\_phase7_9_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included in this PR:

```python
import src.app.analysis_phase7_9_cli  # noqa: F401,E402
```

Otherwise keep CLI registration separate.

## Targeted tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase7_9_review_pipeline_bundle.py
python -X utf8 -m src.main --help
```

## Optional CLI smoke

If CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-analysis-phase7-9-review-bundle --workspace outputs\phase6_domain_rule_workflow_adapter_verify --out-dir outputs\phase7_9_review_pipeline_verify
```

Expected outputs:

```text
PHASE7_DOMAIN_DECISION_PACKAGE.json
PHASE7_DOMAIN_DECISION_PACKAGE.md
PHASE8_REVIEW_GATE_CHAIN.json
PHASE8_COMMAND_PLAN.json
PHASE8_REVIEW_GATE.json
PHASE8_SIGNOFF_MANIFEST.json
PHASE8_SAFE_EXECUTION_STUB.json
PHASE9_PIPELINE_READINESS_SUMMARY.json
PHASE9_PIPELINE_READINESS_SUMMARY.md
```

## Safety checks

Confirm:

- all execution flags are false
- `operator_approved` is false
- `sendcommand_allowed` is false
- `ready_for_live_execution` is false
- outputs are not committed
- no DWG/DXF files are committed

## Commit

```powershell
git add src/analysis/phase7_domain_decision_package_bridge.py
git add src/analysis/phase8_review_gate_chain_bridge.py
git add src/analysis/phase9_pipeline_readiness_summary.py
git add src/workers/analysis_phase7_9_review_pipeline_bundle_worker.py
git add src/app/analysis_phase7_9_cli.py
git add tests/test_analysis_phase7_9_review_pipeline_bundle.py
git add docs/82_analysis_phase7_9_review_pipeline_bundle_prompt.md
git add docs/83_analysis_phase7_9_review_pipeline_bundle_report.md
git add config/worker_manifest.phase7_9.patch.json
git add MAIN_IMPORT_PHASE7_9_PATCH.txt
git add README_APPLY_PHASE7_9.md

git commit -m "feat: add analysis phase7-9 review pipeline bundle"
git push -u origin feat/analysis-phase7-9-review-pipeline-bundle
```

## PR

Base:

```text
feat/analysis-phase6-domain-rule-workflow-adapter
```

Head:

```text
feat/analysis-phase7-9-review-pipeline-bundle
```

Title:

```text
Implement analysis Phase 7-9 review pipeline bundle
```
