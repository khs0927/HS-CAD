# PR82 Worker Manifest Candidates

## Status

This document records worker manifest candidates from PR82.
It does not modify config/worker_manifest.json.

## Why direct merge is blocked

- config/worker_manifest.json is a high-risk integration file.
- Worker entries must be added only after corresponding source modules are merged.
- Worker dry-run tests must pass without skip-based masking.
- src/main.py registration is out of scope.
- Live CAD execution remains blocked.

## Candidate worker entries

| Candidate worker id | Module path | Function/class | Source PR dependency | Test file | Status | Notes |
|---|---|---|---|---|---|---|
| pdf_raster | src.workers.pdf_raster_worker | pdf_raster | PR 91 | test_pdf_raster_worker.py | ready_candidate | Merged but needs manifest test |
| ocr_text_region | src.workers.ocr_text_region_worker | ocr_text_region | PR 91 | test_ocr_text_region_worker.py | ready_candidate | Merged but needs manifest test |
| networkx_graph_audit | src.workers.networkx_graph_audit_worker | networkx_graph_audit | PR 92 | test_networkx_graph_audit.py | ready_candidate | Merged but needs manifest test |
| duckdb_export | src.workers.duckdb_export_worker | duckdb_export | PR 92 | test_duckdb_export.py | ready_candidate | Merged but needs manifest test |
| analysis_advanced_megapack | src.workers.analysis_advanced_megapack_worker | analysis_advanced | unmerged | unknown | missing_module | Needs source module extraction |

## Required validation before actual manifest edit

1. Module import test
2. Worker contract test
3. Dry-run test
4. No CAD execution
5. No original DWG mutation
6. No outputs/artifacts committed
7. No src/main.py changes
8. No live runner changes

## Future implementation PR rule

Actual config/worker_manifest.json changes must be done in small PRs:
- one worker family per PR
- corresponding tests included
- no test skip masking
- full pytest required
