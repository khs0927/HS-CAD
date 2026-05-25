from __future__ import annotations

import sys
from pathlib import Path

from src.ocr.text_calibration_report import write_text_calibration_report
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'text_calibration_report'
BACKEND = 'text_calibration_report'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    max_samples_per_status = int(worker_input.options.get('max_samples_per_status') or 5)
    fallback_provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='human_correction_calibration_summary_v1',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_text_calibration_report(workspace, max_samples_per_status=max_samples_per_status)
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=fallback_provenance)
    provenance = result.get('provenance') or fallback_provenance
    applied_count = int(result.get('applied_count') or 0)
    accuracy_proxy = float(result.get('accuracy_proxy') or 0.0)
    status = str(result.get('status') or 'warning')
    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='ok' if status in {'ok', 'warning'} else 'warning',
        artifacts=list(result.get('artifacts') or []),
        signals=[
            {
                'id': 'text_calibration_report',
                'score': accuracy_proxy,
                'evidence': [f'applied_count={applied_count}', f'accuracy_proxy={accuracy_proxy}'],
            }
        ],
        warnings=list(result.get('warnings') or []),
        metrics={
            'applied_count': applied_count,
            'accuracy_proxy': accuracy_proxy,
            'correction_rate': result.get('correction_rate'),
            'rejection_rate': result.get('rejection_rate'),
            'max_samples_per_status': max_samples_per_status,
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
