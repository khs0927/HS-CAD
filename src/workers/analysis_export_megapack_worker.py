from __future__ import annotations

import sys
from pathlib import Path

from src.analysis.evidence_graph_exporter import export_evidence_graph_tables
from src.analysis.report_zip_packager import create_report_zip_package
from src.analysis.validation_threshold_config import load_or_create_validation_thresholds
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = "analysis_export_megapack"
BACKEND = "analysis_export_megapack"


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm="analysis_export_megapack_v0",
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    artifacts: list[str] = []
    warnings: list[str] = []
    metrics = {}

    try:
        thresholds = load_or_create_validation_thresholds(workspace)
        graph_export = export_evidence_graph_tables(workspace)
        package = create_report_zip_package(
            workspace,
            create_zip=bool(worker_input.options.get("create_zip", False)),
            redact_private_paths=bool(worker_input.options.get("redact_private_paths", True)),
        )

        artifacts.extend([
            str(workspace / "VALIDATION_THRESHOLDS.json"),
            str(workspace / "VALIDATION_THRESHOLD_CONFIG.json"),
            str(workspace / "VALIDATION_THRESHOLD_CONFIG.md"),
            str(workspace / "EVIDENCE_GRAPH_EXPORT.json"),
            str(workspace / "EVIDENCE_GRAPH_EXPORT.md"),
            str(workspace / "evidence_graph" / "nodes.jsonl"),
            str(workspace / "evidence_graph" / "edges.jsonl"),
            str(workspace / "evidence_graph" / "nodes.csv"),
            str(workspace / "evidence_graph" / "edges.csv"),
            str(workspace / "REPORT_ZIP_PACKAGE.json"),
            str(workspace / "REPORT_ZIP_PACKAGE.md"),
        ])

        metrics.update({
            "threshold_rule_count": (thresholds.get("summary") or {}).get("rule_count", 0),
            "graph_node_count": (graph_export.get("summary") or {}).get("node_count", 0),
            "graph_edge_count": (graph_export.get("summary") or {}).get("edge_count", 0),
            "report_zip_created": (package.get("summary") or {}).get("zip_created", False),
            "report_zip_included_count": (package.get("summary") or {}).get("included_count", 0),
        })

        warnings.extend(thresholds.get("warnings") or [])
        warnings.extend(graph_export.get("warnings") or [])
        warnings.extend(package.get("warnings") or [])
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=provenance)

    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status="warning",
        artifacts=artifacts,
        signals=[
            {
                "id": "analysis_export_megapack",
                "score": 0.65,
                "evidence": [
                    "validation thresholds, evidence graph exports, and report zip plan generated"
                ],
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
