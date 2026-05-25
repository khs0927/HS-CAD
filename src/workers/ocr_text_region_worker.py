from __future__ import annotations

import sys
from pathlib import Path

from src.ocr.text_region_analysis import write_ocr_text_regions
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'ocr_text_region'
BACKEND = 'ocr_text_region_analysis'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    max_images = int(worker_input.options.get('max_images') or 20)
    language = str(worker_input.options.get('language') or 'korean')
    fallback_provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='paddleocr_text_regions_with_pdf_coordinate_contract',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_ocr_text_regions(workspace, max_images=max_images, language=language)
    except Exception as exc:
        return WorkerOutput.error(
            worker_name=WORKER_NAME,
            backend=BACKEND,
            message=str(exc),
            provenance=fallback_provenance,
        )
    provenance = result.get('provenance') or fallback_provenance
    status = str(result.get('status') or 'warning')
    region_count = int(result.get('region_count') or 0)
    image_count = int(result.get('image_count') or 0)
    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='ok' if status in {'ok', 'warning'} else 'warning',
        artifacts=list(result.get('artifacts') or []) + [str(workspace / 'OCR_REGION_ANALYSIS.json')],
        signals=[
            {
                'id': 'ocr_text_regions',
                'score': 1.0 if region_count else 0.0,
                'evidence': [f'region_count={region_count}', f'image_count={image_count}'],
            },
            {
                'id': 'ocr_pdf_coordinate_alignment',
                'score': 1.0 if region_count and (workspace / 'PDF_COORDINATE_CONTRACT.json').exists() else 0.0,
                'evidence': [f'has_pdf_coordinate_contract={(workspace / "PDF_COORDINATE_CONTRACT.json").exists()}'],
            },
        ],
        warnings=list(result.get('warnings') or []),
        metrics={
            'image_count': image_count,
            'region_count': region_count,
            'availability': result.get('availability'),
            'language': language,
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
