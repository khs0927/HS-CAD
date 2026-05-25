from __future__ import annotations

import sys
from pathlib import Path

from src.ocr.text_corrections_apply import write_text_corrections_apply
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'text_corrections_apply'
BACKEND = 'text_corrections_apply'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    fallback_provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='human_correction_overlay_v1',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_text_corrections_apply(workspace)
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=fallback_provenance)
    provenance = result.get('provenance') or fallback_provenance
    applied_count = int(result.get('applied_count') or 0)
    correction_count = int(result.get('correction_count') or 0)
    status = str(result.get('status') or 'warning')
    score = (applied_count / correction_count) if correction_count else 0.0
    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='ok' if status in {'ok', 'warning'} else 'warning',
        artifacts=list(result.get('artifacts') or []),
        signals=[
            {
                'id': 'text_corrections_apply',
                'score': max(0.0, min(1.0, score)),
                'evidence': [f'correction_count={correction_count}', f'applied_count={applied_count}'],
            }
        ],
        warnings=list(result.get('warnings') or []),
        metrics={
            'correction_count': correction_count,
            'applied_count': applied_count,
            'accepted_count': result.get('accepted_count'),
            'corrected_count': result.get('corrected_count'),
            'rejected_count': result.get('rejected_count'),
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
