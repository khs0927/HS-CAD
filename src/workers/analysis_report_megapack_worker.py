from __future__ import annotations

import sys
from pathlib import Path

from src.analysis.dashboard_static_assets import write_dashboard_static_assets
from src.analysis.evidence_graph_partitioner import partition_evidence_graph_by_file
from src.analysis.report_redactor import build_report_redaction_plan
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = "analysis_report_megapack"
BACKEND = "analysis_report_megapack"


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm="analysis_report_megapack_v0",
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    artifacts: list[str] = []
    warnings: list[str] = []
    metrics = {}

    try:
        partitions = partition_evidence_graph_by_file(workspace)
        redaction = build_report_redaction_plan(
            workspace,
            apply_redaction=bool(worker_input.options.get("apply_redaction", False)),
        )
        assets = write_dashboard_static_assets(workspace)

        artifacts.extend([
            str(workspace / "EVIDENCE_GRAPH_PARTITIONS.json"),
            str(workspace / "EVIDENCE_GRAPH_PARTITIONS.md"),
            str(workspace / "REPORT_REDACTION_PLAN.json"),
            str(workspace / "REPORT_REDACTION_PLAN.md"),
            str(workspace / "DASHBOARD_STATIC_ASSETS.json"),
            str(workspace / "DASHBOARD_STATIC_ASSETS.md"),
            str(workspace / "dashboard_assets" / "hscad_dashboard.css"),
            str(workspace / "dashboard_assets" / "hscad_dashboard.js"),
        ])

        metrics.update({
            "partition_count": (partitions.get("summary") or {}).get("partition_count", 0),
            "cross_file_edge_count": (partitions.get("summary") or {}).get("cross_file_edge_count", 0),
            "redaction_candidate_file_count": (redaction.get("summary") or {}).get("candidate_file_count", 0),
            "dashboard_asset_count": (assets.get("summary") or {}).get("asset_count", 0),
        })

        warnings.extend(partitions.get("warnings") or [])
        warnings.extend(redaction.get("warnings") or [])
        warnings.extend(assets.get("warnings") or [])
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=provenance)

    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status="warning",
        artifacts=artifacts,
        signals=[{"id": "analysis_report_megapack", "score": 0.65, "evidence": ["partition, redaction plan, and dashboard assets generated"]}],
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
