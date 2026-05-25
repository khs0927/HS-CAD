# PR82 Split Plan

## PR82 status

PR82 is a generated megapack review PR from branch `pr-38-all-generated-megapacks`.

It must not be merged directly.

Observed PR82 metadata on 2026-05-26:

- PR: #82
- State: open
- Draft: false
- Mergeable: CONFLICTING
- Base: main
- Head: pr-38-all-generated-megapacks
- Changed files reported by GitHub: 244
- Commits reported by GitHub: 250

The PR being ready for review does not make it merge-ready. Missing checks mean no CI result was reported, not that the branch passed CI.

## Merge refusal statement

Do not merge PR82 directly into `main`.

Reasons:

- It contains generated megapack ZIP artifacts.
- It contains runtime `outputs/**` reports.
- It directly edits high-risk files.
- It mixes safe source modules, docs, generated artifacts, CLI registration, worker registration, and runtime outputs in one draft PR.
- It requires extraction into smaller reviewable PRs.

## Exclude from all extraction PRs

The following should be excluded unless a later task explicitly creates a non-runtime fixture or documentation artifact:

- `outputs/**`
- `artifacts/**/*.zip`
- binary/runtime artifacts
- generated apply reports
- generated install summaries
- direct edits to `src/main.py`
- direct edits to `config/worker_manifest.json`
- broad edits to `src/adapters/zwcad_com_adapter.py`

## High-risk files found in PR82

- `src/main.py`
- `config/worker_manifest.json`

The prompt referenced `src/adapters/zwcad_com_adapter.py` as high risk. It must remain excluded if present in local or hidden branch history. It was not part of the visible GitHub filename list returned in this triage pass.

## Extraction PR order

### 1. Spatial Foundation

Purpose: isolate geometry and spatial primitives.

Status: completed separately and merged through PR #85. Do not re-extract this group from PR82.

Candidate ownership:

- `src/spatial/**`
- `tests/test_area_elements.py`
- `tests/test_spatial_backends.py`
- `tests/test_spatial_containment.py`
- `tests/test_spatial_graph_exporter.py`
- `tests/test_text_roles.py`
- spatial-specific docs only if directly relevant

Exclude:

- CLI registration in `src/main.py`
- worker manifest direct edits
- runtime outputs
- ZIP artifacts

Expected tests:

- `python -X utf8 -m pytest -q tests/test_area_elements.py tests/test_spatial_backends.py tests/test_spatial_containment.py tests/test_spatial_graph_exporter.py tests/test_text_roles.py`
- `python -X utf8 -m compileall -q src/spatial tests`

### 2. PDF Raster

Purpose: isolate PDF raster review tooling.

Candidate ownership:

- `src/pdf_raster/**`
- `src/workers/pdf_raster_worker.py`
- `tests/test_pdf_raster_worker.py`
- `docs/33_pdf_raster_worker_plan.md`

Exclude:

- CLI registration in `src/main.py`
- worker manifest direct edits
- generated outputs
- ZIP artifacts

Expected tests:

- `python -X utf8 -m pytest -q tests/test_pdf_raster_worker.py`
- `python -X utf8 -m compileall -q src/pdf_raster src/workers tests`

### 3. OCR Tools

Purpose: isolate OCR/text-region and CAD/vector text matching tools.

Candidate ownership:

- `src/ocr/**`
- `src/workers/ocr_text_region_worker.py`
- `src/workers/ocr_vector_text_match_worker.py`
- `src/workers/ocr_cad_text_match_worker.py`
- `src/workers/text_calibration_report_worker.py`
- `src/workers/text_corrections_apply_worker.py`
- `src/workers/text_corrections_export_worker.py`
- `src/workers/text_evidence_fusion_worker.py`
- `src/workers/text_review_queue_worker.py`
- `src/workers/text_weight_suggestions_worker.py`
- `tests/test_ocr_text_region_worker.py`
- `tests/test_ocr_vector_text_match_worker.py`
- `tests/test_ocr_cad_text_match_worker.py`
- `tests/test_text_calibration_report_worker.py`
- `tests/test_text_corrections_apply_worker.py`
- `tests/test_text_corrections_export_worker.py`
- `tests/test_text_evidence_fusion_worker.py`
- `tests/test_text_review_queue_worker.py`
- `tests/test_text_weight_suggestions_worker.py`
- OCR-specific docs 34 through 42 where applicable

Exclude:

- direct CAD mutation paths
- direct edits to `src/main.py`
- direct edits to `config/worker_manifest.json`
- runtime outputs
- ZIP artifacts

Expected tests:

- `python -X utf8 -m pytest -q tests/test_ocr_text_region_worker.py tests/test_ocr_vector_text_match_worker.py tests/test_ocr_cad_text_match_worker.py`
- `python -X utf8 -m pytest -q tests/test_text_calibration_report_worker.py tests/test_text_corrections_apply_worker.py tests/test_text_corrections_export_worker.py tests/test_text_evidence_fusion_worker.py tests/test_text_review_queue_worker.py tests/test_text_weight_suggestions_worker.py`

### 4. NetworkX Graph Audit

Purpose: isolate graph audit utilities.

Candidate ownership:

- `src/graph/**`
- `src/workers/networkx_graph_audit_worker.py`
- `tests/test_networkx_graph_audit.py`
- `docs/31_networkx_graph_audit_plan.md`

Expected tests:

- `python -X utf8 -m pytest -q tests/test_networkx_graph_audit.py`
- `python -X utf8 -m compileall -q src/graph src/workers tests`

### 5. DuckDB Analytics

Purpose: isolate analytics/export support.

Candidate ownership:

- `src/analytics/**`
- `src/workers/duckdb_export_worker.py`
- `tests/test_duckdb_export.py`
- `docs/32_duckdb_analytics_export_plan.md`

Expected tests:

- `python -X utf8 -m pytest -q tests/test_duckdb_export.py`
- `python -X utf8 -m compileall -q src/analytics src/workers tests`

### 6. CLI registration candidates

Purpose: preserve proposed CLI imports without editing `src/main.py` directly.

Candidate ownership:

- `outputs/megapack_main_import_candidates.txt` should not be committed as runtime output.
- Convert its content into a docs-only candidate file such as `docs/pr82_main_import_candidates.md` if needed.
- `docs/megapacks/**/PATCH_MAIN_IMPORT*.md`

Do not edit:

- `src/main.py`

Expected tests after later actual CLI registration PR:

- `python -X utf8 -m src.main --help`
- focused CLI smoke tests only after registration is reviewed.

### 7. Worker manifest candidates

Purpose: preserve worker manifest proposals without editing `config/worker_manifest.json` directly.

Candidate ownership:

- `docs/megapacks/**/PATCH_WORKER_MANIFEST*.md`
- optional docs-only summary such as `docs/pr82_worker_manifest_candidates.md`

Do not edit:

- `config/worker_manifest.json`

Expected tests after later actual worker registration PR:

- worker contract tests
- worker registry tests
- focused worker tests for each worker group

## PR82 docs/config triage

Potential docs-only PRs:

- `docs/26_open_source_integration_framework.md`
- `docs/27_cad_compat_layer_intelligence_plan.md`
- `docs/28_open_source_fusion_and_cross_validation_process.md`
- `docs/29_shapely_topology_backend_plan.md`
- `docs/30_worker_protocol_and_isolation_plan.md`
- `docs/43_analysis_core_megapack_plan.md` through `docs/56_all_generated_megapacks_combined_push.md`

Potential config review PR, only after docs review:

- `config/open_source_backends.json`
- `config/cad_platforms.json`
- `config/open_source_fusion_matrix.json`

Do not include `config/worker_manifest.json` in the config review PR.

## GitHub actions to take next

1. Keep PR82 open as an inspection source only.
2. Add a PR82 comment pointing to this split plan if needed.
3. Do not approve PR82.
4. Do not merge PR82.
5. Create extraction branches from latest `main`, one group at a time.
6. Continue with PDF Raster because Spatial Foundation has already landed.
7. Then extract OCR Tools.
8. Keep CLI and worker manifest changes as candidate docs only until their source groups are validated.
9. Close or supersede PR82 only after all useful parts are extracted into smaller PRs.

## Local validation handoff

Local validation must verify each extraction branch from a clean latest-main worktree. Runtime outputs and binary archives must remain out of commits.
