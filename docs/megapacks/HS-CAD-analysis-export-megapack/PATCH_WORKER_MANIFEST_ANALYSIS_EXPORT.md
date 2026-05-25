# PATCH — Register analysis_export_megapack

Add this worker entry to `config/worker_manifest.json`.

```json
"analysis_export_megapack": {
  "worker_type": "analysis_export",
  "env_manager": "current_python",
  "python": "3.12",
  "requirements": [],
  "entry": "python -m src.workers.analysis_export_megapack_worker",
  "timeout_sec": 900,
  "max_memory_mb": 8192,
  "gpu_required": false,
  "outputs": [
    "VALIDATION_THRESHOLDS.json",
    "VALIDATION_THRESHOLD_CONFIG.json",
    "VALIDATION_THRESHOLD_CONFIG.md",
    "EVIDENCE_GRAPH_EXPORT.json",
    "EVIDENCE_GRAPH_EXPORT.md",
    "evidence_graph/nodes.jsonl",
    "evidence_graph/edges.jsonl",
    "evidence_graph/nodes.csv",
    "evidence_graph/edges.csv",
    "REPORT_ZIP_PACKAGE.json",
    "REPORT_ZIP_PACKAGE.md"
  ]
}
```

Keep validation TODO until local integration.
