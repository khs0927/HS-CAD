# 32. DuckDB / Parquet Analytical Export Plan

This document defines PR #9: optional DuckDB / Parquet Analytical Export Worker.

## Goal

Move HS-CAD from file-by-file JSON artifacts toward project-wide analytical storage.

The worker exports existing artifacts into:

```text
hscad_analysis.duckdb
analytics/*.parquet
DUCKDB_EXPORT.json
DUCKDB_EXPORT_REPORT.md
```

This makes project-wide queries, statistics, and later dashboard/reporting workflows faster and more stable.

## Why DuckDB / Parquet

HS-CAD currently produces many JSON artifacts. JSON is good for auditability and human inspection, but slow for project-wide aggregation.

DuckDB and Parquet provide:

```text
fast embedded analytical queries
workspace-level statistics
low-copy export path for future Polars / Arrow workflows
repeatable SQL reports
optional future spatial extension path
```

## Worker

Worker name:

```text
duckdb_export
```

Manifest status:

```text
implemented
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run duckdb_export --workspace outputs\webhard_batch_100
```

## Inputs

The worker reads available artifacts from the workspace:

```text
fileized/json/*.json
LAYER_SEMANTICS.json
TEXT_ROLE_INFERENCE.json
AREA_ELEMENTS.json
SPATIAL_GRAPH.json
CROSS_VALIDATION.json
GRAPH_AUDIT.json
```

Missing files are allowed. Missing artifacts become empty tables with stable schemas.

## Outputs

```text
DUCKDB_EXPORT.json
DUCKDB_EXPORT_REPORT.md
hscad_analysis.duckdb
analytics/files.parquet
analytics/entities.parquet
analytics/layers.parquet
analytics/texts.parquet
analytics/areas.parquet
analytics/graph_nodes.parquet
analytics/graph_edges.parquet
analytics/cross_validation_results.parquet
analytics/graph_audit_findings.parquet
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/duckdb_export.jsonl
```

## Tables

Initial tables:

```text
files
entities
layers
texts
areas
graph_nodes
graph_edges
cross_validation_results
graph_audit_findings
```

`entities` is now a first-class table. TEXT/MTEXT entities can also populate `texts` as a fallback when `TEXT_ROLE_INFERENCE.json` is not available.

Future tables:

```text
shapely_polygons
shapely_area_matches
topology_audit_findings
raster_contours
ocr_text_regions
bim_projection_items
```

## SQL report metrics

Initial report includes:

```text
file_count
total_entities
entity_rows
area_count
text_count
graph_node_count
graph_edge_count
low_confidence_cross_validation
graph_audit_findings
layer_semantic_counts
entity_type_counts
area_source_type_counts
```

## Provenance

`DUCKDB_EXPORT.json` includes top-level `provenance`.

The worker output also uses the same provenance payload so `WORKER_AUDIT.json` can verify provenance presence.

## Spatial capability

PR #9 does not require DuckDB Spatial extension.

The worker records spatial capability as:

```json
{
  "status": "not_loaded",
  "reason": "spatial extension not required by PR #9 initial export"
}
```

Future PRs can add:

```text
GEOMETRY / WKB columns
R-Tree indexes
ST_Contains / ST_Intersects / ST_DWithin reports
```

## Validation

Run:

```powershell
python -m pytest tests/test_duckdb_export.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run duckdb_export --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\DUCKDB_EXPORT.json
outputs\webhard_batch_100\DUCKDB_EXPORT_REPORT.md
outputs\webhard_batch_100\hscad_analysis.duckdb
outputs\webhard_batch_100\analytics\*.parquet
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\duckdb_export.jsonl
```

## Safety

DuckDB is optional. If DuckDB is missing, the worker returns structured `unavailable` and still writes `DUCKDB_EXPORT_REPORT.md` and `DUCKDB_EXPORT.json`. No drawing files are modified.
