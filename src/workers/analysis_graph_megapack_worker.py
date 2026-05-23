from __future__ import annotations

import sys
from pathlib import Path

from src.analysis.dimension_graph_builder import build_dimension_graph
from src.analysis.geometry_loop_builder import build_geometry_loops
from src.analysis.leader_graph_builder import build_leader_graph
from src.analysis.table_grid_detector import detect_table_grids
from src.analysis.titleblock_classifier import classify_titleblocks
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'analysis_graph_megapack'
BACKEND = 'analysis_graph_megapack'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='analysis_graph_megapack_v0_scaffold',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    artifacts: list[str] = []
    warnings: list[str] = []
    metrics = {}
    try:
        loops = build_geometry_loops(workspace)
        leader = build_leader_graph(workspace)
        dim = build_dimension_graph(workspace)
        table = detect_table_grids(workspace)
        title = classify_titleblocks(workspace)

        artifacts.extend([
            str(workspace / 'GEOMETRY_LOOP_BUILDER.json'),
            str(workspace / 'GEOMETRY_LOOP_BUILDER.md'),
            str(workspace / 'LEADER_GRAPH.json'),
            str(workspace / 'LEADER_GRAPH.md'),
            str(workspace / 'DIMENSION_GRAPH.json'),
            str(workspace / 'DIMENSION_GRAPH.md'),
            str(workspace / 'TABLE_GRID_DETECTOR.json'),
            str(workspace / 'TABLE_GRID_DETECTOR.md'),
            str(workspace / 'TITLEBLOCK_CLASSIFIER.json'),
            str(workspace / 'TITLEBLOCK_CLASSIFIER.md'),
        ])
        metrics.update({
            'geometry_closed_candidate_count': (loops.get('summary') or {}).get('closed_polyline_candidate_count', 0),
            'geometry_fragment_group_count': (loops.get('summary') or {}).get('fragment_group_count', 0),
            'leader_edge_count': (leader.get('summary') or {}).get('edge_count', 0),
            'dimension_edge_count': (dim.get('summary') or {}).get('edge_count', 0),
            'table_grid_candidate_count': (table.get('summary') or {}).get('candidate_count', 0),
            'titleblock_candidate_count': (title.get('summary') or {}).get('candidate_count', 0),
        })
        warnings.append('analysis_graph_megapack contains scaffold-level graph heuristics; validation is TODO')
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=provenance)

    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='warning',
        artifacts=artifacts,
        signals=[
            {
                'id': 'analysis_graph_megapack_scaffold',
                'score': 0.5,
                'evidence': ['graph scaffold artifacts generated', 'validation deferred to TODO'],
            }
        ],
        warnings=warnings,
        metrics=metrics,
        provenance=provenance,
    )


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        output = WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message='missing WorkerInput path argument')
        print(output.to_json())
        return 2
    worker_input = WorkerInput.from_json_file(args[0])
    output = run_worker(worker_input)
    print(output.to_json())
    return 0 if output.status in {'ok', 'warning', 'unavailable'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
