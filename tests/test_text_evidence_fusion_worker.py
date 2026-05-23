from __future__ import annotations

import json
from pathlib import Path

from src.ocr.text_evidence_fusion import build_text_evidence_fusion, write_text_evidence_fusion
from src.workers.contracts import WorkerInput
from src.workers.runner import WorkerRunner


def test_build_text_evidence_fusion_combines_sources():
    ocr_regions = [
        {'text': '사무실', 'confidence': 0.9, 'source_pdf': 'sample.pdf', 'page_index': 0, 'page_contract_id': 'sample:p1', 'pdf_bbox': [0, 0, 10, 10]},
        {'text': '창고', 'confidence': 0.4, 'source_pdf': 'sample.pdf', 'page_index': 0, 'page_contract_id': 'sample:p1', 'pdf_bbox': [20, 20, 30, 30]},
    ]
    vector_matches = [
        {'ocr_index': 0, 'vector_text': '사무실', 'match_score': 0.95, 'bbox_iou': 0.9, 'text_similarity': 1.0},
        {'ocr_index': 1, 'vector_text': '복도', 'match_score': 0.6, 'bbox_iou': 0.2, 'text_similarity': 0.1},
    ]
    cad_matches = [
        {'ocr_index': 0, 'cad_text': '사무실', 'match_score': 0.92, 'bbox_iou': 0.0, 'text_similarity': 1.0},
    ]
    report = build_text_evidence_fusion(ocr_regions, vector_matches, cad_matches)
    assert report['summary']['item_count'] == 2
    assert report['items'][0]['confidence'] > 0.8
    assert report['items'][0]['review_required'] is False
    assert report['items'][1]['review_required'] is True
    assert report['summary']['review_required_count'] >= 1


def test_text_evidence_fusion_flags_conflict():
    report = build_text_evidence_fusion(
        [{'text': 'A', 'confidence': 0.9}],
        [{'ocr_index': 0, 'vector_text': 'B', 'match_score': 0.9}],
        [{'ocr_index': 0, 'cad_text': 'C', 'match_score': 0.9}],
        conflict_threshold=0.35,
    )
    assert report['items'][0]['conflict_score'] >= 0.35
    assert report['items'][0]['review_required'] is True


def test_write_text_evidence_fusion_empty_workspace(tmp_path: Path):
    result = write_text_evidence_fusion(tmp_path)
    assert result['status'] in {'ok', 'warning'}
    assert result['item_count'] == 0
    assert (tmp_path / 'TEXT_EVIDENCE_FUSION.json').exists()
    assert (tmp_path / 'TEXT_EVIDENCE_FUSION_REPORT.md').exists()


def test_write_text_evidence_fusion_with_artifacts(tmp_path: Path):
    (tmp_path / 'OCR_TEXT_REGIONS.json').write_text(json.dumps({
        'regions': [{'text': 'A101', 'confidence': 0.9, 'source_pdf': 'sample.pdf', 'page_index': 0, 'page_contract_id': 'sample:p1'}]
    }, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'OCR_VECTOR_TEXT_MATCHES.json').write_text(json.dumps({
        'matches': [{'ocr_index': 0, 'vector_text': 'A101', 'match_score': 1.0, 'bbox_iou': 1.0, 'text_similarity': 1.0}]
    }, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'OCR_CAD_TEXT_MATCHES.json').write_text(json.dumps({
        'matches': [{'ocr_index': 0, 'cad_text': 'A101', 'match_score': 1.0, 'bbox_iou': 0.0, 'text_similarity': 1.0}]
    }, ensure_ascii=False), encoding='utf-8')
    result = write_text_evidence_fusion(tmp_path)
    assert result['status'] == 'ok'
    assert result['item_count'] == 1
    payload = json.loads((tmp_path / 'TEXT_EVIDENCE_FUSION.json').read_text(encoding='utf-8'))
    assert payload['items'][0]['confidence'] > 0.9
    assert payload['items'][0]['review_required'] is False
    assert payload['policy']['source'] == 'DEFAULT_TEXT_POLICY'


def test_text_evidence_fusion_uses_workspace_policy(tmp_path: Path):
    (tmp_path / 'TEXT_FUSION_POLICY.json').write_text(json.dumps({
        'version': 'custom-test-policy',
        'weights': {
            'ocr_confidence': 0.10,
            'vector_match': 0.0,
            'cad_match': 0.0,
            'coverage': 0.0,
            'conflict_penalty': 0.0,
        },
    }), encoding='utf-8')
    (tmp_path / 'OCR_TEXT_REGIONS.json').write_text(json.dumps({
        'regions': [{'text': 'A101', 'confidence': 0.9}]
    }), encoding='utf-8')
    result = write_text_evidence_fusion(tmp_path)
    payload = json.loads((tmp_path / 'TEXT_EVIDENCE_FUSION.json').read_text(encoding='utf-8'))
    assert result['policy_source'] == 'TEXT_FUSION_POLICY.json'
    assert payload['policy']['version'] == 'custom-test-policy'
    assert payload['policy']['weights']['ocr_confidence'] == 0.10
    assert payload['items'][0]['confidence'] == 0.09


def test_text_evidence_fusion_worker_registered_and_plans_command():
    runner = WorkerRunner(record_runs=False)
    worker_input = WorkerInput(worker_name='text_evidence_fusion', task='run', workspace='outputs/sample')
    plan = runner.dry_run('text_evidence_fusion', worker_input)
    assert plan['worker']['name'] == 'text_evidence_fusion'
    assert 'TEXT_EVIDENCE_FUSION.json' in plan['worker']['outputs']
    assert 'src.workers.text_evidence_fusion_worker' in plan['command']


def test_text_evidence_fusion_worker_run_empty_workspace(tmp_path: Path):
    runner = WorkerRunner(record_runs=True)
    worker_input = WorkerInput(worker_name='text_evidence_fusion', task='run', workspace=str(tmp_path))
    output = runner.run('text_evidence_fusion', worker_input)
    assert output.status in {'ok', 'warning'}
    assert (tmp_path / 'WORKER_RUNS.json').exists()
    assert (tmp_path / 'WORKER_AUDIT.json').exists()
    assert any(path.endswith('TEXT_EVIDENCE_FUSION.json') for path in output.artifacts)
    assert 'avg_confidence' in output.metrics
