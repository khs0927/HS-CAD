# PR82 Worker Candidate Validation Matrix

This document tracks the validation status of the worker candidates from PR82 before registering them into `config/worker_manifest.json`.

| Candidate | Module path | Exists | Import pass | Dry-run contract | Source PR | Status | Notes |
|---|---|---:|---:|---|---|---|---|
| pdf_raster | src.workers.pdf_raster_worker | Yes | Yes | Passed | PR 91 / PR 89 | ready_for_small_manifest_pr | Merged but needs manifest test |
| ocr_text_region | src.workers.ocr_text_region_worker | Yes | Yes | Passed | PR 91 / PR 93 | ready_for_small_manifest_pr | Merged but needs manifest test |
| networkx_graph_audit | src.workers.networkx_graph_audit_worker | Yes | Yes | Passed | PR 92 / PR 96 | ready_for_small_manifest_pr | Merged but needs manifest test |
| duckdb_export | src.workers.duckdb_export_worker | Yes | Yes | Passed | PR 92 / PR 97 | ready_for_small_manifest_pr | Merged but needs manifest test |
| analysis_advanced_megapack | src.workers.analysis_advanced_megapack_worker | No | No | N/A | Unmerged | missing_module | Needs source module extraction |

## Summary

- **4 ready candidates** are fully validated for import and are ready to be registered in a dedicated, focused manifest PR.
- **1 missing candidate** requires source module extraction and has been marked as `missing_module`.
