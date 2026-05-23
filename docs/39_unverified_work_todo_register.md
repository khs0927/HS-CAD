# HS-CAD unverified work TODO register

This document records work that has not yet been independently verified. Keep it
updated whenever a new experimental branch is created or validated.

## Verified branches

| PR | Branch | Status | Evidence |
|---|---|---|---|
| #26 | `exp/domain-rule-engines` | verified / ready for review | Reported: `tests/test_domain_rule_engines.py` 5 passed, full pytest 160 passed / 16 skipped, CLI and local XiCAD optional checks passed |
| #28 | `exp/domain-rule-decision-workflows` | verified / ready for review | Reported: targeted tests 10 passed, full pytest 165 passed / 16 skipped, CLI and artifact checks passed |

## Unverified branches and tasks

| PR / Branch | Area | Unverified items | Required validation |
|---|---|---|---|
| #30 / `exp/domain-rule-command-plans` | Domain-rule dry-run command plans | command plan models, builder, report renderer, worker, CLI, tests, synthetic artifact generation | Run `docs/38_domain_rule_command_plan_validation_prompt.md` |
| `exp/domain-rule-review-gates` | Review gate / sign-off package | files created after this register in the same branch | Run `docs/40_domain_rule_review_gates_validation_prompt.md` after implementation |
| #24 / `exp/isolated-tools-development` latest state | Experimental CAD backend/scanner tools | later additions after the last reported validation: evidence report, worker, scan strategy, experimental CLI, validation prompt | Run `docs/35_experimental_cad_tools_validation_prompt.md` again |
| #21 / `docs/unused-code-roadmap` | Documentation / import-safety guard for isolated modules | roadmap doc and import-safety tests | Run `pytest -q tests/test_isolated_module_roadmap.py` and full pytest if not already done |
| #12 / `fix/main-pr-verify-routing` | Main CLI/import safety hotfix | optional CLI module skipping, adapter lazy logger imports, import-safety tests | Run PR #12 suggested validation if not already completed on latest branch |

## Policy

- Do not merge an experimental PR until its TODO prompt has been executed.
- Do not push experimental patches to `main`.
- If a validation agent fixes an issue, commit only to the relevant experimental branch.
- Original DWG files must not be modified during validation.
- Review-gated command plans and queue candidates are not execution commands.

## Current next validation priority

1. Validate #30: `exp/domain-rule-command-plans`.
2. Validate this branch after review-gate implementation: `exp/domain-rule-review-gates`.
3. Re-run #24 validation if the experimental CAD scanner/backend line is resumed.
