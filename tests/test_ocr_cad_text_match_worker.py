from __future__ import annotations

import json
from pathlib import Path

from src.ocr.cad_text_matching import (
    build_ocr_cad_text_matches,
    collect_cad_texts,
    write_ocr_cad_text_matches,
)
from src.workers.contracts import WorkerInput
from src.workers.ocr_cad_text_match_worker import run_worker


def _sample_fileized(tmp_path: Path) -> None:
    json_dir = tmp_path / 'fileized' / 'json'
    json_dir.mkdir(parents=True)
    (json_dir / 'sample.json').write_text(json.dumps({
        'file_id': 'sample',
        'relative_path': 'sample.dxf',
        'entities': [
            {'entity_type': 'TEXT', 'handle': 'T1', 'layer': 'ROOM', 'text': '사무실', 'bbox': [0, 0, 10, 10]},
            {'entity_type': 'MTEXT', 'handle': 'M1', 'layer': 'NOTE', 'text': '복도'},
            {'entity_type': 'LINE', 'handle': 'L1', 'layer': 'WALL'},
        ],
    }, ensure_ascii=False), encoding='utf-8')


def test_collect_cad_texts_extracts_text_and_mtext(tmp_path: Path):
    _sample_fileized(tmp_path)
    rows = collect_cad_texts(tmp_path)
    assert len(rows) == 2
    assert rows[0]['text'] == '사무실'
    assert rows[1]['entity_type'] == 'MTEXT'


def test_build_ocr_cad_text_matches_text_similarity_primary():
    ocr_regions = [
        {'text': '사무실', 'confidence': 0.95, 'source_pdf': 'sample.pdf', 'page_index': 0, 'page_contract_id': 'sample:p1', 'pdf_bbox': [0, 0, 10, 10]},
        {'text': '창고', 'confidence': 0.9, 'source_pdf': 'sample.pdf', 'page_index': 0, 'page_contract_id': 'sample:p1', 'pdf_bbox': [100, 100, 110, 110]},
    ]
    cad_texts = [
        {'text': '사무실', 'file_id': 'sample', 'relative_path': 'sample.dxf', 'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'ROOM', 'bbox': [0, 0, 10, 10]},
        {'text': '복도', 'file_id': 'sample', 'relative_path': 'sample.dxf', 'handle': 'T2', 'entity_type': 'TEXT', 'layer': 'ROOM'},
    ]
    report = build_ocr_cad_text_matches(ocr_regions, cad_texts)
    assert report['summary']['ocr_region_count'] == 2
    assert report['summary']['cad_text_count'] == 2
    assert report['summary']['match_count'] == 1
    assert report['summary']['unmatched_ocr_count'] == 1
    assert report['matches'][0]['ocr_text'] == '사무실'
    assert report['matches'][0]['cad_text'] == '사무실'
    assert report['matches'][0]['match_score'] == 1.0


def test_write_ocr_cad_text_matches_empty_workspace(tmp_path: Path):
    result = write_ocr_cad_text_matches(tmp_path)
    assert result['status'] in {'ok', 'warning'}
    assert result['ocr_region_count'] == 0
    assert result['cad_text_count'] == 0
    assert (tmp_path / 'OCR_CAD_TEXT_MATCHES.json').exists()
    assert (tmp_path / 'OCR_CAD_TEXT_MATCH_REPORT.md').exists()


def test_write_ocr_cad_text_matches_with_artifacts(tmp_path: Path):
    _sample_fileized(tmp_path)
    (tmp_path / 'OCR_TEXT_REGIONS.json').write_text(json.dumps({
        'regions': [{'text': '사무실', 'confidence': 0.9, 'pdf_bbox': [0, 0, 10, 10]}]
    }, ensure_ascii=False), encoding='utf-8')
    result = write_ocr_cad_text_matches(tmp_path)
    assert result['status'] == 'ok'
    assert result['match_count'] == 1
    payload = json.loads((tmp_path / 'OCR_CAD_TEXT_MATCHES.json').read_text(encoding='utf-8'))
    assert payload['summary']['avg_text_similarity'] == 1.0


def test_ocr_cad_text_match_worker_run_empty_workspace(tmp_path: Path):
    worker_input = WorkerInput(worker_name='ocr_cad_text_match', task='run', workspace=str(tmp_path))
    output = run_worker(worker_input)
    assert output.status in {'ok', 'warning'}
    assert any(path.endswith('OCR_CAD_TEXT_MATCHES.json') for path in output.artifacts)
    assert 'match_count' in output.metrics
