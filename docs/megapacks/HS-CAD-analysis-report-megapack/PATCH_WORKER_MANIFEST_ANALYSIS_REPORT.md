# PATCH — Register analysis_report_megapack

Add this worker entry to `config/worker_manifest.json`.

```json
"analysis_report_megapack": {
  "worker_type": "analysis_report",
  "env_manager": "current_python",
  "python": "3.12",
  "requirements": [],
  "entry": "python -m src.workers.analysis_report_megapack_worker",
  "timeout_sec": 900,
  "max_memory_mb": 8192,
  "gpu_required": false,
  "outputs": [
    "EVIDENCE_GRAPH_PARTITIONS.json",
    "EVIDENCE_GRAPH_PARTITIONS.md",
    "REPORT_REDACTION_PLAN.json",
    "REPORT_REDACTION_PLAN.md",
    "DASHBOARD_STATIC_ASSETS.json",
    "DASHBOARD_STATIC_ASSETS.md",
    "dashboard_assets/hscad_dashboard.css",
    "dashboard_assets/hscad_dashboard.js"
  ]
}
```
