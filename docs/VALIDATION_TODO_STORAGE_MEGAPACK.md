# Validation TODO — Storage Megapack

All verification is deferred.

## Commands

```powershell
python -X utf8 -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run analysis_storage_megapack --workspace outputs\webhard_batch_100
```

## Expected artifacts

```text
EVIDENCE_GRAPH_STORAGE_EXPORT.json
evidence_storage/nodes.table.json
evidence_storage/edges.table.json
VALIDATION_RULE_RESULTS_V2.json
```

## Optional artifacts

```text
evidence_storage/evidence_graph.duckdb
evidence_storage/nodes.parquet
evidence_storage/edges.parquet
```
