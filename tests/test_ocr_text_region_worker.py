from __future__ import annotations

import json
from pathlib import Path

from src.ocr.text_region_analysis import (
    OCRTextRegionAnalyzer,
    _infer_contract_for_image,
    _points_to_bbox,
    write_ocr_text_regions,
)
from src.workers.contracts import WorkerInput
from src.workers.runner import WorkerRunner


def test_ocr_availability_never_raises():
    availability = OCRTextRegionAnalyzer().availability()
    assert 'paddleocr' in availability
    assert 'available' in availability['paddleocr']


def test_points_to_bbox():
    assert _points_to_bbox([[0, 1], [10, 2], [9, 20], [1, 19]]) == [0.0, 1.0, 10.0, 20.0]
    assert _points_to_bbox([]) == [0.0, 0.0, 0.0, 0.0]


def test_infer_contract_for_rendered_image(tmp_path: Path):
    image = tmp_path / 'sample_p2_180dpi.png'
    image.write_text('x', encoding='utf-8')
    contract = _infer_contract_for_image(image, {
        'sample:p1': {'source_pdf': 'sample.pdf', 'page_index': 0, 'page_contract_id': 'sample:p1'},
        'sample:p2': {'source_pdf': 'sample.pdf', 'page_index': 1, 'page_contract_id': 'sample:p2'},
    })
    assert contract is not None
    assert contract['page_contract_id'] == 'sample:p2'


def test_ocr_no_images_workspace_writes_artifacts(tmp_path: Path):
    result = write_ocr_text_regions(tmp_path, max_images=1)
    assert result['status'] in {'ok', 'warning'}
    assert result['image_count'] == 0
    assert (tmp_path / 'OCR_REGION_ANALYSIS.json').exists()
    assert (tmp_path / 'OCR_TEXT_REGIONS.json').exists()
    assert (tmp_path / 'OCR_REGION_REPORT.md').exists()
    payload = json.loads((tmp_path / 'OCR_TEXT_REGIONS.json').read_text(encoding='utf-8'))
    assert payload['backend'] == 'ocr_text_region_analysis'
    assert payload['region_count'] == 0


def test_ocr_worker_registered_and_plans_command():
    runner = WorkerRunner(record_runs=False)
    worker_input = WorkerInput(worker_name='ocr_text_region', task='run', workspace='outputs/sample')
    plan = runner.dry_run('ocr_text_region', worker_input)
    assert plan['worker']['name'] == 'ocr_text_region'
    assert 'OCR_TEXT_REGIONS.json' in plan['worker']['outputs']
    assert 'src.workers.ocr_text_region_worker' in plan['command']


def test_ocr_worker_run_no_images_does_not_crash(tmp_path: Path):
    runner = WorkerRunner(record_runs=True)
    worker_input = WorkerInput(worker_name='ocr_text_region', task='run', workspace=str(tmp_path), options={'max_images': 1})
    output = runner.run('ocr_text_region', worker_input)
    assert output.status in {'ok', 'warning'}
    assert (tmp_path / 'WORKER_RUNS.json').exists()
    assert (tmp_path / 'WORKER_AUDIT.json').exists()
    assert any(path.endswith('OCR_REGION_ANALYSIS.json') for path in output.artifacts)
    assert any(path.endswith('OCR_TEXT_REGIONS.json') for path in output.artifacts)
    assert 'region_count' in output.metrics
