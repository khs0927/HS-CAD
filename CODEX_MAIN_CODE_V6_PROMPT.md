# CODEX MAIN CODE V6 PROMPT

You are working on HS-CAD after PR #66.

Goal:
- Strengthen the legacy artifact evidence bridge with schema-aware extraction.
- Keep all workflows review-only.
- Do not execute CAD, ZWCAD COM, SendCommand, XiCAD aliases, or mutate original DWG files.

Apply/validate:
```bash
python -X utf8 -m pytest -q tests/test_legacy_artifact_schema_v6.py
python -X utf8 scripts/inspect_legacy_artifact_schema.py --legacy-dir <legacy-output-dir> --out outputs/schema_report_v6.json
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

Commit policy:
- Commit only source, tests, scripts, and docs.
- Do not commit outputs, _incoming, zips, DWG, runtime DXF, SQLite DBs, or caches.

Expected branch:
- `feature/evidence-bridge-schema-golden`
- Stack on top of `feature/main-code-pipeline-overlay` until PR #66 is merged.
