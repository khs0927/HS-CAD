# CODEX_MAIN_CODE_V5_PROMPT

Apply HS-CAD main-code overlay v5 on top of the already validated v1-v4 branch.

Goals:
- Add PR readiness validation.
- Add PR body generation.
- Add tests for forbidden commit candidates.
- Keep all workflows review-only.
- Do not implement live CAD execution.

Safety invariants:
- No CAD execution.
- No ZWCAD COM invocation.
- No SendCommand.
- No XiCAD alias execution.
- No original DWG mutation.
- Keep runtime files out of commit.

Validation:
```bash
python -X utf8 -m pytest -q tests/test_pr_readiness_v5.py
python -X utf8 scripts/validate_hscad_pr_ready.py --repo-root .
python -X utf8 scripts/generate_hscad_pr_body.py --repo-root . --out docs/35_main_code_overlay_pr_body.md
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

Do not commit or push unless explicitly asked.
