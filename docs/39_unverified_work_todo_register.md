# HS-CAD unverified work TODO register

This document records work that has not yet been independently verified. Keep it
updated whenever a new experimental branch is created or validated.

## Verified branches

| PR | Branch | Status | Evidence |
|---|---|---|---|
| #26 | `exp/domain-rule-engines` | verified / ready for review | Reported: `tests/test_domain_rule_engines.py` 5 passed, full pytest 160 passed / 16 skipped, CLI and local XiCAD optional checks passed |
| #28 | `exp/domain-rule-decision-workflows` | verified / ready for review | Reported: targeted tests 10 passed, full pytest 165 passed / 16 skipped, CLI and artifact checks passed |
| #30 | `exp/domain-rule-command-plans` | verified / ready for review | Reported: full pytest 169 passed / 16 skipped, CLI chained execution and artifact structure passed |
| #31 | `exp/domain-rule-review-gates` | verified / ready for review | Reported: full pytest 173 passed / 16 skipped, CLI chained execution, review gate and sign-off manifest structure passed |
| #24 | `exp/isolated-tools-development` | verified / ready for review | Reported: full pytest 163 passed / 16 skipped, CLI mock scan strategy passed |
| #21 | `docs/unused-code-roadmap` | verified / ready for review | Reported: pytest isolated module roadmap passed (1 assertion patch applied) |
| #12 | `fix/main-pr-verify-routing` | verified / ready for review | Reported: pytest import safety passed, CLI main load successful |
| #33 | `exp/domain-rule-safe-execution-harness` | verified / ready for review | Reported: pytest safe execution harness 7 passed, full pytest 180 passed / 16 skipped, chained CLI execution and audit log checks passed |

## Unverified branches and tasks

| PR / Branch | Area | Unverified items | Required validation |
|---|---|---|---|
| (None currently) | - | - | - |

## Policy

- Do not merge an experimental PR until its TODO prompt has been executed.
- Do not push experimental patches to `main`.
- If a validation agent fixes an issue, commit only to the relevant experimental branch.
- Original DWG files must not be modified during validation.
- Review-gated command plans and queue candidates are not execution commands.

## Current next validation priority

(All experimental and base branches currently verified)
