from __future__ import annotations

import sys
from pathlib import Path

from src.analysis.area_boundary_inference import infer_area_boundaries
from src.analysis.leader_dimension_table_inference import (
    infer_dimension_texts,
    infer_leader_notes,
    infer_table_regions,
    infer_titleblocks,
)
from src.analysis.policy_loader import load_text_fusion_policy
from src.analysis.text_role_inference import infer_text_roles
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'analysis_core_megapack'
BACKEND = 'analysis_core_megapack'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='analysis_core_megapack_v0_scaffold',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    artifacts: list[str] = []
    warnings: list[str] = []
    metrics = {}
    try:
        policy = load_text_fusion_policy(workspace)
        metrics['text_policy_source'] = policy.get('source')

        text_roles = infer_text_roles(workspace)
        area = infer_area_boundaries(workspace)
        leaders = infer_leader_notes(workspace)
        dims = infer_dimension_texts(workspace)
        tables = infer_table_regions(workspace)
        titleblocks = infer_titleblocks(workspace)

        artifacts.extend([
            str(workspace / 'TEXT_ROLE_INFERENCE.json'),
            str(workspace / 'TEXT_ROLE_INFERENCE.md'),
            str(workspace / 'AREA_BOUNDARY_INFERENCE.json'),
            str(workspace / 'AREA_BOUNDARY_INFERENCE.md'),
            str(workspace / 'LEADER_NOTE_INFERENCE.json'),
            str(workspace / 'LEADER_NOTE_INFERENCE.md'),
            str(workspace / 'DIMENSION_TEXT_INFERENCE.json'),
            str(workspace / 'DIMENSION_TEXT_INFERENCE.md'),
            str(workspace / 'TABLE_REGION_INFERENCE.json'),
            str(workspace / 'TABLE_REGION_INFERENCE.md'),
            str(workspace / 'TITLEBLOCK_INFERENCE.json'),
            str(workspace / 'TITLEBLOCK_INFERENCE.md'),
        ])
        metrics.update({
            'text_role_count': (text_roles.get('summary') or {}).get('text_count', 0),
            'area_candidate_count': (area.get('summary') or {}).get('candidate_count', 0),
            'leader_candidate_count': len(leaders.get('candidates') or []),
            'dimension_candidate_count': len(dims.get('candidates') or []),
            'table_candidate_count': len(tables.get('candidates') or []),
            'titleblock_candidate_count': len(titleblocks.get('candidates') or []),
        })
        warnings.extend(['analysis_core_megapack contains scaffold-level heuristics; validation is TODO'])
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=provenance)

    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='warning',
        artifacts=artifacts,
        signals=[
            {
                'id': 'analysis_core_megapack_scaffold',
                'score': 0.5,
                'evidence': ['scaffold artifacts generated', 'validation deferred to TODO'],
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
