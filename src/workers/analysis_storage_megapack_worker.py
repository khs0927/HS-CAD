from __future__ import annotations

import sys
from pathlib import Path

from src.analysis.evidence_graph_storage_exporter import export_evidence_graph_storage
from src.analysis.validation_rule_engine_v2 import run_validation_rules_v2
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = "analysis_storage_megapack"
BACKEND = "analysis_storage_megapack"


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm="analysis_storage_megapack_v0",
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )

    artifacts: list[str] = []
    warnings: list[str] = []
    metrics = {}

    try:
        storage = export_evidence_graph_storage(workspace)
        rules = run_validation_rules_v2(workspace)
        artifacts.extend([
            str(workspace / "EVIDENCE_GRAPH_STORAGE_EXPORT.json"),
            str(workspace / "EVIDENCE_GRAPH_STORAGE_EXPORT.md"),
            str(workspace / "evidence_storage" / "nodes.table.json"),
            str(workspace / "evidence_storage" / "edges.table.json"),
            str(workspace / "VALIDATION_RULE_RESULTS_V2.json"),
            str(workspace / "VALIDATION_RULE_RESULTS_V2.md"),
        ])

        metrics.update({
            "storage_node_count": (storage.get("summary") or {}).get("node_count", 0),
            "storage_edge_count": (storage.get("summary") or {}).get("edge_count", 0),
            "duckdb_status": (storage.get("summary") or {}).get("duckdb_status"),
            "parquet_status": (storage.get("summary") or {}).get("parquet_status"),
            "validation_v2_status": (rules.get("summary") or {}).get("overall_status"),
            "validation_v2_fail_count": (rules.get("summary") or {}).get("fail_count", 0),
        })

        warnings.extend(storage.get("warnings") or [])
        warnings.extend(rules.get("warnings") or [])
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=provenance)

    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status="warning",
        artifacts=artifacts,
        signals=[
            {
                "id": "analysis_storage_megapack",
                "score": 0.65,
                "evidence": ["storage export and threshold-aware validation generated"],
            }
        ],
        warnings=warnings,
        metrics=metrics,
        provenance=provenance,
    )


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        output = WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message="missing WorkerInput path argument")
        print(output.to_json())
        return 2
    worker_input = WorkerInput.from_json_file(args[0])
    output = run_worker(worker_input)
    print(output.to_json())
    return 0 if output.status in {"ok", "warning", "unavailable"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
