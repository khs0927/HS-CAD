# Validation prompt for domain rule review gates

Copy this prompt into the verification agent after fetching `exp/domain-rule-review-gates`.

```text
You are validating the HS-CAD domain rule review gate branch.

Repository: khs0927/HS-CAD
Branch: exp/domain-rule-review-gates
Base branch stack: exp/domain-rule-command-plans

Goal:
Validate the review-gate layer that converts a DOMAIN_RULE_COMMAND_PLAN into a review gate package and sign-off manifest.

Architecture:
- This branch does not execute CAD commands.
- Review gate package only classifies whether a command plan can proceed to dry-run review.
- Execution is still not allowed.
- Original DWG files must not be modified.
- Human approval and SaveAs remain mandatory for any future execution stage.

Tasks:
1. Fetch and checkout.
   - git fetch origin exp/domain-rule-review-gates
   - git switch exp/domain-rule-review-gates

2. Inspect TODO register.
   - docs/39_unverified_work_todo_register.md

3. Inspect review gate files.
   - src/domain_rules/review_gate_models.py
   - src/domain_rules/review_gate_builder.py
   - src/domain_rules/review_gate_report.py
   - src/workers/domain_rule_review_gate_worker.py
   - src/app/domain_rule_review_gate_cli.py
   - tests/test_domain_rule_review_gates.py

4. Run targeted tests.
   - python -X utf8 -m pytest -q tests/test_domain_rule_engines.py tests/test_domain_rule_decision_workflow.py tests/test_domain_rule_command_plans.py tests/test_domain_rule_review_gates.py

5. Run full tests.
   - python -X utf8 -m pytest -q

6. Check CLI registration.
   - python -X utf8 -m src.main --help
   - Confirm commands:
     - domain-rule-pack
     - domain-rule-review-synthetic
     - domain-rule-decision
     - domain-rule-decision-synthetic
     - domain-rule-command-plan
     - domain-rule-command-plan-synthetic
     - domain-rule-review-gate

7. Chained smoke test.
   - python -X utf8 -m src.main domain-rule-decision-synthetic --out-dir outputs/review_gate_chain/decision_source
   - python -X utf8 -m src.main domain-rule-command-plan --decision-package-json outputs/review_gate_chain/decision_source/DOMAIN_RULE_DECISION_PACKAGE.json --out-dir outputs/review_gate_chain/command_plan
   - python -X utf8 -m src.main domain-rule-review-gate --command-plan-json outputs/review_gate_chain/command_plan/DOMAIN_RULE_COMMAND_PLAN.json --out-dir outputs/review_gate_chain/review_gate

8. Confirm artifacts.
   - outputs/review_gate_chain/review_gate/DOMAIN_RULE_REVIEW_GATE.json
   - outputs/review_gate_chain/review_gate/DOMAIN_RULE_REVIEW_GATE.md
   - outputs/review_gate_chain/review_gate/DOMAIN_RULE_SIGNOFF_MANIFEST.json

9. Confirm JSON contains:
   - task
   - source_command_plan
   - status
   - checks
   - signoff_required
   - allowed_next_steps
   - blocked_reasons
   - warnings

10. Confirm Markdown contains:
   - HS-CAD Domain Rule Review Gate
   - Gate checks
   - Required sign-off
   - Safety note
   - Original DWG files must not be modified

11. Update TODO status suggestion.
   - If this branch passes, report that `exp/domain-rule-review-gates` can be marked verified.
   - Do not edit TODO unless asked.

12. Report format:
   - Branch/commit tested:
   - Targeted test result:
   - Full test result:
   - CLI registration result:
   - Chained smoke test result:
   - Artifact verification result:
   - Failures with traceback:
   - Required patches:
   - PR readiness: keep open / patch needed / ready for review

Do not merge the PR. Do not push to main. If a patch is needed, commit only to exp/domain-rule-review-gates.
```
