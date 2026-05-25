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
from src.workers.ocr_text_region_worker import run_worker


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


def test_ocr_worker_run_no_images_does_not_crash(tmp_path: Path):
    worker_input = WorkerInput(worker_name='ocr_text_region', task='run', workspace=str(tmp_path), options={'max_images': 1})
    output = run_worker(worker_input)
    assert output.status in {'ok', 'warning'}
    assert any(path.endswith('OCR_REGION_ANALYSIS.json') for path in output.artifacts)
    assert any(path.endswith('OCR_TEXT_REGIONS.json') for path in output.artifacts)
    assert 'region_count' in output.metrics
