from __future__ import annotations

import json
from pathlib import Path

from src.ocr.text_calibration_report import build_text_calibration_report, write_text_calibration_report
from src.workers.contracts import WorkerInput
from src.workers.runner import WorkerRunner


def _applied_rows():
    return [
        {'target_id': 'ocr:1', 'before_text': '사무실', 'final_text': '사무실', 'correction_status': 'accepted'},
        {'target_id': 'ocr:2', 'before_text': '사무실', 'final_text': '사무소', 'correction_status': 'corrected'},
        {'target_id': 'ocr:3', 'before_text': 'xx', 'final_text': 'xx', 'correction_status': 'rejected'},
        {'target_id': 'ocr:4', 'before_text': '??', 'final_text': '??', 'correction_status': 'unclear'},
    ]


def _corrected_items():
    return [
        {'target_id': 'ocr:1', 'confidence': 0.9, 'signals': {'ocr_confidence': 0.9, 'vector_match_score': 0.95, 'cad_match_score': 0.9}},
        {'target_id': 'ocr:2', 'confidence': 0.8, 'signals': {'ocr_confidence': 0.8, 'vector_match_score': 0.7, 'cad_match_score': 0.6}},
        {'target_id': 'ocr:3', 'confidence': 0.85, 'signals': {'ocr_confidence': 0.85, 'vector_match_score': 0.8, 'cad_match_score': 0.0}},
        {'target_id': 'ocr:4', 'confidence': 0.2, 'signals': {'ocr_confidence': 0.2, 'vector_match_score': 0.0, 'cad_match_score': 0.0}},
    ]


def test_build_text_calibration_report_counts_status_and_buckets():
    report = build_text_calibration_report(_applied_rows(), _corrected_items())
    summary = report['summary']
    assert summary['applied_count'] == 4
    assert summary['status_counts']['accepted'] == 1
    assert summary['status_counts']['corrected'] == 1
    assert summary['status_counts']['rejected'] == 1
    assert summary['status_counts']['unclear'] == 1
    assert summary['accuracy_proxy'] == 0.25
    assert summary['correction_rate'] == 0.25
    assert report['confidence_buckets']['0.75-1.00']['count'] == 3
    assert report['confidence_buckets']['0.00-0.25']['count'] == 1
    assert report['samples_by_status']['corrected'][0]['target_id'] == 'ocr:2'
    assert report['recommendations']


def test_write_text_calibration_report_empty_workspace(tmp_path: Path):
    result = write_text_calibration_report(tmp_path)
    assert result['status'] in {'ok', 'warning'}
    assert result['applied_count'] == 0
    assert (tmp_path / 'TEXT_CALIBRATION_REPORT.json').exists()
    assert (tmp_path / 'TEXT_CALIBRATION_REPORT.md').exists()


def test_write_text_calibration_report_with_artifacts(tmp_path: Path):
    (tmp_path / 'TEXT_CORRECTIONS_APPLIED.json').write_text(json.dumps({'applied': _applied_rows()}, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'TEXT_EVIDENCE_FUSION_CORRECTED.json').write_text(json.dumps({'items': _corrected_items()}, ensure_ascii=False), encoding='utf-8')
    result = write_text_calibration_report(tmp_path)
    assert result['status'] == 'ok'
    assert result['applied_count'] == 4
    payload = json.loads((tmp_path / 'TEXT_CALIBRATION_REPORT.json').read_text(encoding='utf-8'))
    assert payload['summary']['rejection_rate'] == 0.25
    assert 'backend_signal_stats' in payload


def test_text_calibration_report_worker_registered_and_plans_command():
    runner = WorkerRunner(record_runs=False)
    worker_input = WorkerInput(worker_name='text_calibration_report', task='run', workspace='outputs/sample')
    plan = runner.dry_run('text_calibration_report', worker_input)
    assert plan['worker']['name'] == 'text_calibration_report'
    assert 'TEXT_CALIBRATION_REPORT.json' in plan['worker']['outputs']
    assert 'src.workers.text_calibration_report_worker' in plan['command']


def test_text_calibration_report_worker_run_empty_workspace(tmp_path: Path):
    runner = WorkerRunner(record_runs=True)
    worker_input = WorkerInput(worker_name='text_calibration_report', task='run', workspace=str(tmp_path))
    output = runner.run('text_calibration_report', worker_input)
    assert output.status in {'ok', 'warning'}
    assert (tmp_path / 'WORKER_RUNS.json').exists()
    assert (tmp_path / 'WORKER_AUDIT.json').exists()
    assert any(path.endswith('TEXT_CALIBRATION_REPORT.json') for path in output.artifacts)
    assert 'accuracy_proxy' in output.metrics
