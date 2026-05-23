from __future__ import annotations

import sys
from pathlib import Path

from src.ocr.text_review_queue import write_text_review_queue
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'text_review_queue'
BACKEND = 'text_review_queue'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    include_all = bool(worker_input.options.get('include_all') or False)
    fallback_provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='review_required_text_items_v1',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_text_review_queue(workspace, include_all=include_all)
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=fallback_provenance)
    provenance = result.get('provenance') or fallback_provenance
    queue_count = int(result.get('queue_count') or 0)
    source_item_count = int(result.get('source_item_count') or 0)
    status = str(result.get('status') or 'warning')
    score = 1.0 - (queue_count / source_item_count) if source_item_count else 1.0
    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='ok' if status in {'ok', 'warning'} else 'warning',
        artifacts=list(result.get('artifacts') or []),
        signals=[
            {
                'id': 'text_review_queue',
                'score': max(0.0, min(1.0, score)),
                'evidence': [f'queue_count={queue_count}', f'source_item_count={source_item_count}'],
            }
        ],
        warnings=list(result.get('warnings') or []),
        metrics={
            'source_item_count': source_item_count,
            'queue_count': queue_count,
            'high_conflict_count': result.get('high_conflict_count'),
            'low_confidence_count': result.get('low_confidence_count'),
            'include_all': include_all,
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
