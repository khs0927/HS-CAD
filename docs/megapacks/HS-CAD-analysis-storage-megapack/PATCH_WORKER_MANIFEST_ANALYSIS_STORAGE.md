# PATCH — Register analysis_storage_megapack

Add this worker entry to `config/worker_manifest.json`.

```json
"analysis_storage_megapack": {
  "worker_type": "analysis_storage",
  "env_manager": "current_python",
  "python": "3.12",
  "requirements": ["duckdb", "pyarrow"],
  "entry": "python -m src.workers.analysis_storage_megapack_worker",
  "timeout_sec": 900,
  "max_memory_mb": 8192,
  "gpu_required": false,
  "outputs": [
    "EVIDENCE_GRAPH_STORAGE_EXPORT.json",
    "EVIDENCE_GRAPH_STORAGE_EXPORT.md",
    "evidence_storage/nodes.table.json",
    "evidence_storage/edges.table.json",
    "evidence_storage/evidence_graph.duckdb",
    "evidence_storage/nodes.parquet",
    "evidence_storage/edges.parquet",
    "VALIDATION_RULE_RESULTS_V2.json",
    "VALIDATION_RULE_RESULTS_V2.md"
  ]
}
```

Keep validation TODO until local integration.
