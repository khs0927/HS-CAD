from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


WORKERS: dict[str, dict[str, Any]] = {
    "analysis_export_megapack": {
        "worker_type": "analysis_export",
        "env_manager": "current_python",
        "python": "3.12",
        "requirements": [],
        "entry": "python -m src.workers.analysis_export_megapack_worker",
        "timeout_sec": 900,
        "max_memory_mb": 8192,
        "gpu_required": False,
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
            "REPORT_ZIP_PACKAGE.md",
        ],
    },
    "analysis_storage_megapack": {
        "worker_type": "analysis_storage",
        "env_manager": "current_python",
        "python": "3.12",
        "requirements": ["duckdb", "pyarrow"],
        "entry": "python -m src.workers.analysis_storage_megapack_worker",
        "timeout_sec": 900,
        "max_memory_mb": 8192,
        "gpu_required": False,
        "outputs": [
            "EVIDENCE_GRAPH_STORAGE_EXPORT.json",
            "EVIDENCE_GRAPH_STORAGE_EXPORT.md",
            "evidence_storage/nodes.table.json",
            "evidence_storage/edges.table.json",
            "evidence_storage/evidence_graph.duckdb",
            "evidence_storage/nodes.parquet",
            "evidence_storage/edges.parquet",
            "VALIDATION_RULE_RESULTS_V2.json",
            "VALIDATION_RULE_RESULTS_V2.md",
        ],
    },
    "analysis_report_megapack": {
        "worker_type": "analysis_report",
        "env_manager": "current_python",
        "python": "3.12",
        "requirements": [],
        "entry": "python -m src.workers.analysis_report_megapack_worker",
        "timeout_sec": 900,
        "max_memory_mb": 8192,
        "gpu_required": False,
        "outputs": [
            "EVIDENCE_GRAPH_PARTITIONS.json",
            "EVIDENCE_GRAPH_PARTITIONS.md",
            "REPORT_REDACTION_PLAN.json",
            "REPORT_REDACTION_PLAN.md",
            "DASHBOARD_STATIC_ASSETS.json",
            "DASHBOARD_STATIC_ASSETS.md",
            "dashboard_assets/hscad_dashboard.css",
            "dashboard_assets/hscad_dashboard.js",
        ],
    },
}


def update_manifest(repo_root: Path) -> Path:
    path = repo_root / "config" / "worker_manifest.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {
            "protocol_version": "1.0",
            "description": "HS-CAD optional backend workers.",
            "workers": {},
        }

    workers = payload.setdefault("workers", {})
    for name, cfg in WORKERS.items():
        workers[name] = cfg

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    path = update_manifest(Path(args.repo_root))
    print(f"updated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
