from __future__ import annotations

import json
from pathlib import Path

from src.ocr.vector_text_matching import (
    build_ocr_vector_text_matches,
    normalized_text_similarity,
    write_ocr_vector_text_matches,
)
from src.workers.contracts import WorkerInput
from src.workers.runner import WorkerRunner


def test_normalized_text_similarity():
    assert normalized_text_similarity(' 사무실 ', '사무실') == 1.0
    assert normalized_text_similarity('', '사무실') == 0.0
    assert normalized_text_similarity('ABC', 'ABD') > 0.6


def test_build_ocr_vector_text_matches_same_page_contract():
    ocr_regions = [
        {
            'source_pdf': 'sample.pdf',
            'page_index': 0,
            'page_contract_id': 'sample:p1',
            'text': '사무실',
            'confidence': 0.95,
            'pdf_bbox': [0, 0, 10, 10],
        },
        {
            'source_pdf': 'sample.pdf',
            'page_index': 1,
            'page_contract_id': 'sample:p2',
            'text': '복도',
            'confidence': 0.9,
            'pdf_bbox': [0, 0, 10, 10],
        },
    ]
    vector_objects = [
        {
            'source_pdf': 'sample.pdf',
            'page_index': 0,
            'page_contract_id': 'sample:p1',
            'object_type': 'char',
            'text': '사무실',
            'pdf_bbox': [0, 0, 10, 10],
        },
        {
            'source_pdf': 'sample.pdf',
            'page_index': 0,
            'page_contract_id': 'sample:p1',
            'object_type': 'char',
            'text': '창고',
            'pdf_bbox': [100, 100, 110, 110],
        },
    ]
    report = build_ocr_vector_text_matches(ocr_regions, vector_objects)
    assert report['summary']['ocr_region_count'] == 2
    assert report['summary']['vector_text_count'] == 2
    assert report['summary']['match_count'] == 1
    assert report['summary']['unmatched_ocr_count'] == 1
    assert report['matches'][0]['ocr_text'] == '사무실'
    assert report['matches'][0]['vector_text'] == '사무실'
    assert report['matches'][0]['match_score'] == 1.0


def test_write_ocr_vector_text_matches_empty_workspace(tmp_path: Path):
    result = write_ocr_vector_text_matches(tmp_path)
    assert result['status'] in {'ok', 'warning'}
    assert result['ocr_region_count'] == 0
    assert result['vector_text_count'] == 0
    assert (tmp_path / 'OCR_VECTOR_TEXT_MATCHES.json').exists()
    assert (tmp_path / 'OCR_VECTOR_TEXT_MATCH_REPORT.md').exists()


def test_write_ocr_vector_text_matches_with_artifacts(tmp_path: Path):
    (tmp_path / 'OCR_TEXT_REGIONS.json').write_text(json.dumps({
        'regions': [
            {
                'source_pdf': 'sample.pdf',
                'page_index': 0,
                'page_contract_id': 'sample:p1',
                'text': 'A101',
                'confidence': 0.9,
                'pdf_bbox': [0, 0, 10, 10],
            }
        ]
    }, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'PDF_VECTOR_OBJECTS.json').write_text(json.dumps({
        'objects': [
            {
                'source_pdf': 'sample.pdf',
                'page_index': 0,
                'page_contract_id': 'sample:p1',
                'object_type': 'char',
                'text': 'A101',
                'pdf_bbox': [0, 0, 10, 10],
            }
        ]
    }, ensure_ascii=False), encoding='utf-8')
    result = write_ocr_vector_text_matches(tmp_path)
    assert result['status'] == 'ok'
    assert result['match_count'] == 1
    payload = json.loads((tmp_path / 'OCR_VECTOR_TEXT_MATCHES.json').read_text(encoding='utf-8'))
    assert payload['summary']['avg_match_score'] == 1.0


def test_ocr_vector_text_match_worker_registered_and_plans_command():
    runner = WorkerRunner(record_runs=False)
    worker_input = WorkerInput(worker_name='ocr_vector_text_match', task='run', workspace='outputs/sample')
    plan = runner.dry_run('ocr_vector_text_match', worker_input)
    assert plan['worker']['name'] == 'ocr_vector_text_match'
    assert 'OCR_VECTOR_TEXT_MATCHES.json' in plan['worker']['outputs']
    assert 'src.workers.ocr_vector_text_match_worker' in plan['command']


def test_ocr_vector_text_match_worker_run_empty_workspace(tmp_path: Path):
    runner = WorkerRunner(record_runs=True)
    worker_input = WorkerInput(worker_name='ocr_vector_text_match', task='run', workspace=str(tmp_path))
    output = runner.run('ocr_vector_text_match', worker_input)
    assert output.status in {'ok', 'warning'}
    assert (tmp_path / 'WORKER_RUNS.json').exists()
    assert (tmp_path / 'WORKER_AUDIT.json').exists()
    assert any(path.endswith('OCR_VECTOR_TEXT_MATCHES.json') for path in output.artifacts)
    assert 'match_count' in output.metrics
