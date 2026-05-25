from __future__ import annotations

import sys
from pathlib import Path

from src.ocr.vector_text_matching import write_ocr_vector_text_matches
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'ocr_vector_text_match'
BACKEND = 'ocr_vector_text_matching'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    min_score = float(worker_input.options.get('min_score') or 0.15)
    fallback_provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='bbox_iou_plus_text_similarity',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_ocr_vector_text_matches(workspace, min_score=min_score)
    except Exception as exc:
        return WorkerOutput.error(
            worker_name=WORKER_NAME,
            backend=BACKEND,
            message=str(exc),
            provenance=fallback_provenance,
        )
    provenance = result.get('provenance') or fallback_provenance
    match_count = int(result.get('match_count') or 0)
    avg_match_score = float(result.get('avg_match_score') or 0.0)
    status = str(result.get('status') or 'warning')
    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='ok' if status in {'ok', 'warning'} else 'warning',
        artifacts=list(result.get('artifacts') or []),
        signals=[
            {
                'id': 'ocr_vector_text_match',
                'score': avg_match_score,
                'evidence': [f'match_count={match_count}', f'avg_match_score={avg_match_score}'],
            }
        ],
        warnings=list(result.get('warnings') or []),
        metrics={
            'ocr_region_count': result.get('ocr_region_count'),
            'vector_text_count': result.get('vector_text_count'),
            'match_count': match_count,
            'avg_match_score': avg_match_score,
            'min_score': min_score,
        },
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
