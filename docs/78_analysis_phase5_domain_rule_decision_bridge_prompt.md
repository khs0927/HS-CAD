# HS-CAD Phase 5 Domain Rule Decision Bridge Validation Prompt

## Goal

Validate Phase 5 bridge from Phase 4 metrics/decision candidates into a review-only Domain Rule Decision input package.

This phase does not run Domain Rule execution, CAD, ZWCAD COM, SendCommand, or XiCAD aliases.

## Branch

```powershell
git fetch origin feat/analysis-phase4-metrics-decision-bridge
git switch feat/analysis-phase4-metrics-decision-bridge
git switch -c feat/analysis-phase5-domain-rule-decision-bridge
```

## Apply patch ZIP

Save the ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-phase5-domain-rule-decision-bridge-patch.zip
```

Apply from repo root:

```powershell
cd C:\CODE\HS-CAD
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase5-domain-rule-decision-bridge-patch.zip" -DestinationPath ".\_phase5_patch" -Force
Copy-Item -Path ".\_phase5_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included in this PR:

```python
import src.app.analysis_phase5_cli  # noqa: F401,E402
```

Otherwise keep CLI registration separate.

## Targeted tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase5_domain_rule_decision_bridge.py
python -X utf8 -m src.main --help
```

## Optional CLI smoke

If CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-analysis-phase5-domain-bridge --workspace outputs\phase4_metrics_decision_bridge_verify --out-dir outputs\phase5_domain_decision_bridge_verify
```

Expected outputs:

```text
PHASE5_DOMAIN_DECISION_BRIDGE.json
PHASE5_DOMAIN_DECISION_BRIDGE.md
PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json
```

## Safety checks

Confirm:

- `source_mutation_allowed` is false
- `cad_execution_allowed` is false
- `zwcad_com_allowed` is false
- `sendcommand_allowed` is false
- `xicad_alias_execution_allowed` is false
- `execution_allowed` is false
- `domain_rule_review_only` is true

## Full validation

```powershell
python -X utf8 -m pytest -q
```

If full pytest is too expensive, leave it as reviewer TODO.

## Commit

```powershell
git add src/analysis/phase5_domain_rule_decision_bridge.py
git add src/workers/analysis_phase5_domain_rule_decision_bridge_worker.py
git add src/app/analysis_phase5_cli.py
git add tests/test_analysis_phase5_domain_rule_decision_bridge.py
git add docs/78_analysis_phase5_domain_rule_decision_bridge_prompt.md
git add docs/79_analysis_phase5_domain_rule_decision_bridge_report.md
git add config/worker_manifest.phase5.patch.json
git add MAIN_IMPORT_PHASE5_PATCH.txt
git add README_APPLY_PHASE5.md

git commit -m "feat: add analysis phase5 domain rule decision bridge"
git push -u origin feat/analysis-phase5-domain-rule-decision-bridge
```

## PR

Base:

```text
feat/analysis-phase4-metrics-decision-bridge
```

Head:

```text
feat/analysis-phase5-domain-rule-decision-bridge
```

Title:

```text
Implement analysis Phase 5 domain rule decision bridge
```
