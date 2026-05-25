from __future__ import annotations

from pathlib import Path

from src.ocr.text_region_analysis import OCRTextRegionAnalyzer, write_ocr_text_regions
from src.workers.contracts import WorkerInput
from src.workers.ocr_text_region_worker import run_worker


def test_ocr_text_region_empty_workspace_writes_warning_artifacts(tmp_path: Path):
    result = write_ocr_text_regions(tmp_path)

    assert result['backend'] == 'ocr_text_region_analysis'
    assert result['status'] == 'warning'
    assert result['image_count'] == 0
    assert result['region_count'] == 0
    assert (tmp_path / 'OCR_TEXT_REGIONS.json').exists()
    assert (tmp_path / 'OCR_REGION_ANALYSIS.json').exists()
    assert (tmp_path / 'OCR_REGION_REPORT.md').exists()
    assert 'paddleocr' in result['availability']


def test_ocr_text_region_worker_returns_warning_without_images(tmp_path: Path):
    output = run_worker(WorkerInput(workspace=str(tmp_path), options={'language': 'korean'}))

    assert output.worker_name == 'ocr_text_region'
    assert output.backend == 'ocr_text_region_analysis'
    assert output.status == 'ok'
    assert output.metrics['image_count'] == 0
    assert output.metrics['region_count'] == 0
    assert any('no rendered images' in warning for warning in output.warnings)


def test_ocr_text_region_availability_contract():
    availability = OCRTextRegionAnalyzer().availability()

    assert 'paddleocr' in availability
    assert 'available' in availability['paddleocr']
