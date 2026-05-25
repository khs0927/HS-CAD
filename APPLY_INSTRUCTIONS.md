# Apply HS-CAD Main-Code Overlay v5

This overlay should be applied only after v1-v4 have been applied and validated on:

`C:\CODE\HS-CAD-main-code-overlay`

## Apply

```powershell
python -X utf8 .\_incoming\main_code_overlay_v5\scripts\apply_hscad_main_code_overlay_v5.py `
  --overlay .\_incoming\main_code_overlay_v5 `
  --repo-root . `
  --dry-run

python -X utf8 .\_incoming\main_code_overlay_v5\scripts\apply_hscad_main_code_overlay_v5.py `
  --overlay .\_incoming\main_code_overlay_v5 `
  --repo-root .
```

## Validate

```powershell
python -X utf8 -m pytest -q tests/test_pr_readiness_v5.py
python -X utf8 scripts\validate_hscad_pr_ready.py --repo-root .
python -X utf8 scripts\generate_hscad_pr_body.py --repo-root . --out docs\35_main_code_overlay_pr_body.md
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

If `validate_hscad_pr_ready.py` fails because `_incoming/**` or `outputs/**` are present, that is expected before cleanup. Do not commit those files.
