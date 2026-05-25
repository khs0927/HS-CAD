from __future__ import annotations

import sys
from pathlib import Path

from src.spatial.shapely_area_matching import write_shapely_area_matches
from src.spatial.shapely_topology import ShapelyTopologyAnalyzer
from src.spatial.shapely_topology_audit import ShapelyTopologyAuditor
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'shapely_topology'
BACKEND = 'shapely_topology'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    json_dir = workspace / 'fileized' / 'json'
    snap_tolerance = float(worker_input.options.get('snap_tolerance', 0.0))
    topology_path = workspace / 'SHAPELY_TOPOLOGY.json'
    matches_path = workspace / 'SHAPELY_AREA_MATCHES.json'
    audit_path = workspace / 'SHAPELY_TOPOLOGY_AUDIT.json'

    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='polygonize+area_match+polygonize_full_audit',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )

    try:
        topology = ShapelyTopologyAnalyzer().analyze_json_dir(json_dir)
        topology['provenance'] = provenance
        topology_path.write_text(_json(topology), encoding='utf-8')

        matches = write_shapely_area_matches(workspace, out_json=matches_path)
        matches['provenance'] = provenance
        matches_path.write_text(_json(matches), encoding='utf-8')

        audit = ShapelyTopologyAuditor().audit_json_dir(json_dir, snap_tolerance=snap_tolerance)
        audit['provenance'] = provenance
        audit_path.write_text(_json(audit), encoding='utf-8')
    except Exception as exc:
        return WorkerOutput.error(
            worker_name=WORKER_NAME,
            backend=BACKEND,
            message=str(exc),
            provenance=provenance,
        )

    warnings = []
    if topology.get('status_counts', {}).get('unavailable'):
        warnings.append('shapely unavailable for one or more files')

    return WorkerOutput.ok(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        artifacts=[str(topology_path), str(matches_path), str(audit_path)],
        signals=topology.get('signals') or [],
        warnings=warnings,
        metrics={
            'topology_polygon_count': topology.get('polygon_count'),
            'area_match_count': matches.get('match_count'),
            'topology_audit_finding_count': audit.get('finding_count'),
            'topology_audit_avg_quality_score': audit.get('avg_quality_score'),
        },
        provenance=provenance,
    )


def _json(payload: object) -> str:
    import json
    return json.dumps(payload, ensure_ascii=False, indent=2)


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
