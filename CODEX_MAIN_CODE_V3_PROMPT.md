# CODEX MAIN CODE V3 PROMPT

Implement and validate the HS-CAD evidence bridge overlay.

Main goal:
- Convert existing HS-CAD JSON artifacts into normalized Evidence records.
- Produce evidence graph, fusion matrix, cross-validation, markdown report, and SQLite index.
- Keep everything review-only: no CAD execution, no COM, no SendCommand, no XiCAD alias, no DWG mutation.

Key modules:
- `hscad.connectors.legacy_artifact_adapter`
- `hscad.pipelines.evidence_bridge_pipeline`
- `hscad.reports.evidence_bridge_report`
- `hscad.app.cli_evidence_bridge`

Validation:
```bash
python -X utf8 -m pytest -q tests/test_evidence_bridge_contracts.py tests/test_evidence_bridge_pipeline_smoke.py tests/test_commit_candidate_filter.py
python -X utf8 -m hscad.app.cli_evidence_bridge --legacy-dir outputs/main_code_v2_smoke --out outputs/evidence_bridge_v3_smoke
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

Do not commit runtime outputs, incoming overlays, CAD files, or caches.
