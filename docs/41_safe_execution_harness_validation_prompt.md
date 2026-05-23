# Validation prompt for safe execution harness

You are validating HS-CAD safe execution harness.

Branch:
exp/domain-rule-safe-execution-harness

Base:
exp/domain-rule-review-gates

Goal:
Validate safe dry-run execution package generation without mutating DWG files.

Rules:
- Do not run real ZWCAD command execution.
- Do not modify original DWG.
- Do not execute approved_copy_execution unless explicitly instructed later.
- This validation only checks dry-run and safety blocking behavior.

Commands:

git fetch origin exp/domain-rule-safe-execution-harness
git switch exp/domain-rule-safe-execution-harness

python -X utf8 -m pytest -q tests/test_safe_execution_harness.py

python -X utf8 -m pytest -q

python -X utf8 -m src.main --help

Confirm CLI:
- safe-execution-dry-run

Chained dry-run validation:

1. Generate decision:
python -X utf8 -m src.main domain-rule-decision-synthetic --out-dir outputs/safe_exec_chain/decision

2. Generate command plan:
python -X utf8 -m src.main domain-rule-command-plan --decision-package-json outputs/safe_exec_chain/decision/DOMAIN_RULE_DECISION_PACKAGE.json --out-dir outputs/safe_exec_chain/command_plan

3. Generate review gate:
python -X utf8 -m src.main domain-rule-review-gate --command-plan-json outputs/safe_exec_chain/command_plan/DOMAIN_RULE_COMMAND_PLAN.json --out-dir outputs/safe_exec_chain/review_gate

4. Generate safe execution dry-run:
python -X utf8 -m src.main safe-execution-dry-run --command-plan-json outputs/safe_exec_chain/command_plan/DOMAIN_RULE_COMMAND_PLAN.json --review-gate-json outputs/safe_exec_chain/review_gate/DOMAIN_RULE_REVIEW_GATE.json --signoff-manifest-json outputs/safe_exec_chain/review_gate/DOMAIN_RULE_SIGNOFF_MANIFEST.json --out-dir outputs/safe_exec_chain/safe_execution

Confirm artifacts:
- SAFE_EXECUTION_PACKAGE.json
- SAFE_EXECUTION_DRY_RUN_RESULT.json
- EXECUTION_AUDIT_LOG.json

Confirm:
- SAFE_EXECUTION_PACKAGE.json status is ready_for_dry_run or blocked with clear reason
- SAFE_EXECUTION_DRY_RUN_RESULT.json does not execute CAD
- EXECUTION_AUDIT_LOG.json says original_dwg_mutation_allowed=false
- No DWG file was created, edited, or overwritten

Report:
- Branch/commit tested
- Targeted test result
- Full pytest result
- CLI result
- Chained dry-run result
- Artifact result
- Failures
- Patch required
- PR readiness
