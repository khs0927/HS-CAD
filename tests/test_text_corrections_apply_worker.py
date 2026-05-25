from __future__ import annotations

import csv
import json
from pathlib import Path

from src.ocr.text_corrections_apply import apply_text_corrections, load_text_corrections, write_text_corrections_apply
from src.workers.contracts import WorkerInput
from src.workers.text_corrections_apply_worker import run_worker


def _fusion_payload():
    return {
        'items': [
            {'target_id': 'ocr:1', 'text': '사무실', 'confidence': 0.4, 'review_required': True},
            {'target_id': 'ocr:2', 'text': '복도', 'confidence': 0.8, 'review_required': False},
        ]
    }


def test_apply_text_corrections_corrected_and_rejected():
    result = apply_text_corrections(_fusion_payload(), [
        {'target_id': 'ocr:1', 'correction_status': 'corrected', 'corrected_text': '사무소', 'reviewer_note': '도면 표기 확인'},
        {'target_id': 'ocr:2', 'correction_status': 'rejected', 'reviewer_note': '오검출'},
    ])
    corrected_items = result['corrected_fusion']['items']
    assert result['summary']['applied_count'] == 2
    assert result['summary']['corrected_count'] == 1
    assert result['summary']['rejected_count'] == 1
    assert corrected_items[0]['final_text'] == '사무소'
    assert corrected_items[0]['usable'] is True
    assert corrected_items[0]['human_verified'] is True
    assert corrected_items[1]['usable'] is False


def test_load_text_corrections_prefers_json(tmp_path: Path):
    (tmp_path / 'TEXT_CORRECTIONS_TEMPLATE.json').write_text(json.dumps({
        'corrections': [{'target_id': 'ocr:1', 'correction_status': 'accepted'}]
    }, ensure_ascii=False), encoding='utf-8')
    rows = load_text_corrections(tmp_path)
    assert rows[0]['target_id'] == 'ocr:1'


def test_load_text_corrections_from_csv(tmp_path: Path):
    with (tmp_path / 'TEXT_CORRECTIONS_TEMPLATE.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['target_id', 'correction_status', 'corrected_text'])
        writer.writeheader()
        writer.writerow({'target_id': 'ocr:1', 'correction_status': 'corrected', 'corrected_text': '사무소'})
    rows = load_text_corrections(tmp_path)
    assert rows[0]['corrected_text'] == '사무소'


def test_write_text_corrections_apply_empty_workspace(tmp_path: Path):
    result = write_text_corrections_apply(tmp_path)
    assert result['status'] in {'ok', 'warning'}
    assert result['correction_count'] == 0
    assert (tmp_path / 'TEXT_CORRECTIONS_APPLIED.json').exists()
    assert (tmp_path / 'TEXT_EVIDENCE_FUSION_CORRECTED.json').exists()
    assert (tmp_path / 'TEXT_CORRECTIONS_APPLY_REPORT.md').exists()


def test_write_text_corrections_apply_with_artifacts(tmp_path: Path):
    (tmp_path / 'TEXT_EVIDENCE_FUSION.json').write_text(json.dumps(_fusion_payload(), ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'TEXT_CORRECTIONS_TEMPLATE.json').write_text(json.dumps({
        'corrections': [{'target_id': 'ocr:1', 'correction_status': 'corrected', 'corrected_text': '사무소'}]
    }, ensure_ascii=False), encoding='utf-8')
    result = write_text_corrections_apply(tmp_path)
    assert result['status'] == 'ok'
    assert result['applied_count'] == 1
    corrected = json.loads((tmp_path / 'TEXT_EVIDENCE_FUSION_CORRECTED.json').read_text(encoding='utf-8'))
    assert corrected['items'][0]['final_text'] == '사무소'
    applied = json.loads((tmp_path / 'TEXT_CORRECTIONS_APPLIED.json').read_text(encoding='utf-8'))
    assert applied['summary']['corrected_count'] == 1


def test_text_corrections_apply_worker_run_empty_workspace(tmp_path: Path):
    worker_input = WorkerInput(worker_name='text_corrections_apply', task='run', workspace=str(tmp_path))
    output = run_worker(worker_input)
    assert output.status in {'ok', 'warning'}
    assert any(path.endswith('TEXT_CORRECTIONS_APPLIED.json') for path in output.artifacts)
    assert 'applied_count' in output.metrics
