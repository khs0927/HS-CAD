from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.workers.provenance import build_provenance


STATUS_VALUES = ['accepted', 'corrected', 'rejected', 'unclear']
CONFIDENCE_BUCKETS = [
    ('0.00-0.25', 0.0, 0.25),
    ('0.25-0.50', 0.25, 0.50),
    ('0.50-0.75', 0.50, 0.75),
    ('0.75-1.00', 0.75, 1.01),
]


def write_text_calibration_report(workspace: str | Path, *, max_samples_per_status: int = 5) -> dict[str, Any]:
    base = Path(workspace)
    applied_path = base / 'TEXT_CORRECTIONS_APPLIED.json'
    corrected_path = base / 'TEXT_EVIDENCE_FUSION_CORRECTED.json'
    applied_payload = _read_json(applied_path)
    corrected_payload = _read_json(corrected_path)
    provenance = build_provenance(
        workspace=base,
        backend='text_calibration_report',
        algorithm='human_correction_calibration_summary_v1',
        source_artifacts=[str(applied_path), str(corrected_path)],
        worker_name='text_calibration_report',
    )
    report_payload = build_text_calibration_report(
        applied_payload.get('applied') or [],
        corrected_payload.get('items') or [],
        max_samples_per_status=max_samples_per_status,
        provenance=provenance,
    )
    out_json = base / 'TEXT_CALIBRATION_REPORT.json'
    out_md = base / 'TEXT_CALIBRATION_REPORT.md'
    out_json.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding='utf-8')
    out_md.write_text(_markdown(report_payload), encoding='utf-8')
    summary = report_payload.get('summary') or {}
    return {
        'backend': 'text_calibration_report',
        'status': 'ok' if summary.get('applied_count') else 'warning',
        'workspace': str(base),
        'applied_count': summary.get('applied_count'),
        'accuracy_proxy': summary.get('accuracy_proxy'),
        'correction_rate': summary.get('correction_rate'),
        'rejection_rate': summary.get('rejection_rate'),
        'artifacts': [str(out_json), str(out_md)],
        'warnings': report_payload.get('warnings') or [],
        'provenance': provenance,
    }


def build_text_calibration_report(
    applied_rows: list[dict[str, Any]],
    corrected_items: list[dict[str, Any]],
    *,
    max_samples_per_status: int = 5,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_counts = {status: 0 for status in STATUS_VALUES}
    samples_by_status = {status: [] for status in STATUS_VALUES}
    corrected_by_target = {str(item.get('target_id')): item for item in corrected_items if item.get('target_id') is not None}
    confidence_buckets = _empty_confidence_buckets()
    backend_signal_stats = _empty_backend_signal_stats()

    for row in applied_rows:
        status = str(row.get('correction_status') or '').strip().lower()
        if status not in status_counts:
            continue
        status_counts[status] += 1
        target_id = str(row.get('target_id') or '')
        item = corrected_by_target.get(target_id, {})
        confidence = _safe_float(item.get('confidence'))
        _add_to_confidence_bucket(confidence_buckets, confidence, status)
        _add_backend_signal_stats(backend_signal_stats, item, status)
        if len(samples_by_status[status]) < max_samples_per_status:
            samples_by_status[status].append({
                'target_id': target_id,
                'before_text': row.get('before_text'),
                'final_text': row.get('final_text'),
                'confidence': confidence,
                'status': status,
                'reviewer_note': row.get('reviewer_note') or '',
                'signals': item.get('signals') or {},
            })
    applied_count = sum(status_counts.values())
    accepted_count = status_counts.get('accepted', 0)
    corrected_count = status_counts.get('corrected', 0)
    rejected_count = status_counts.get('rejected', 0)
    unclear_count = status_counts.get('unclear', 0)
    accuracy_proxy = round(accepted_count / applied_count, 6) if applied_count else 0.0
    correction_rate = round(corrected_count / applied_count, 6) if applied_count else 0.0
    rejection_rate = round(rejected_count / applied_count, 6) if applied_count else 0.0
    unclear_rate = round(unclear_count / applied_count, 6) if applied_count else 0.0
    recommendations = _recommendations(status_counts, confidence_buckets, backend_signal_stats)
    warnings = [] if applied_count else ['no applied corrections found']
    return {
        'backend': 'text_calibration_report',
        'source': 'TEXT_CORRECTIONS_APPLIED+TEXT_EVIDENCE_FUSION_CORRECTED',
        'summary': {
            'applied_count': applied_count,
            'status_counts': status_counts,
            'accuracy_proxy': accuracy_proxy,
            'correction_rate': correction_rate,
            'rejection_rate': rejection_rate,
            'unclear_rate': unclear_rate,
        },
        'confidence_buckets': confidence_buckets,
        'backend_signal_stats': backend_signal_stats,
        'samples_by_status': samples_by_status,
        'recommendations': recommendations,
        'warnings': warnings,
        'provenance': provenance or {},
    }


def _empty_confidence_buckets() -> dict[str, dict[str, Any]]:
    return {
        label: {
            'count': 0,
            'accepted': 0,
            'corrected': 0,
            'rejected': 0,
            'unclear': 0,
            'error_like_count': 0,
        }
        for label, _lo, _hi in CONFIDENCE_BUCKETS
    }


def _add_to_confidence_bucket(buckets: dict[str, dict[str, Any]], confidence: float, status: str) -> None:
    for label, lo, hi in CONFIDENCE_BUCKETS:
        if lo <= confidence < hi:
            row = buckets[label]
            row['count'] += 1
            row[status] = row.get(status, 0) + 1
            if status in {'corrected', 'rejected'}:
                row['error_like_count'] += 1
            return


def _empty_backend_signal_stats() -> dict[str, dict[str, Any]]:
    return {
        'ocr': {'count': 0, 'score_sum': 0.0, 'accepted': 0, 'corrected': 0, 'rejected': 0, 'unclear': 0},
        'vector': {'count': 0, 'score_sum': 0.0, 'accepted': 0, 'corrected': 0, 'rejected': 0, 'unclear': 0},
        'cad': {'count': 0, 'score_sum': 0.0, 'accepted': 0, 'corrected': 0, 'rejected': 0, 'unclear': 0},
    }


def _add_backend_signal_stats(stats: dict[str, dict[str, Any]], item: dict[str, Any], status: str) -> None:
    signals = item.get('signals') or {}
    signal_map = {
        'ocr': signals.get('ocr_confidence'),
        'vector': signals.get('vector_match_score'),
        'cad': signals.get('cad_match_score'),
    }
    for name, value in signal_map.items():
        score = _safe_float(value)
        if score <= 0:
            continue
        row = stats[name]
        row['count'] += 1
        row['score_sum'] += score
        row[status] = row.get(status, 0) + 1


def _finalize_backend_signal_stats(stats: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    finalized: dict[str, dict[str, Any]] = {}
    for name, row in stats.items():
        count = int(row.get('count') or 0)
        score_sum = float(row.get('score_sum') or 0.0)
        new_row = dict(row)
        new_row.pop('score_sum', None)
        new_row['avg_score'] = round(score_sum / count, 6) if count else 0.0
        finalized[name] = new_row
    return finalized


def _recommendations(status_counts: dict[str, int], confidence_buckets: dict[str, dict[str, Any]], backend_signal_stats: dict[str, dict[str, Any]]) -> list[str]:
    recs: list[str] = []
    total = sum(status_counts.values())
    if not total:
        return ['Collect human corrections before calibration.']
    corrected_or_rejected = status_counts.get('corrected', 0) + status_counts.get('rejected', 0)
    if corrected_or_rejected / total >= 0.3:
        recs.append('High correction/rejection rate: review OCR/vector/CAD text matching weights before increasing automation.')
    high_bucket = confidence_buckets.get('0.75-1.00') or {}
    if high_bucket.get('count', 0) and high_bucket.get('error_like_count', 0) / max(high_bucket.get('count', 1), 1) >= 0.2:
        recs.append('High-confidence items still contain errors: lower trust thresholds or increase conflict penalty.')
    low_bucket = confidence_buckets.get('0.00-0.25') or {}
    if low_bucket.get('count', 0):
        recs.append('Low-confidence bucket has review items: inspect scan quality, OCR language settings, and PDF coordinate alignment.')
    finalized = _finalize_backend_signal_stats(backend_signal_stats)
    for backend, row in finalized.items():
        if row.get('count', 0) and row.get('rejected', 0) / max(row.get('count', 1), 1) >= 0.25:
            recs.append(f'{backend} signal has elevated rejected ratio: consider lowering its fusion weight or adding stricter filters.')
    if not recs:
        recs.append('Correction distribution looks stable for the current sample. Continue collecting corrections across more projects.')
    return recs


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


def _markdown(report: dict[str, Any]) -> str:
    summary = report.get('summary') or {}
    status_counts = summary.get('status_counts') or {}
    lines = [
        '# Text Calibration Report',
        '',
        f"- Applied count: `{summary.get('applied_count')}`",
        f"- Accuracy proxy: `{summary.get('accuracy_proxy')}`",
        f"- Correction rate: `{summary.get('correction_rate')}`",
        f"- Rejection rate: `{summary.get('rejection_rate')}`",
        f"- Unclear rate: `{summary.get('unclear_rate')}`",
        '',
        '## Status Counts',
        '',
        '| Status | Count |',
        '|---|---:|',
    ]
    for status in STATUS_VALUES:
        lines.append(f"| {status} | {status_counts.get(status, 0)} |")
    lines.extend(['', '## Confidence Buckets', '', '| Bucket | Count | Accepted | Corrected | Rejected | Unclear | Error-like |', '|---|---:|---:|---:|---:|---:|---:|'])
    for label, row in (report.get('confidence_buckets') or {}).items():
        lines.append(f"| {label} | {row.get('count')} | {row.get('accepted')} | {row.get('corrected')} | {row.get('rejected')} | {row.get('unclear')} | {row.get('error_like_count')} |")
    lines.extend(['', '## Recommendations', ''])
    for rec in report.get('recommendations') or []:
        lines.append(f'- {rec}')
    lines.append('')
    return '\n'.join(lines)
