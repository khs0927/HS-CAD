from __future__ import annotations

import json
import sys
from pathlib import Path

from src.graph.networkx_graph_audit import write_graph_audit
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'networkx_graph_audit'
BACKEND = 'networkx_graph_audit'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    json_path = workspace / 'GRAPH_AUDIT.json'
    md_path = workspace / 'GRAPH_AUDIT.md'
    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='networkx_graph_audit_rules',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_graph_audit(workspace, out_json=json_path, out_md=md_path)
        result['provenance'] = provenance
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as exc:
        return WorkerOutput.error(
            worker_name=WORKER_NAME,
            backend=BACKEND,
            message=str(exc),
            provenance=provenance,
        )
    status = str(result.get('status') or 'ok')
    if status == 'unavailable':
        return WorkerOutput.error(
            worker_name=WORKER_NAME,
            backend=BACKEND,
            message=str(result.get('reason') or 'networkx unavailable'),
            status='unavailable',
            provenance=provenance,
        )
    score = _score_from_result(result)
    metrics = result.get('metrics') or {}
    return WorkerOutput(
        status='ok',
        worker_name=WORKER_NAME,
        backend=BACKEND,
        artifacts=[str(json_path), str(md_path)],
        signals=[
            {
                'id': 'networkx_component_check',
                'score': score,
                'evidence': [
                    f"finding_count={result.get('finding_count')}",
                    f"node_count={result.get('node_count')}",
                    f"graph_quality_score={metrics.get('graph_quality_score')}",
                ],
            },
            {
                'id': 'orphan_detection',
                'score': score,
                'evidence': [
                    f"finding_count={result.get('finding_count')}",
                    f"weighted_finding_rate={metrics.get('weighted_finding_rate')}",
                ],
            },
        ],
        warnings=[] if not result.get('findings') else ['graph audit produced findings'],
        metrics={
            'node_count': result.get('node_count'),
            'edge_count': result.get('edge_count'),
            'finding_count': result.get('finding_count'),
            'finding_rate': metrics.get('finding_rate'),
            'weighted_finding_rate': metrics.get('weighted_finding_rate'),
            'graph_penalty': metrics.get('graph_penalty'),
            'graph_quality_score': metrics.get('graph_quality_score'),
            'severity_counts': metrics.get('severity_counts'),
            'finding_type_counts': metrics.get('finding_type_counts'),
        },
        provenance=provenance,
    )


def _score_from_result(result: dict) -> float:
    metrics = result.get('metrics') or {}
    if metrics.get('graph_quality_score') is not None:
        return float(metrics.get('graph_quality_score') or 0.0)
    rate = float(metrics.get('finding_rate') or 0.0)
    return round(max(0.0, min(1.0, 1.0 - rate)), 6)


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        output = WorkerOutput.error(
            worker_name=WORKER_NAME,
            backend=BACKEND,
            message='missing WorkerInput path argument',
        )
        print(output.to_json())
        return 2
    worker_input = WorkerInput.from_json_file(args[0])
    output = run_worker(worker_input)
    print(output.to_json())
    return 0 if output.status in {'ok', 'warning', 'unavailable'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
