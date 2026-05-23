from __future__ import annotations

import sys
from pathlib import Path

from src.ocr.text_weight_suggestions import write_text_weight_suggestions
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'text_weight_suggestions'
BACKEND = 'text_weight_suggestions'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    fallback_provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='backend_reliability_weight_suggestions_v1',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_text_weight_suggestions(workspace)
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=fallback_provenance)
    provenance = result.get('provenance') or fallback_provenance
    suggested_weights = result.get('suggested_weights') or {}
    has_calibration_data = bool(result.get('has_calibration_data'))
    status = str(result.get('status') or 'warning')
    score = 1.0 if has_calibration_data else 0.0
    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='ok' if status in {'ok', 'warning'} else 'warning',
        artifacts=list(result.get('artifacts') or []),
        signals=[
            {
                'id': 'text_weight_suggestions',
                'score': score,
                'evidence': [f'has_calibration_data={has_calibration_data}', f'suggested_weights={suggested_weights}'],
            }
        ],
        warnings=list(result.get('warnings') or []),
        metrics={
            'has_calibration_data': has_calibration_data,
            'suggested_weights': suggested_weights,
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
