from __future__ import annotations

import json
from pathlib import Path

from src.pdf_raster.pdf_raster_analysis import (
    PDFRasterAnalyzer,
    bbox_iou,
    normalize_bbox,
    pixel_bbox_to_pdf_bbox,
    write_pdf_raster_analysis,
)
from src.workers.contracts import WorkerInput
from src.workers.runner import WorkerRunner


def test_pdf_raster_availability_never_raises():
    availability = PDFRasterAnalyzer().availability()
    assert 'pymupdf' in availability
    assert 'pdfplumber' in availability
    assert 'opencv' in availability
    assert 'numpy' in availability
    for info in availability.values():
        assert 'available' in info
        assert 'reason' in info


def test_bbox_helpers_for_future_vector_raster_iou():
    contract = {
        'pixel_to_pdf_scale_x': 0.5,
        'pixel_to_pdf_scale_y': 0.25,
        'page_width_pdf': 100.0,
        'page_height_pdf': 50.0,
    }
    pdf_bbox = pixel_bbox_to_pdf_bbox([10, 20, 30, 60], contract)
    assert pdf_bbox == [5.0, 5.0, 15.0, 15.0]
    assert normalize_bbox(pdf_bbox, 100.0, 50.0) == [0.05, 0.1, 0.15, 0.3]
    assert bbox_iou([0, 0, 10, 10], [5, 5, 15, 15]) == 0.142857
    assert bbox_iou([0, 0, 1, 1], [2, 2, 3, 3]) == 0.0


def test_pdf_raster_no_pdf_workspace_writes_artifacts(tmp_path: Path):
    result = write_pdf_raster_analysis(tmp_path, dpi=72, max_pages=1)
    assert result['status'] in {'ok', 'warning'}
    assert result['pdf_count'] == 0
    assert (tmp_path / 'PDF_RASTER_ANALYSIS.json').exists()
    assert (tmp_path / 'PDF_COORDINATE_CONTRACT.json').exists()
    assert (tmp_path / 'PDF_VECTOR_OBJECTS.json').exists()
    assert (tmp_path / 'RASTER_CONTOURS.json').exists()
    assert (tmp_path / 'PDF_RASTER_REPORT.md').exists()
    payload = json.loads((tmp_path / 'PDF_RASTER_ANALYSIS.json').read_text(encoding='utf-8'))
    assert payload['provenance']['backend'] == 'pdf_raster_analysis'
    contract = json.loads((tmp_path / 'PDF_COORDINATE_CONTRACT.json').read_text(encoding='utf-8'))
    assert contract['contract_version'] == '1.0'
    assert 'pdf_points_top_left' in contract['coordinate_spaces']


def test_pdf_raster_worker_registered_and_plans_command():
    runner = WorkerRunner(record_runs=False)
    worker_input = WorkerInput(worker_name='pdf_raster', task='run', workspace='outputs/sample')
    plan = runner.dry_run('pdf_raster', worker_input)
    assert plan['worker']['name'] == 'pdf_raster'
    assert 'PDF_COORDINATE_CONTRACT.json' in plan['worker']['outputs']
    assert 'src.workers.pdf_raster_worker' in plan['command']


def test_pdf_raster_worker_run_no_pdf_does_not_crash(tmp_path: Path):
    runner = WorkerRunner(record_runs=True)
    worker_input = WorkerInput(
        worker_name='pdf_raster',
        task='run',
        workspace=str(tmp_path),
        options={'dpi': 72, 'max_pages': 1},
    )
    output = runner.run('pdf_raster', worker_input)
    assert output.status in {'ok', 'warning'}
    assert (tmp_path / 'WORKER_RUNS.json').exists()
    assert (tmp_path / 'WORKER_AUDIT.json').exists()
    assert any(path.endswith('PDF_RASTER_ANALYSIS.json') for path in output.artifacts)
    assert any(path.endswith('PDF_COORDINATE_CONTRACT.json') for path in output.artifacts)
    assert 'page_contract_count' in output.metrics
