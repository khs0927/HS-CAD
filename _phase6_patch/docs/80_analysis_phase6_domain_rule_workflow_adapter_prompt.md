# HS-CAD Phase 6 Domain Rule Workflow Adapter Validation Prompt

## Goal

Validate Phase 6 adapter from Phase 5 Domain Rule input package into a normalized review-only Domain Rule Decision Workflow input.

This phase does not execute Domain Rule Command Plan, CAD, ZWCAD COM, SendCommand, or XiCAD aliases.

## Branch

```powershell
git fetch origin feat/analysis-phase5-domain-rule-decision-bridge
git switch feat/analysis-phase5-domain-rule-decision-bridge
git switch -c feat/analysis-phase6-domain-rule-workflow-adapter
```

## Apply patch ZIP

Save the ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-phase6-domain-rule-workflow-adapter-patch.zip
```

Apply from repo root:

```powershell
cd C:\CODE\HS-CAD
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase6-domain-rule-workflow-adapter-patch.zip" -DestinationPath ".\_phase6_patch" -Force
Copy-Item -Path ".\_phase6_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included in this PR:

```python
import src.app.analysis_phase6_cli  # noqa: F401,E402
```

Otherwise keep CLI registration separate.

## Targeted tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase6_domain_rule_workflow_adapter.py
python -X utf8 -m src.main --help
```

## Optional CLI smoke

If CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-analysis-phase6-domain-adapter --workspace outputs\phase5_domain_decision_bridge_verify --out-dir outputs\phase6_domain_rule_workflow_adapter_verify
```

Expected outputs:

```text
PHASE6_DOMAIN_RULE_WORKFLOW_ADAPTER.json
PHASE6_DOMAIN_RULE_WORKFLOW_ADAPTER.md
DOMAIN_RULE_DECISION_INPUT_FROM_PHASE6.json
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
- `command_plan_execution_allowed` is false

## Full validation

```powershell
python -X utf8 -m pytest -q
```

If full pytest is too expensive, leave it as reviewer TODO.

## Commit

```powershell
git add src/analysis/phase6_domain_rule_workflow_adapter.py
git add src/workers/analysis_phase6_domain_rule_workflow_adapter_worker.py
git add src/app/analysis_phase6_cli.py
git add tests/test_analysis_phase6_domain_rule_workflow_adapter.py
git add docs/80_analysis_phase6_domain_rule_workflow_adapter_prompt.md
git add docs/81_analysis_phase6_domain_rule_workflow_adapter_report.md
git add config/worker_manifest.phase6.patch.json
git add MAIN_IMPORT_PHASE6_PATCH.txt
git add README_APPLY_PHASE6.md

git commit -m "feat: add analysis phase6 domain rule workflow adapter"
git push -u origin feat/analysis-phase6-domain-rule-workflow-adapter
```

## PR

Base:

```text
feat/analysis-phase5-domain-rule-decision-bridge
```

Head:

```text
feat/analysis-phase6-domain-rule-workflow-adapter
```

Title:

```text
Implement analysis Phase 6 domain rule workflow adapter
```
