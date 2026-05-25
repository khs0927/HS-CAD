# PR82 Generated Megapack Split Plan

Date: 2026-05-25

## Merge refusal statement

PR82 must not be merged directly.

Reason:

```text
PR82 is a draft generated megapack review PR from branch `pr-38-all-generated-megapacks`.
It contains generated source files, ZIP artifacts, runtime outputs, and direct high-risk edits.
It is useful as an inspection source only, not as a merge-ready branch.
```

Confirmed PR82 status at triage time:

```text
PR: #82 Review PR38 generated megapack validation branch
State: open
Draft: true
Merged: false
Mergeable: false
Base: main
Head: pr-38-all-generated-megapacks
Commits: 250
Changed files: 244
```

## High-risk exclusions

The following must be excluded from direct merge:

```text
artifacts/**/*.zip
outputs/**
*.dwg
*.dxf
*.sqlite
*.sqlite3
*.zip
__pycache__/**
.pytest_cache/**
```

The following high-risk files must not be accepted as direct edits from PR82:

```text
src/main.py
config/worker_manifest.json
src/adapters/zwcad_com_adapter.py
```

These should be converted into candidate patch documents instead:

```text
outputs/megapack_main_import_candidates.txt
outputs/megapack_worker_manifest_candidates.json
outputs/high_risk_file_change_plan.md
```

## Exact extraction PR order

### PR82-S1: Spatial Foundation

Purpose:

```text
Introduce isolated spatial helpers without runtime CLI registration.
```

File ownership:

```text
src/spatial/**
tests/test_spatial_*.py
tests/test_shapely_*.py
docs/29_shapely_topology_backend_plan.md
```

Exclude:

```text
src/main.py
config/worker_manifest.json
outputs/**
artifacts/**/*.zip
```

Expected tests:

```powershell
python -X utf8 -m compileall -q src/spatial tests
python -X utf8 -m pytest -q tests/test_spatial_backends.py tests/test_spatial_containment.py tests/test_spatial_graph_exporter.py tests/test_shapely_topology.py tests/test_shapely_topology_audit.py tests/test_shapely_area_matching.py
```

Safety posture:

```text
no CAD mutation
no ZWCAD COM
no SendCommand
no SaveAs
no XiCAD alias execution
```

### PR82-S2: PDF Raster

Purpose:

```text
Introduce PDF raster analysis utilities as isolated modules.
```

File ownership:

```text
src/pdf_raster/**
src/workers/pdf_raster_worker.py
tests/test_pdf_raster_worker.py
docs/33_pdf_raster_worker_plan.md
```

Expected tests:

```powershell
python -X utf8 -m compileall -q src/pdf_raster src/workers tests
python -X utf8 -m pytest -q tests/test_pdf_raster_worker.py
```

Notes:

```text
If optional PDF/image dependencies are missing, tests must skip gracefully instead of failing import-time.
```

### PR82-S3: OCR Tools

Purpose:

```text
Add OCR/text-region, vector-text matching, text review, and correction planning tools.
```

File ownership:

```text
src/ocr/**
src/workers/ocr_*_worker.py
src/workers/text_*_worker.py
tests/test_ocr_*_worker.py
tests/test_text_*_worker.py
docs/34_ocr_text_region_worker_plan.md
docs/35_ocr_vector_text_match_plan.md
docs/36_ocr_cad_text_match_plan.md
docs/37_text_evidence_fusion_plan.md
docs/38_text_review_queue_plan.md
docs/39_text_corrections_export_plan.md
docs/40_text_corrections_apply_plan.md
docs/41_text_calibration_report_plan.md
docs/42_text_weight_suggestions_plan.md
```

Expected tests:

```powershell
python -X utf8 -m compileall -q src/ocr src/workers tests
python -X utf8 -m pytest -q tests/test_ocr_text_region_worker.py tests/test_ocr_vector_text_match_worker.py tests/test_ocr_cad_text_match_worker.py tests/test_text_evidence_fusion_worker.py tests/test_text_review_queue_worker.py tests/test_text_corrections_export_worker.py tests/test_text_corrections_apply_worker.py tests/test_text_calibration_report_worker.py tests/test_text_weight_suggestions_worker.py
```

Safety posture:

```text
text review and correction planning only
no direct CAD text mutation
no applying corrections to DWG/DXF without separate approval gate
```

### PR82-S4: NetworkX Graph Audit

Purpose:

```text
Add graph audit and graph evidence helpers.
```

File ownership:

```text
src/graph/**
src/workers/networkx_graph_audit_worker.py
tests/test_networkx_graph_audit.py
docs/31_networkx_graph_audit_plan.md
```

Expected tests:

```powershell
python -X utf8 -m compileall -q src/graph src/workers tests
python -X utf8 -m pytest -q tests/test_networkx_graph_audit.py
```

Notes:

```text
NetworkX dependency should be optional or declared clearly. Missing dependency must not break unrelated HS-CAD commands.
```

### PR82-S5: DuckDB Analytics

Purpose:

```text
Add analytics export layer isolated from core runtime.
```

File ownership:

```text
src/analytics/**
src/workers/duckdb_export_worker.py
tests/test_duckdb_export.py
docs/32_duckdb_analytics_export_plan.md
```

Expected tests:

```powershell
python -X utf8 -m compileall -q src/analytics src/workers tests
python -X utf8 -m pytest -q tests/test_duckdb_export.py
```

Notes:

```text
DuckDB dependency should be optional or test-skipped if unavailable.
No output database files should be committed.
```

### PR82-S6: CLI registration candidates

Purpose:

```text
Convert PR82 src/main.py direct edits into reviewable import candidates.
```

File ownership:

```text
docs/pr82_cli_registration_candidates.md
outputs/megapack_main_import_candidates.txt, if kept local only
```

Do not modify:

```text
src/main.py
```

Expected tests:

```powershell
python -X utf8 -m src.main --help
```

Rule:

```text
CLI registration should be merged only after each module PR passes import and targeted tests.
```

### PR82-S7: Worker manifest candidates

Purpose:

```text
Convert PR82 config/worker_manifest.json direct edits into reviewable worker manifest candidates.
```

File ownership:

```text
docs/pr82_worker_manifest_candidates.md
outputs/megapack_worker_manifest_candidates.json, if kept local only
```

Do not modify:

```text
config/worker_manifest.json
```

Expected tests:

```powershell
python -X utf8 -m compileall -q src/workers tests
python -X utf8 -m pytest -q tests/test_worker_contracts.py tests/test_worker_run_log.py tests/test_worker_runner.py
```

Rule:

```text
Worker entries should be enabled only after their owning module PR is merged and locally validated.
```

## Files to quarantine or delete from split PRs

Do not include these in extraction PRs:

```text
artifacts/megapacks/*.zip
outputs/combined_megapack_apply_report.json
outputs/combined_megapack_install_summary.md
outputs/megapack_main_import_candidates.txt
outputs/megapack_worker_manifest_candidates.json
```

These are local validation outputs or source ZIP artifacts, not merge-ready source code.

## GitHub actions to take next

1. Keep PR82 open as draft inspection source only.
2. Add a comment to PR82 pointing to this split plan, if desired.
3. Create PR82-S1 from current main using only `src/spatial/**`, spatial tests, and spatial docs.
4. Run targeted tests for S1.
5. Only after S1 is merged, create S2 through S5 independently.
6. Create S6 and S7 only after source module PRs pass.
7. Close PR82 after all accepted split PRs are extracted and rejected artifacts are confirmed unnecessary.

## Final safety statement

This plan does not approve live CAD execution. It explicitly rejects direct merge of:

```text
src/main.py
config/worker_manifest.json
src/adapters/zwcad_com_adapter.py
artifacts/**/*.zip
outputs/**
```

The project remains review-only and dry-run-only until separate safety gates explicitly approve copied-DWG-only execution.
