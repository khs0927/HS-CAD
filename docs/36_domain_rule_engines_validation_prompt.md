# Validation prompt for domain rule engines

Copy this prompt into the verification agent after fetching `exp/domain-rule-engines`.

```text
You are validating the HS-CAD domain rule engine branch.

Repository: khs0927/HS-CAD
Branch: exp/domain-rule-engines

Goal:
Validate the new XiCAD / ArchiOffice / HS-Steel domain rule layer. This branch is separate from the earlier drawing-analysis experiment branch. The goal is not raw drawing scanning; the goal is deciding how analyzed drawings should be modified using domain rules.

Important architecture:
- XiCAD / ArchiOffice / HS-Steel are the design-rule authority.
- ZWCAD COM is only an execution channel, not the design authority.
- No original DWG should be mutated during validation.
- All modification recommendations must remain review-gated and SaveAs-based.
- Local C:/xicad may or may not exist. Tests must pass even when XiCAD is missing by producing warnings and empty packs.

Tasks:
1. Fetch and checkout the branch.
   - git fetch origin exp/domain-rule-engines
   - git switch exp/domain-rule-engines

2. Inspect changed files.
   - src/domain_rules/models.py
   - src/domain_rules/xicad_rule_adapter.py
   - src/domain_rules/archioffice_rule_engine.py
   - src/domain_rules/hssteel_rule_engine.py
   - src/domain_rules/orchestrator.py
   - src/domain_rules/prompt_builder.py
   - src/app/domain_rules_cli.py
   - tests/test_domain_rule_engines.py

3. Run targeted tests.
   - python -X utf8 -m pytest -q tests/test_domain_rule_engines.py

4. Run full tests.
   - python -X utf8 -m pytest -q

5. Import smoke tests.
   - python -X utf8 -c "from src.domain_rules.orchestrator import DomainRuleOrchestrator; print(DomainRuleOrchestrator(xicad_root='Z:/missing-xicad-for-test').review_drawing([], task='smoke').to_dict())"
   - python -X utf8 -c "import src.app.domain_rules_cli; print('domain_rules_cli import ok')"

6. CLI status check.
   - python -X utf8 -m src.main --help
   - Check whether domain-rule-pack and domain-rule-review-synthetic appear.
   - If they do not appear, report that src.main still needs to import src.app.domain_rules_cli.
   - Do not patch main unless specifically instructed.

7. Optional local XiCAD test, only if C:/xicad exists.
   - python -X utf8 -m src.main domain-rule-pack --xicad-root C:/xicad --out outputs/domain_rule_pack.json
   - Confirm output JSON includes xicad, archioffice, hssteel knowledge packs.

8. Synthetic review artifact test, if CLI is registered.
   - python -X utf8 -m src.main domain-rule-review-synthetic --out-dir outputs/domain_rule_review_synthetic_verify
   - Confirm these files exist:
     - DOMAIN_RULE_REVIEW.json
     - SYSTEM_DRAFTING_CONSTRAINTS.txt
     - DOMAIN_RULE_REVIEW.md
   - Confirm the prompt states that XiCAD / ArchiOffice / HS-Steel are the domain authority and ZWCAD COM is only an execution channel.

9. Report results in this format:
   - Branch/commit tested:
   - Targeted test result:
   - Full test result:
   - Import smoke result:
   - src.main --help / CLI registration result:
   - Optional XiCAD local pack result:
   - Synthetic review artifact result:
   - Failures with exact traceback:
   - Required patches:
   - PR readiness: keep open / patch needed / ready for review

Do not merge the PR. Do not push to main. If a patch is needed, commit only to exp/domain-rule-engines or provide a patch summary.
```
