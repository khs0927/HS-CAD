from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.workers.provenance import build_provenance


DEFAULT_WEIGHTS = {
    'ocr_confidence': 0.45,
    'vector_match': 0.30,
    'cad_match': 0.20,
    'coverage': 0.05,
    'conflict_penalty': 0.25,
}
BACKEND_TO_WEIGHT = {
    'ocr': 'ocr_confidence',
    'vector': 'vector_match',
    'cad': 'cad_match',
}


def write_text_weight_suggestions(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    calibration_path = base / 'TEXT_CALIBRATION_REPORT.json'
    calibration = _read_json(calibration_path)
    provenance = build_provenance(
        workspace=base,
        backend='text_weight_suggestions',
        algorithm='backend_reliability_weight_suggestions_v1',
        source_artifacts=[str(calibration_path)],
        worker_name='text_weight_suggestions',
    )
    suggestions = build_text_weight_suggestions(calibration, provenance=provenance)
    out_json = base / 'TEXT_FUSION_WEIGHT_SUGGESTIONS.json'
    out_md = base / 'TEXT_FUSION_WEIGHT_SUGGESTIONS.md'
    out_json.write_text(json.dumps(suggestions, ensure_ascii=False, indent=2), encoding='utf-8')
    out_md.write_text(_markdown(suggestions), encoding='utf-8')
    return {
        'backend': 'text_weight_suggestions',
        'status': 'ok' if suggestions['summary']['has_calibration_data'] else 'warning',
        'workspace': str(base),
        'has_calibration_data': suggestions['summary']['has_calibration_data'],
        'suggested_weights': suggestions['suggested_weights'],
        'artifacts': [str(out_json), str(out_md)],
        'warnings': suggestions.get('warnings') or [],
        'provenance': provenance,
    }


def build_text_weight_suggestions(calibration: dict[str, Any], *, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = calibration.get('summary') or {}
    applied_count = int(summary.get('applied_count') or 0)
    backend_stats = calibration.get('backend_signal_stats') or {}
    has_data = applied_count > 0 and bool(backend_stats)
    reliability: dict[str, dict[str, Any]] = {}
    raw_weights = {
        'ocr_confidence': DEFAULT_WEIGHTS['ocr_confidence'],
        'vector_match': DEFAULT_WEIGHTS['vector_match'],
        'cad_match': DEFAULT_WEIGHTS['cad_match'],
    }
    warnings: list[str] = []
    if not has_data:
        warnings.append('no calibration data found; using default weights')
    for backend, weight_key in BACKEND_TO_WEIGHT.items():
        stat = backend_stats.get(backend) or {}
        reliability_row = _backend_reliability(stat)
        reliability[backend] = reliability_row
        if has_data and reliability_row['count'] > 0:
            raw_weights[weight_key] = DEFAULT_WEIGHTS[weight_key] * reliability_row['weight_multiplier']
        elif has_data:
            warnings.append(f'no {backend} signal calibration rows; keeping default weight')
    normalized_core = _normalize_core_weights(raw_weights)
    suggested_weights = {
        'ocr_confidence': normalized_core['ocr_confidence'],
        'vector_match': normalized_core['vector_match'],
        'cad_match': normalized_core['cad_match'],
        'coverage': DEFAULT_WEIGHTS['coverage'],
        'conflict_penalty': _suggest_conflict_penalty(summary, calibration.get('confidence_buckets') or {}),
    }
    return {
        'backend': 'text_weight_suggestions',
        'source': 'TEXT_CALIBRATION_REPORT',
        'summary': {
            'has_calibration_data': has_data,
            'applied_count': applied_count,
            'accuracy_proxy': summary.get('accuracy_proxy', 0.0),
            'correction_rate': summary.get('correction_rate', 0.0),
            'rejection_rate': summary.get('rejection_rate', 0.0),
        },
        'default_weights': DEFAULT_WEIGHTS,
        'suggested_weights': suggested_weights,
        'backend_reliability': reliability,
        'policy_patch': {
            'text_evidence_fusion': {
                'weights': suggested_weights,
                'notes': 'Generated from human correction calibration. Treat as a proposal, not an automatic production override.',
            }
        },
        'warnings': warnings,
        'provenance': provenance or {},
    }


def _backend_reliability(stat: dict[str, Any]) -> dict[str, Any]:
    count = int(stat.get('count') or 0)
    accepted = int(stat.get('accepted') or 0)
    corrected = int(stat.get('corrected') or 0)
    rejected = int(stat.get('rejected') or 0)
    unclear = int(stat.get('unclear') or 0)
    avg_score = _safe_float(stat.get('avg_score'))
    if count <= 0:
        return {
            'count': 0,
            'accepted_ratio': 0.0,
            'error_like_ratio': 0.0,
            'unclear_ratio': 0.0,
            'avg_score': 0.0,
            'reliability_score': 0.5,
            'weight_multiplier': 1.0,
        }
    accepted_ratio = accepted / count
    error_like_ratio = (corrected + rejected) / count
    unclear_ratio = unclear / count
    reliability_score = max(0.05, min(1.0, (0.70 * accepted_ratio) + (0.20 * avg_score) - (0.35 * error_like_ratio) - (0.15 * unclear_ratio) + 0.20))
    weight_multiplier = max(0.50, min(1.35, 0.65 + reliability_score))
    return {
        'count': count,
        'accepted_ratio': round(accepted_ratio, 6),
        'error_like_ratio': round(error_like_ratio, 6),
        'unclear_ratio': round(unclear_ratio, 6),
        'avg_score': round(avg_score, 6),
        'reliability_score': round(reliability_score, 6),
        'weight_multiplier': round(weight_multiplier, 6),
    }


def _normalize_core_weights(raw: dict[str, float]) -> dict[str, float]:
    core_keys = ['ocr_confidence', 'vector_match', 'cad_match']
    target_sum = DEFAULT_WEIGHTS['ocr_confidence'] + DEFAULT_WEIGHTS['vector_match'] + DEFAULT_WEIGHTS['cad_match']
    raw_sum = sum(max(0.0, float(raw.get(key) or 0.0)) for key in core_keys)
    if raw_sum <= 0:
        return {key: DEFAULT_WEIGHTS[key] for key in core_keys}
    normalized = {
        key: round(max(0.0, float(raw.get(key) or 0.0)) / raw_sum * target_sum, 6)
        for key in core_keys
    }
    rounding_drift = round(target_sum - sum(normalized.values()), 6)
    normalized[core_keys[-1]] = round(normalized[core_keys[-1]] + rounding_drift, 6)
    return normalized


def _suggest_conflict_penalty(summary: dict[str, Any], confidence_buckets: dict[str, Any]) -> float:
    base = DEFAULT_WEIGHTS['conflict_penalty']
    correction_rate = _safe_float(summary.get('correction_rate'))
    rejection_rate = _safe_float(summary.get('rejection_rate'))
    high_bucket = confidence_buckets.get('0.75-1.00') or {}
    high_count = int(high_bucket.get('count') or 0)
    high_error = int(high_bucket.get('error_like_count') or 0)
    penalty = base
    if correction_rate + rejection_rate >= 0.30:
        penalty += 0.05
    if high_count and high_error / max(high_count, 1) >= 0.20:
        penalty += 0.05
    return round(max(0.10, min(0.45, penalty)), 6)


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _markdown(suggestions: dict[str, Any]) -> str:
    summary = suggestions.get('summary') or {}
    weights = suggestions.get('suggested_weights') or {}
    reliability = suggestions.get('backend_reliability') or {}
    lines = [
        '# Text Fusion Weight Suggestions',
        '',
        f"- Has calibration data: `{summary.get('has_calibration_data')}`",
        f"- Applied count: `{summary.get('applied_count')}`",
        f"- Accuracy proxy: `{summary.get('accuracy_proxy')}`",
        f"- Correction rate: `{summary.get('correction_rate')}`",
        f"- Rejection rate: `{summary.get('rejection_rate')}`",
        '',
        '## Suggested Weights',
        '',
        '| Weight | Value |',
        '|---|---:|',
    ]
    for key, value in weights.items():
        lines.append(f'| {key} | {value} |')
    lines.extend(['', '## Backend Reliability', '', '| Backend | Count | Accepted Ratio | Error-like Ratio | Avg Score | Multiplier |', '|---|---:|---:|---:|---:|---:|'])
    for backend, row in reliability.items():
        lines.append(f"| {backend} | {row.get('count')} | {row.get('accepted_ratio')} | {row.get('error_like_ratio')} | {row.get('avg_score')} | {row.get('weight_multiplier')} |")
    lines.extend(['', '## Warnings', ''])
    for warning in suggestions.get('warnings') or []:
        lines.append(f'- {warning}')
    if not suggestions.get('warnings'):
        lines.append('- None')
    lines.append('')
    return '\n'.join(lines)
