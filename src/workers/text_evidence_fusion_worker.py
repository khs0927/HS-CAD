from __future__ import annotations

import sys
from pathlib import Path

from src.ocr.text_evidence_fusion import write_text_evidence_fusion
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'text_evidence_fusion'
BACKEND = 'text_evidence_fusion'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    review_threshold = float(worker_input.options.get('review_threshold') or 0.55)
    conflict_threshold = float(worker_input.options.get('conflict_threshold') or 0.35)
    fallback_provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='weighted_text_evidence_score_v1',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_text_evidence_fusion(
            workspace,
            review_threshold=review_threshold,
            conflict_threshold=conflict_threshold,
        )
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=fallback_provenance)
    provenance = result.get('provenance') or fallback_provenance
    item_count = int(result.get('item_count') or 0)
    avg_confidence = float(result.get('avg_confidence') or 0.0)
    status = str(result.get('status') or 'warning')
    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='ok' if status in {'ok', 'warning'} else 'warning',
        artifacts=list(result.get('artifacts') or []),
        signals=[
            {
                'id': 'text_evidence_fusion',
                'score': avg_confidence,
                'evidence': [f'item_count={item_count}', f'avg_confidence={avg_confidence}'],
            }
        ],
        warnings=list(result.get('warnings') or []),
        metrics={
            'item_count': item_count,
            'review_required_count': result.get('review_required_count'),
            'avg_confidence': avg_confidence,
            'review_threshold': review_threshold,
            'conflict_threshold': conflict_threshold,
            'policy_source': result.get('policy_source'),
            'weights': result.get('weights'),
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
