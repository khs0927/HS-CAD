from __future__ import annotations

import json
from pathlib import Path

from src.ocr.text_weight_suggestions import build_text_weight_suggestions, write_text_weight_suggestions
from src.workers.contracts import WorkerInput
from src.workers.text_weight_suggestions_worker import run_worker


def _calibration_payload():
    return {
        'summary': {
            'applied_count': 10,
            'accuracy_proxy': 0.6,
            'correction_rate': 0.2,
            'rejection_rate': 0.1,
        },
        'confidence_buckets': {
            '0.75-1.00': {'count': 5, 'error_like_count': 2},
            '0.00-0.25': {'count': 1, 'error_like_count': 1},
        },
        'backend_signal_stats': {
            'ocr': {'count': 10, 'accepted': 7, 'corrected': 2, 'rejected': 1, 'unclear': 0, 'avg_score': 0.85},
            'vector': {'count': 8, 'accepted': 6, 'corrected': 1, 'rejected': 0, 'unclear': 1, 'avg_score': 0.75},
            'cad': {'count': 5, 'accepted': 1, 'corrected': 2, 'rejected': 2, 'unclear': 0, 'avg_score': 0.4},
        },
    }


def test_build_text_weight_suggestions_uses_backend_reliability():
    payload = build_text_weight_suggestions(_calibration_payload())
    assert payload['summary']['has_calibration_data'] is True
    weights = payload['suggested_weights']
    assert set(weights) == {'ocr_confidence', 'vector_match', 'cad_match', 'coverage', 'conflict_penalty'}
    assert abs((weights['ocr_confidence'] + weights['vector_match'] + weights['cad_match']) - 0.95) < 0.00001
    assert weights['cad_match'] < 0.20
    assert weights['conflict_penalty'] >= 0.25
    assert payload['backend_reliability']['ocr']['count'] == 10
    assert payload['policy_patch']['text_evidence_fusion']['weights'] == weights


def test_build_text_weight_suggestions_no_data_uses_defaults():
    payload = build_text_weight_suggestions({})
    assert payload['summary']['has_calibration_data'] is False
    assert payload['suggested_weights']['ocr_confidence'] == 0.45
    assert payload['suggested_weights']['vector_match'] == 0.30
    assert payload['suggested_weights']['cad_match'] == 0.20
    assert payload['warnings']


def test_write_text_weight_suggestions_empty_workspace(tmp_path: Path):
    result = write_text_weight_suggestions(tmp_path)
    assert result['status'] in {'ok', 'warning'}
    assert result['has_calibration_data'] is False
    assert (tmp_path / 'TEXT_FUSION_WEIGHT_SUGGESTIONS.json').exists()
    assert (tmp_path / 'TEXT_FUSION_WEIGHT_SUGGESTIONS.md').exists()


def test_write_text_weight_suggestions_with_calibration(tmp_path: Path):
    (tmp_path / 'TEXT_CALIBRATION_REPORT.json').write_text(json.dumps(_calibration_payload(), ensure_ascii=False), encoding='utf-8')
    result = write_text_weight_suggestions(tmp_path)
    assert result['status'] == 'ok'
    payload = json.loads((tmp_path / 'TEXT_FUSION_WEIGHT_SUGGESTIONS.json').read_text(encoding='utf-8'))
    assert payload['summary']['has_calibration_data'] is True
    assert payload['suggested_weights']['cad_match'] < 0.20


def test_text_weight_suggestions_worker_run_empty_workspace(tmp_path: Path):
    worker_input = WorkerInput(worker_name='text_weight_suggestions', task='run', workspace=str(tmp_path))
    output = run_worker(worker_input)
    assert output.status in {'ok', 'warning'}
    assert any(path.endswith('TEXT_FUSION_WEIGHT_SUGGESTIONS.json') for path in output.artifacts)
    assert 'suggested_weights' in output.metrics
