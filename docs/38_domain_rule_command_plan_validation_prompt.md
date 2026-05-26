# Validation prompt for domain rule command plans

Copy this prompt into the verification agent after fetching `exp/domain-rule-command-plans`.

```text
You are validating the HS-CAD domain rule command plan branch.

Repository: khs0927/HS-CAD
Branch: exp/domain-rule-command-plans
Base branch stack: exp/domain-rule-decision-workflows

Goal:
Validate the workflow that converts a DOMAIN_RULE_DECISION_PACKAGE into a dry-run command plan, review table, and execution queue candidate.

Architecture:
- XiCAD / ArchiOffice / HS-Steel are the rule authority.
- ZWCAD COM is only the execution channel.
- This workflow must not mutate DWG files.
- Output is a review-gated dry-run plan only.
- Execution queue candidate is not an execution command.

Tasks:
1. Fetch and checkout.
   - git fetch origin exp/domain-rule-command-plans
   - git switch exp/domain-rule-command-plans

2. Inspect files.
   - src/domain_rules/command_plan_models.py
   - src/domain_rules/command_plan_builder.py
   - src/domain_rules/command_plan_report.py
   - src/workers/domain_rule_command_plan_worker.py
   - src/app/domain_rule_command_plan_cli.py
   - tests/test_domain_rule_command_plans.py

3. Run targeted tests.
   - python -X utf8 -m pytest -q tests/test_domain_rule_engines.py tests/test_domain_rule_decision_workflow.py tests/test_domain_rule_command_plans.py

4. Run full tests.
   - python -X utf8 -m pytest -q

5. Check CLI registration.
   - python -X utf8 -m src.main --help
   - Confirm commands:
     - domain-rule-pack
     - domain-rule-review-synthetic
     - domain-rule-decision
     - domain-rule-decision-synthetic
     - domain-rule-command-plan
     - domain-rule-command-plan-synthetic

6. Run synthetic command plan CLI.
   - python -X utf8 -m src.main domain-rule-command-plan-synthetic --out-dir outputs/domain_rule_command_plan_synthetic_verify

7. Confirm artifacts.
   - outputs/domain_rule_command_plan_synthetic_verify/synthetic_objects.json
   - outputs/domain_rule_command_plan_synthetic_verify/decision/DOMAIN_RULE_DECISION_PACKAGE.json
   - outputs/domain_rule_command_plan_synthetic_verify/command_plan/DOMAIN_RULE_COMMAND_PLAN.json
   - outputs/domain_rule_command_plan_synthetic_verify/command_plan/DOMAIN_RULE_COMMAND_PLAN.md
   - outputs/domain_rule_command_plan_synthetic_verify/command_plan/DOMAIN_RULE_REVIEW_TABLE.json
   - outputs/domain_rule_command_plan_synthetic_verify/command_plan/DOMAIN_RULE_EXECUTION_QUEUE_CANDIDATE.json

8. Confirm JSON contains:
   - task
   - source_decision_package
   - status
   - dry_run_steps
   - review_table
   - execution_queue_candidate
   - blocked_reasons
   - warnings

9. Confirm Markdown contains:
   - HS-CAD Domain Rule Command Plan
   - Safety posture
   - Dry-run steps
   - Review table
   - Execution queue candidate
   - Original DWG must not be mutated

10. Optional chained real object test.
   - Use a copied/generated objects.json only.
   - Do not mutate original DWG.
   - Run domain-rule-decision first.
   - Then run domain-rule-command-plan with the generated DOMAIN_RULE_DECISION_PACKAGE.json.

11. Report format:
   - Branch/commit tested:
   - Targeted test result:
   - Full test result:
   - CLI registration result:
   - Synthetic command plan CLI result:
   - Artifact verification result:
   - Optional chained objects JSON result:
   - Failures with traceback:
   - Required patches:
   - PR readiness: keep open / patch needed / ready for review

Do not merge the PR. Do not push to main. If a patch is needed, commit only to exp/domain-rule-command-plans.
```
