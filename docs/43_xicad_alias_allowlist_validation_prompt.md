# Validation prompt for XiCAD alias allowlist

Repository:
khs0927/HS-CAD

Branch:
exp/xicad-alias-allowlist

Base:
exp/zwcad-copy-execution-validation

Goal:
Validate XiCAD alias allowlist classification before any real XiCAD command execution.

Rules:
- Do not execute XiCAD aliases.
- Do not run SendCommand.
- Do not modify DWG files.
- Unknown aliases must be blocked.
- Destructive aliases must be blocked.
- execution_allowed_aliases must remain empty.

Commands:

git fetch origin exp/xicad-alias-allowlist
git switch exp/xicad-alias-allowlist

python -X utf8 -m pytest -q tests/test_xicad_alias_allowlist.py

python -X utf8 -m pytest -q

python -X utf8 -m src.main --help

Confirm CLI:
- xicad-alias-allowlist

Optional chained smoke test:
Use a generated command plan only.

python -X utf8 -m src.main domain-rule-decision-synthetic --out-dir outputs/alias_chain/decision

python -X utf8 -m src.main domain-rule-command-plan --decision-package-json outputs/alias_chain/decision/DOMAIN_RULE_DECISION_PACKAGE.json --out-dir outputs/alias_chain/command_plan

python -X utf8 -m src.main xicad-alias-allowlist --command-plan-json outputs/alias_chain/command_plan/DOMAIN_RULE_COMMAND_PLAN.json --out-dir outputs/alias_chain/alias

Confirm artifacts:
- XICAD_ALIAS_ALLOWLIST_PLAN.json
- XICAD_ALIAS_ALLOWLIST_PLAN.md

Confirm:
- unknown aliases are blocked
- destructive aliases are blocked
- execution_allowed_aliases is []
- no DWG files are modified
- no XiCAD command is executed

Report:
- Branch/commit tested
- Unit test result
- Full pytest result
- CLI result
- Chained smoke result
- Artifact result
- Failures
- Patch required
- PR readiness
