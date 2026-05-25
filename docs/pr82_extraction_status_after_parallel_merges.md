# PR82 Extraction Status After Parallel Merges

Date: 2026-05-25

## Context

During PR82 split execution, multiple parallel merges occurred on `main`. To avoid duplicate extraction PRs and file conflicts, this document records which PR82 safe groups are already present on latest `main`.

Latest checked main SHA:

```text
27ee6d533d042aade8242b800f344941f2005846
```

## Result

The safe code groups identified in `docs/pr82_split_plan.md` appear to have been mostly extracted into `main` by parallel work.

## Group status

| PR82 group | Status on latest main | Notes |
|---|---|---|
| Spatial Foundation | Present | `src/spatial/geometry.py`, `src/spatial/containment.py` exist on main |
| PDF Raster | Present | `src/pdf_raster/pdf_raster_analysis.py` exists on main |
| OCR Text Region | Present | `src/ocr/text_region_analysis.py` exists on main |
| OCR Vector/Text Evidence | Present | `src/ocr/vector_text_matching.py`, `src/ocr/text_evidence_fusion.py` exist on main |
| NetworkX Graph Audit | Present | `src/graph/networkx_graph_audit.py` exists on main |
| DuckDB Analytics | Present | `src/analytics/duckdb_export.py` exists on main |

## Branches intentionally not opened as PRs

The following temporary extraction branches were created or partially prepared, but should not be opened as PRs because `main` moved and the target files were already present on latest `main`:

```text
pr82-s1-spatial-foundation
pr82-s3-ocr-tools
pr82-s4-networkx-graph-audit
```

Do not merge these branches. They are superseded by latest `main`.

## Remaining PR82 work

The remaining work is not broad source extraction. It is review and candidate registration only:

1. Verify that no `outputs/**` artifacts from PR82 need to remain in Git.
2. Verify that `artifacts/megapacks/*.zip` are excluded or intentionally preserved elsewhere.
3. Convert CLI registration proposals into docs-only candidates.
4. Convert worker manifest proposals into docs-only candidates.
5. Keep direct edits to `src/main.py` and `config/worker_manifest.json` out of PR82 extraction.
6. Keep PR82 open only as an inspection source until all useful pieces are accounted for.

## Recommended next task

Create candidate documents only:

```text
docs/pr82_main_import_candidates.md
docs/pr82_worker_manifest_candidates.md
```

Do not edit:

```text
src/main.py
config/worker_manifest.json
```

## Safety

No live CAD execution is approved by this status update.

Still blocked:

```text
ZWCAD COM SendCommand
CHPROP execution
SAVEAS execution
DXFOUT execution
XiCAD alias execution
original DWG mutation
```
