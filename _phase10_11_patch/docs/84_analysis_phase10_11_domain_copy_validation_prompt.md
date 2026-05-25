# HS-CAD Phase 10~11 Domain Decision + Copied DWG Validation Bridge Prompt

## Goal

Apply a bundled Phase 10~11 review-only bridge:

- Phase 10: connect Phase 8/9 review-gated artifacts to Domain Rule Decision CLI planning
- Phase 11: prepare copied-DWG validation plan without opening CAD or mutating files

This bundle does not execute CAD, ZWCAD COM, SendCommand, XiCAD alias, or Domain Rule Command Plan.

## Branch

```powershell
git fetch origin feat/analysis-phase7-9-review-pipeline-bundle
git switch feat/analysis-phase7-9-review-pipeline-bundle
git switch -c feat/analysis-phase10-11-domain-copy-validation
```

## Apply patch ZIP

Save the ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-phase10-11-domain-copy-validation-bundle-patch.zip
```

Apply from repo root:

```powershell
cd C:\CODE\HS-CAD
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase10-11-domain-copy-validation-bundle-patch.zip" -DestinationPath ".\_phase10_11_patch" -Force
Copy-Item -Path ".\_phase10_11_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included in this PR:

```python
import src.app.analysis_phase10_11_cli  # noqa: F401,E402
```

Otherwise keep CLI registration separate.

## Targeted tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase10_11_domain_copy_validation_bundle.py
python -X utf8 -m src.main --help
```

## Optional CLI smoke

If CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-analysis-phase10-11-domain-copy --workspace outputs\phase7_9_review_pipeline_verify --out-dir outputs\phase10_11_domain_copy_verify
```

Expected outputs:

```text
PHASE10_DOMAIN_DECISION_CONNECTOR.json
PHASE10_DOMAIN_DECISION_CONNECTOR.md
PHASE10_DOMAIN_RULE_DECISION_CLI_PLAN.json
PHASE11_COPIED_DWG_VALIDATION_BRIDGE.json
PHASE11_COPIED_DWG_VALIDATION_BRIDGE.md
PHASE11_COPY_VALIDATION_CLI_PLAN.json
```

## Safety checks

Confirm:

- all execution flags are false
- `sendcommand_allowed` is false
- `zwcad_com_allowed` is false
- `original_dwg_mutation_allowed` is false
- `live_execution_allowed` is false
- outputs are not committed
- no DWG/DXF files are committed

## Commit

```powershell
git add src/analysis/phase10_domain_decision_connector.py
git add src/analysis/phase11_copied_dwg_validation_bridge.py
git add src/workers/analysis_phase10_11_domain_copy_validation_worker.py
git add src/app/analysis_phase10_11_cli.py
git add tests/test_analysis_phase10_11_domain_copy_validation_bundle.py
git add docs/84_analysis_phase10_11_domain_copy_validation_prompt.md
git add docs/85_analysis_phase10_11_domain_copy_validation_report.md
git add config/worker_manifest.phase10_11.patch.json
git add MAIN_IMPORT_PHASE10_11_PATCH.txt
git add README_APPLY_PHASE10_11.md

git commit -m "feat: add analysis phase10-11 domain copy validation bridge"
git push -u origin feat/analysis-phase10-11-domain-copy-validation
```

## PR

Base:

```text
feat/analysis-phase7-9-review-pipeline-bundle
```

Head:

```text
feat/analysis-phase10-11-domain-copy-validation
```

Title:

```text
Implement analysis Phase 10-11 domain copy validation bridge
```
