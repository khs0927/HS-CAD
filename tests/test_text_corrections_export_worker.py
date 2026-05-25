from __future__ import annotations

import csv
import json
from pathlib import Path

from src.ocr.text_corrections_export import build_text_corrections_template, write_text_corrections_export
from src.workers.contracts import WorkerInput
from src.workers.runner import WorkerRunner


def _queue_items():
    return [
        {
            'review_rank': 1,
            'target_id': 'ocr:1',
            'text': '사무실',
            'confidence': 0.42,
            'conflict_score': 0.8,
            'coverage_score': 0.6,
            'review_reasons': ['text_conflict', 'low_confidence'],
            'source_pdf': 'sample.pdf',
            'page_index': 0,
            'page_contract_id': 'sample:p1',
            'pdf_bbox': [0, 0, 10, 10],
            'signals': {'ocr_text': '사무실', 'cad_text': '사무소'},
        }
    ]


def test_build_text_corrections_template_defaults_pending():
    payload = build_text_corrections_template(_queue_items())
    assert payload['schema_version'] == '1.0'
    assert payload['summary']['correction_count'] == 1
    row = payload['corrections'][0]
    assert row['target_id'] == 'ocr:1'
    assert row['correction_status'] == 'pending'
    assert row['corrected_text'] == ''
    assert 'corrected' in payload['instructions']['correction_status_allowed']


def test_write_text_corrections_export_empty_workspace(tmp_path: Path):
    result = write_text_corrections_export(tmp_path)
    assert result['status'] in {'ok', 'warning'}
    assert result['queue_count'] == 0
    assert (tmp_path / 'TEXT_REVIEW_QUEUE.csv').exists()
    assert (tmp_path / 'TEXT_CORRECTIONS_TEMPLATE.json').exists()
    assert (tmp_path / 'TEXT_CORRECTIONS_TEMPLATE.csv').exists()
    assert (tmp_path / 'TEXT_CORRECTIONS_EXPORT_REPORT.md').exists()


def test_write_text_corrections_export_with_queue(tmp_path: Path):
    (tmp_path / 'TEXT_REVIEW_QUEUE.json').write_text(json.dumps({'items': _queue_items()}, ensure_ascii=False), encoding='utf-8')
    result = write_text_corrections_export(tmp_path)
    assert result['status'] == 'ok'
    assert result['queue_count'] == 1
    template = json.loads((tmp_path / 'TEXT_CORRECTIONS_TEMPLATE.json').read_text(encoding='utf-8'))
    assert template['corrections'][0]['target_id'] == 'ocr:1'
    with (tmp_path / 'TEXT_CORRECTIONS_TEMPLATE.csv').open('r', encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert rows[0]['target_id'] == 'ocr:1'
    assert rows[0]['correction_status'] == 'pending'


def test_text_corrections_export_worker_registered_and_plans_command():
    runner = WorkerRunner(record_runs=False)
    worker_input = WorkerInput(worker_name='text_corrections_export', task='run', workspace='outputs/sample')
    plan = runner.dry_run('text_corrections_export', worker_input)
    assert plan['worker']['name'] == 'text_corrections_export'
    assert 'TEXT_CORRECTIONS_TEMPLATE.json' in plan['worker']['outputs']
    assert 'src.workers.text_corrections_export_worker' in plan['command']


def test_text_corrections_export_worker_run_empty_workspace(tmp_path: Path):
    runner = WorkerRunner(record_runs=True)
    worker_input = WorkerInput(worker_name='text_corrections_export', task='run', workspace=str(tmp_path))
    output = runner.run('text_corrections_export', worker_input)
    assert output.status in {'ok', 'warning'}
    assert (tmp_path / 'WORKER_RUNS.json').exists()
    assert (tmp_path / 'WORKER_AUDIT.json').exists()
    assert any(path.endswith('TEXT_CORRECTIONS_TEMPLATE.json') for path in output.artifacts)
    assert 'queue_count' in output.metrics
