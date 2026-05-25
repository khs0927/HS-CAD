# Validation prompt for XiCAD policy candidate generator

Repository:
khs0927/HS-CAD

Branch:
exp/xicad-policy-candidate-generator

Base:
exp/xicad-alias-allowlist

Goal:
Validate XiCAD policy candidate generation and safe runner dry-run behavior.

Rules:
- Do not execute XiCAD aliases.
- Do not call SendCommand.
- Do not modify DWG.
- C:/xicad is read-only input.
- allowed_for_execution must remain false.
- Unknown and destructive aliases must be blocked.

Commands:

git fetch origin exp/xicad-policy-candidate-generator
git switch exp/xicad-policy-candidate-generator

python -X utf8 -m pytest -q tests/test_xicad_policy_candidate_generator.py tests/test_xicad_safe_runner.py

python -X utf8 -m pytest -q

python -X utf8 -m src.main --help

Confirm CLI:
- xicad-policy-candidates
- xicad-safe-runner-dry-run

CLI smoke:
python -X utf8 -m src.main xicad-safe-runner-dry-run "xicad-safe-plan --alias WAL"
python -X utf8 -m src.main xicad-safe-runner-dry-run "xicad-safe-plan --alias ERASE"
python -X utf8 -m src.main xicad-safe-runner-dry-run "xicad-safe-plan --alias UNKNOWN_ABC"

Optional local C:/xicad candidate generation:
python -X utf8 -m src.main xicad-policy-candidates --xicad-root C:/xicad --out-dir outputs/xicad_policy_candidates_verify

Confirm artifacts:
- XICAD_POLICY_CANDIDATES.json
- XICAD_POLICY_CANDIDATES.md
- XICAD_ALIAS_POLICIES_EFFECTIVE.json

Confirm:
- allowed_for_execution is false for generated/effective policies
- destructive aliases are blocked
- unknown aliases are blocked
- output is review-only
- no XiCAD command was executed
- no DWG was modified

Report:
- Branch/commit tested
- Targeted test result
- Full pytest result
- CLI registration result
- CLI smoke result
- Optional C:/xicad result
- Artifact verification result
- Failures
- Patch required
- PR readiness
