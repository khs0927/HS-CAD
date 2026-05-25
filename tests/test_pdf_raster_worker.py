from __future__ import annotations

import json
from pathlib import Path

from src.pdf_raster.contour_classification import (
    classify_contour,
    classify_contour_rows,
    contour_class_summary,
    postprocess_raster_contours,
)
from src.pdf_raster.pdf_raster_analysis import (
    PDFRasterAnalyzer,
    bbox_iou,
    build_vector_raster_iou_report,
    normalize_bbox,
    pixel_bbox_to_pdf_bbox,
    write_pdf_raster_analysis,
)
from src.workers.contracts import WorkerInput
from src.workers.pdf_raster_worker import run_worker


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
    contract = {'pixel_to_pdf_scale_x': 0.5, 'pixel_to_pdf_scale_y': 0.25, 'page_width_pdf': 100.0, 'page_height_pdf': 50.0}
    pdf_bbox = pixel_bbox_to_pdf_bbox([10, 20, 30, 60], contract)
    assert pdf_bbox == [5.0, 5.0, 15.0, 15.0]
    assert normalize_bbox(pdf_bbox, 100.0, 50.0) == [0.05, 0.1, 0.15, 0.3]
    assert bbox_iou([0, 0, 10, 10], [5, 5, 15, 15]) == 0.142857
    assert bbox_iou([0, 0, 1, 1], [2, 2, 3, 3]) == 0.0


def test_contour_classification_helpers():
    assert classify_contour(width=200, height=4, area=600)['contour_class'] == 'line_candidate'
    assert classify_contour(width=100, height=80, area=700)['contour_class'] == 'table_candidate'
    assert classify_contour(width=30, height=20, area=250)['contour_class'] == 'text_blob_candidate'
    rows = classify_contour_rows([
        {'width': 200, 'height': 4, 'area': 600},
        {'width': 30, 'height': 20, 'area': 250},
    ])
    summary = contour_class_summary(rows)
    assert summary['class_counts']['line_candidate'] == 1
    assert summary['class_counts']['text_blob_candidate'] == 1
    assert rows[0]['aspect_ratio'] >= 18


def test_postprocess_raster_contours_writes_class_artifact(tmp_path: Path):
    (tmp_path / 'RASTER_CONTOURS.json').write_text(json.dumps({
        'contours': [
            {'width': 200, 'height': 4, 'area': 600},
            {'width': 30, 'height': 20, 'area': 250},
        ]
    }), encoding='utf-8')
    result = postprocess_raster_contours(tmp_path)
    assert result['status'] == 'ok'
    assert (tmp_path / 'RASTER_CONTOUR_CLASSES.json').exists()
    payload = json.loads((tmp_path / 'RASTER_CONTOURS.json').read_text(encoding='utf-8'))
    assert payload['class_summary']['class_counts']['line_candidate'] == 1
    assert 'contour_class' in payload['contours'][0]


def test_vector_raster_iou_report_matches_same_page_contract():
    vector_objects = [
        {'source_pdf': 'sample.pdf', 'page_index': 0, 'page_contract_id': 'sample:p1', 'object_type': 'rect', 'text': None, 'pdf_bbox': [0, 0, 10, 10]},
        {'source_pdf': 'sample.pdf', 'page_index': 0, 'page_contract_id': 'sample:p1', 'object_type': 'char', 'text': 'A', 'pdf_bbox': [100, 100, 110, 110]},
    ]
    contours = [
        {'source_pdf': 'sample.pdf', 'page_index': 0, 'page_contract_id': 'sample:p1', 'contour_index': 7, 'pdf_bbox': [0, 0, 10, 10], 'contour_class': 'rectangle_candidate'},
        {'source_pdf': 'sample.pdf', 'page_index': 1, 'page_contract_id': 'sample:p2', 'contour_index': 8, 'pdf_bbox': [100, 100, 110, 110], 'contour_class': 'text_blob_candidate'},
    ]
    report = build_vector_raster_iou_report(vector_objects, contours)
    assert report['summary']['vector_count'] == 2
    assert report['summary']['contour_count'] == 2
    assert report['summary']['match_count'] == 1
    assert report['summary']['unmatched_vector_count'] == 1
    assert report['summary']['avg_iou'] == 1.0
    assert report['matches'][0]['contour_index'] == 7
    assert report['matches'][0]['contour_class'] == 'rectangle_candidate'
    assert report['summary']['object_type_summary']['rect']['match_count'] == 1


def test_pdf_raster_no_pdf_workspace_writes_artifacts(tmp_path: Path):
    result = write_pdf_raster_analysis(tmp_path, dpi=72, max_pages=1)
    assert result['status'] in {'ok', 'warning'}
    assert result['pdf_count'] == 0
    assert (tmp_path / 'PDF_RASTER_ANALYSIS.json').exists()
    assert (tmp_path / 'PDF_COORDINATE_CONTRACT.json').exists()
    assert (tmp_path / 'PDF_VECTOR_OBJECTS.json').exists()
    assert (tmp_path / 'RASTER_CONTOURS.json').exists()
    assert (tmp_path / 'PDF_VECTOR_RASTER_IOU.json').exists()
    assert (tmp_path / 'PDF_RASTER_REPORT.md').exists()
    payload = json.loads((tmp_path / 'PDF_RASTER_ANALYSIS.json').read_text(encoding='utf-8'))
    assert payload['provenance']['backend'] == 'pdf_raster_analysis'
    assert 'iou_summary' in payload
    contract = json.loads((tmp_path / 'PDF_COORDINATE_CONTRACT.json').read_text(encoding='utf-8'))
    assert contract['contract_version'] == '1.0'
    assert 'pdf_points_top_left' in contract['coordinate_spaces']
    iou = json.loads((tmp_path / 'PDF_VECTOR_RASTER_IOU.json').read_text(encoding='utf-8'))
    assert iou['summary']['vector_count'] == 0
    assert iou['summary']['match_count'] == 0


def test_pdf_raster_worker_run_no_pdf_does_not_crash(tmp_path: Path):
    worker_input = WorkerInput(worker_name='pdf_raster', task='run', workspace=str(tmp_path), options={'dpi': 72, 'max_pages': 1})
    output = run_worker(worker_input)
    assert output.status in {'ok', 'warning'}
    assert any(path.endswith('PDF_RASTER_ANALYSIS.json') for path in output.artifacts)
    assert any(path.endswith('PDF_COORDINATE_CONTRACT.json') for path in output.artifacts)
    assert any(path.endswith('PDF_VECTOR_RASTER_IOU.json') for path in output.artifacts)
    assert any(path.endswith('RASTER_CONTOUR_CLASSES.json') for path in output.artifacts)
    assert 'page_contract_count' in output.metrics
    assert 'iou_summary' in output.metrics
    assert 'contour_class_summary' in output.metrics
