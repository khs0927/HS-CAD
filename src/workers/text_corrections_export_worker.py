from __future__ import annotations

import sys
from pathlib import Path

from src.ocr.text_corrections_export import write_text_corrections_export
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'text_corrections_export'
BACKEND = 'text_corrections_export'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    fallback_provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='review_queue_csv_and_correction_template_v1',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_text_corrections_export(workspace)
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=fallback_provenance)
    provenance = result.get('provenance') or fallback_provenance
    queue_count = int(result.get('queue_count') or 0)
    status = str(result.get('status') or 'warning')
    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='ok' if status in {'ok', 'warning'} else 'warning',
        artifacts=list(result.get('artifacts') or []),
        signals=[
            {
                'id': 'text_corrections_export',
                'score': 1.0 if queue_count else 0.0,
                'evidence': [f'queue_count={queue_count}'],
            }
        ],
        warnings=list(result.get('warnings') or []),
        metrics={
            'queue_count': queue_count,
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
