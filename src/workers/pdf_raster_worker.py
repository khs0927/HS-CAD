from __future__ import annotations

import sys
from pathlib import Path

from src.pdf_raster.pdf_raster_analysis import write_pdf_raster_analysis
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'pdf_raster'
BACKEND = 'pdf_raster_analysis'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    dpi = int(worker_input.options.get('dpi') or 180)
    max_pages = int(worker_input.options.get('max_pages') or 3)
    fallback_provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='pymupdf_render_pdfplumber_vector_opencv_contours_with_coordinate_contract',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_pdf_raster_analysis(workspace, dpi=dpi, max_pages=max_pages)
    except Exception as exc:
        return WorkerOutput.error(
            worker_name=WORKER_NAME,
            backend=BACKEND,
            message=str(exc),
            provenance=fallback_provenance,
        )
    provenance = result.get('provenance') or fallback_provenance
    status = str(result.get('status') or 'warning')
    artifacts = list(result.get('artifacts') or [])
    artifacts.append(str(workspace / 'PDF_RASTER_ANALYSIS.json'))
    score = 1.0 if status == 'ok' else 0.4
    iou_summary = result.get('iou_summary') or {}
    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='ok' if status in {'ok', 'warning'} else 'warning',
        artifacts=artifacts,
        signals=[
            {
                'id': 'pdf_coordinate_contract',
                'score': 1.0 if result.get('page_contract_count') else 0.0,
                'evidence': [f"page_contract_count={result.get('page_contract_count')}"],
            },
            {
                'id': 'pdf_vector_objects',
                'score': 1.0 if result.get('vector_object_count') else 0.0,
                'evidence': [f"vector_object_count={result.get('vector_object_count')}"],
            },
            {
                'id': 'raster_contours',
                'score': 1.0 if result.get('contour_count') else 0.0,
                'evidence': [f"contour_count={result.get('contour_count')}"],
            },
            {
                'id': 'vector_raster_iou',
                'score': float(iou_summary.get('avg_iou') or 0.0),
                'evidence': [f"match_count={iou_summary.get('match_count')}", f"avg_iou={iou_summary.get('avg_iou')}"],
            },
            {
                'id': 'pdf_raster_analysis_complete',
                'score': score,
                'evidence': [f"pdf_count={result.get('pdf_count')}", f"status={status}"],
            },
        ],
        warnings=list(result.get('warnings') or []),
        metrics={
            'pdf_count': result.get('pdf_count'),
            'page_contract_count': result.get('page_contract_count'),
            'vector_object_count': result.get('vector_object_count'),
            'contour_count': result.get('contour_count'),
            'render_output_count': result.get('render_output_count'),
            'iou_summary': iou_summary,
            'availability': result.get('availability'),
        },
        provenance=provenance,
    )


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
