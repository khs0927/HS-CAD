# Validation prompt for domain rule decision workflows

Copy this prompt into the verification agent after fetching `exp/domain-rule-decision-workflows`.

```text
You are validating the HS-CAD domain rule decision workflow branch.

Repository: khs0927/HS-CAD
Branch: exp/domain-rule-decision-workflows
Base branch stack: exp/domain-rule-engines

Goal:
Validate the new workflow that converts analyzed drawing object JSON into a domain-rule-based modification decision package.

Architecture:
- XiCAD / ArchiOffice / HS-Steel are the rule authority.
- ZWCAD COM is only the execution channel.
- The output of this workflow is not a mutation. It is a review package for deciding what can be modified.
- Original DWG files must not be modified.

Tasks:
1. Fetch and checkout.
   - git fetch origin exp/domain-rule-decision-workflows
   - git switch exp/domain-rule-decision-workflows

2. Inspect files.
   - src/domain_rules/decision_models.py
   - src/domain_rules/decision_engine.py
   - src/domain_rules/decision_report.py
   - src/workers/domain_rule_decision_worker.py
   - src/app/domain_rule_decision_cli.py
   - tests/test_domain_rule_decision_workflow.py

3. Run targeted tests.
   - python -X utf8 -m pytest -q tests/test_domain_rule_engines.py tests/test_domain_rule_decision_workflow.py

4. Run full tests.
   - python -X utf8 -m pytest -q

5. Check CLI registration.
   - python -X utf8 -m src.main --help
   - Confirm commands:
     - domain-rule-pack
     - domain-rule-review-synthetic
     - domain-rule-decision
     - domain-rule-decision-synthetic

6. Run synthetic decision CLI.
   - python -X utf8 -m src.main domain-rule-decision-synthetic --out-dir outputs/domain_rule_decision_synthetic_verify

7. Confirm artifacts.
   - outputs/domain_rule_decision_synthetic_verify/synthetic_objects.json
   - outputs/domain_rule_decision_synthetic_verify/DOMAIN_RULE_DECISION_PACKAGE.json
   - outputs/domain_rule_decision_synthetic_verify/DOMAIN_RULE_DECISION_PACKAGE.md
   - outputs/domain_rule_decision_synthetic_verify/SYSTEM_DRAFTING_CONSTRAINTS.txt

8. Confirm JSON contains:
   - task
   - source
   - status
   - decisions
   - blocked_reasons
   - required_evidence
   - review_checklist
   - system_prompt
   - warnings

9. Confirm Markdown contains:
   - HS-CAD Modification Decision Package
   - Decisions
   - Review checklist
   - System drafting constraints

10. Optional real objects JSON test.
   - Use a copied/generated objects.json only.
   - Do not mutate original DWG.
   - python -X utf8 -m src.main domain-rule-decision --objects-json outputs/architecture_report/objects.json --out-dir outputs/domain_rule_decision_verify

11. Report format:
   - Branch/commit tested:
   - Targeted test result:
   - Full test result:
   - CLI registration result:
   - Synthetic decision CLI result:
   - Artifact verification result:
   - Optional objects JSON result:
   - Failures with traceback:
   - Required patches:
   - PR readiness: keep open / patch needed / ready for review

Do not merge the PR. Do not push to main. If a patch is needed, commit only to exp/domain-rule-decision-workflows.
```
