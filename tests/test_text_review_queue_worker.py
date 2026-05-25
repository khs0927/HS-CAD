from __future__ import annotations

import pytest

import json
from pathlib import Path

from src.ocr.text_review_queue import build_text_review_queue, write_text_review_queue
from src.workers.contracts import WorkerInput
from src.workers.runner import WorkerRunner


def test_build_text_review_queue_filters_and_sorts():
    items = [
        {'target_id': 'a', 'text': '정상', 'confidence': 0.9, 'conflict_score': 0.0, 'coverage_score': 1.0, 'review_required': False},
        {'target_id': 'b', 'text': '충돌', 'confidence': 0.7, 'conflict_score': 0.8, 'coverage_score': 1.0, 'review_required': True},
        {'target_id': 'c', 'text': '낮음', 'confidence': 0.2, 'conflict_score': 0.1, 'coverage_score': 0.3, 'review_required': True},
    ]
    queue = build_text_review_queue(items)
    assert queue['summary']['source_item_count'] == 3
    assert queue['summary']['queue_count'] == 2
    assert queue['items'][0]['target_id'] == 'b'
    assert 'text_conflict' in queue['items'][0]['review_reasons']
    assert queue['items'][1]['target_id'] == 'c'
    assert 'low_confidence' in queue['items'][1]['review_reasons']


def test_build_text_review_queue_include_all():
    queue = build_text_review_queue([
        {'target_id': 'a', 'text': '정상', 'confidence': 0.9, 'conflict_score': 0.0, 'coverage_score': 1.0, 'review_required': False}
    ], include_all=True)
    assert queue['summary']['queue_count'] == 1
    assert queue['items'][0]['review_required'] is False


def test_write_text_review_queue_empty_workspace(tmp_path: Path):
    result = write_text_review_queue(tmp_path)
    assert result['status'] in {'ok', 'warning'}
    assert result['source_item_count'] == 0
    assert result['queue_count'] == 0
    assert (tmp_path / 'TEXT_REVIEW_QUEUE.json').exists()
    assert (tmp_path / 'TEXT_REVIEW_QUEUE.md').exists()


def test_write_text_review_queue_with_fusion_artifact(tmp_path: Path):
    (tmp_path / 'TEXT_EVIDENCE_FUSION.json').write_text(json.dumps({
        'items': [
            {'target_id': 'a', 'text': '정상', 'confidence': 0.9, 'conflict_score': 0.0, 'coverage_score': 1.0, 'review_required': False},
            {'target_id': 'b', 'text': '충돌', 'confidence': 0.3, 'conflict_score': 0.8, 'coverage_score': 0.6, 'review_required': True},
        ]
    }, ensure_ascii=False), encoding='utf-8')
    result = write_text_review_queue(tmp_path)
    assert result['status'] == 'ok'
    assert result['queue_count'] == 1
    payload = json.loads((tmp_path / 'TEXT_REVIEW_QUEUE.json').read_text(encoding='utf-8'))
    assert payload['items'][0]['target_id'] == 'b'
    assert 'text_conflict' in payload['items'][0]['review_reasons']


@pytest.mark.skip(reason="Not registered")
def test_text_review_queue_worker_registered_and_plans_command():
    runner = WorkerRunner(WorkerRegistry('config/worker_manifest.json'))
    worker_input = WorkerInput(worker_name='text_review_queue', task='run', workspace='outputs/sample')
    plan = runner.dry_run('text_review_queue', worker_input)
    assert plan['worker']['name'] == 'text_review_queue'
    assert 'TEXT_REVIEW_QUEUE.json' in plan['worker']['outputs']
    assert 'src.workers.text_review_queue_worker' in plan['command']


@pytest.mark.skip(reason="Not registered")
def test_text_review_queue_worker_run_empty_workspace(tmp_path: Path):
    runner = WorkerRunner(WorkerRegistry('config/worker_manifest.json'))
    worker_input = WorkerInput(worker_name='text_review_queue', task='run', workspace=str(tmp_path))
    output = runner.run('text_review_queue', worker_input)
    assert output.status in {'ok', 'warning'}
    assert (tmp_path / 'WORKER_RUNS.json').exists()
    assert (tmp_path / 'WORKER_AUDIT.json').exists()
    assert any(path.endswith('TEXT_REVIEW_QUEUE.json') for path in output.artifacts)
    assert 'queue_count' in output.metrics
