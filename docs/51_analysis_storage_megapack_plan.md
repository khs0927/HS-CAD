# 51. Analysis Storage Megapack Plan

## Goal

Continue code generation without validation.

This pack adds:

```text
optional DuckDB evidence graph export
optional Parquet evidence graph export
JSON table export fallback
threshold-aware validation rule engine v2
analysis_storage_megapack worker
```

## New worker

```text
analysis_storage_megapack
```

Expected command:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_storage_megapack --workspace outputs\webhard_batch_100
```

## Outputs

```text
EVIDENCE_GRAPH_STORAGE_EXPORT.json
EVIDENCE_GRAPH_STORAGE_EXPORT.md
evidence_storage/nodes.table.json
evidence_storage/edges.table.json
evidence_storage/evidence_graph.duckdb        # optional
evidence_storage/nodes.parquet                # optional
evidence_storage/edges.parquet                # optional
VALIDATION_RULE_RESULTS_V2.json
VALIDATION_RULE_RESULTS_V2.md
```

## Validation TODO

Do not run validation now.

```powershell
python -m pip install duckdb pyarrow
python -X utf8 -m src.main hscad-worker-run analysis_storage_megapack --workspace outputs\webhard_batch_100
```

## Manual patch TODO

Register `analysis_storage_megapack` in `config/worker_manifest.json`.

## Next pack candidates

```text
real CLI registration
dashboard static assets
report redaction
per-file evidence graph partitioner
```
