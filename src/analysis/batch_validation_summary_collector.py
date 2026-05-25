from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md

EXPECTED_ARTIFACTS = [
    'TEXT_ROLE_INFERENCE.json',
    'AREA_BOUNDARY_INFERENCE.json',
    'GEOMETRY_LOOP_BUILDER.json',
    'REAL_GEOMETRY_POLYGONIZER.json',
    'SPATIAL_INDEX_SERVICE.json',
    'LEADER_GRAPH.json',
    'DIMENSION_GRAPH.json',
    'TABLE_GRID_DETECTOR.json',
    'TABLE_CELL_EXTRACTOR.json',
    'TITLEBLOCK_CLASSIFIER.json',
    'TITLEBLOCK_KEY_VALUES.json',
    'DRAWING_SHEET_METADATA.json',
    'LAYER_PROFILE_SAMPLE.json',
    'DRAWING_SHEET_CLASSIFIER.json',
]


def collect_batch_validation_summary(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    artifacts = []
    warnings = []
    metrics: dict[str, Any] = {}
    for name in EXPECTED_ARTIFACTS:
        path = base / name
        payload = read_json(path)
        exists = path.exists()
        artifacts.append({
            'artifact': name,
            'exists': exists,
            'status': payload.get('status') or payload.get('backend') or ('missing' if not exists else 'present'),
            'summary': payload.get('summary') or {},
            'warning_count': len(payload.get('warnings') or []),
        })
        if not exists:
            warnings.append(f'missing artifact: {name}')
    worker_runs = read_json(base / 'WORKER_RUNS.json')
    worker_audit = read_json(base / 'WORKER_AUDIT.json')
    failures = _collect_failures(base)
    metrics.update(_extract_key_metrics(base))
    payload = {
        'backend': 'batch_validation_summary_collector',
        'schema_version': '0.1',
        'summary': {
            'expected_artifact_count': len(EXPECTED_ARTIFACTS),
            'existing_artifact_count': sum(1 for a in artifacts if a['exists']),
            'missing_artifact_count': sum(1 for a in artifacts if not a['exists']),
            'failure_count': len(failures),
            'worker_run_count': _maybe_len(worker_runs),
            'worker_audit_count': _maybe_len(worker_audit),
        },
        'key_metrics': metrics,
        'artifacts': artifacts,
        'failures_sample': failures[:50],
        'todo': [
            'Use this report as the first stop after every batch run.',
            'Add runtime extraction from worker_logs/*.jsonl.',
            'Add pass/fail thresholds after real corpus calibration.',
            'Emit machine-readable CI status after validation rules mature.',
        ],
        'warnings': warnings,
    }
    write_json_and_md(base, 'BATCH_VALIDATION_SUMMARY', payload, _markdown(payload))
    (base / 'VALIDATION_SUMMARY.md').write_text(_markdown(payload), encoding='utf-8')
    return payload


def _extract_key_metrics(base: Path) -> dict[str, Any]:
    files = {
        'TEXT_ROLE_INFERENCE.json': ['text_count'],
        'AREA_BOUNDARY_INFERENCE.json': ['candidate_count'],
        'REAL_GEOMETRY_POLYGONIZER.json': ['polygon_count', 'dangle_count', 'cut_edge_count', 'invalid_ring_count', 'fragment_quality_score'],
        'SPATIAL_INDEX_SERVICE.json': ['bin_count', 'text_area_candidate_count'],
        'LEADER_GRAPH.json': ['edge_count'],
        'DIMENSION_GRAPH.json': ['edge_count'],
        'TABLE_GRID_DETECTOR.json': ['candidate_count'],
        'TABLE_CELL_EXTRACTOR.json': ['cell_candidate_count'],
        'TITLEBLOCK_CLASSIFIER.json': ['candidate_count'],
        'TITLEBLOCK_KEY_VALUES.json': ['key_value_candidate_count'],
        'LAYER_PROFILE_SAMPLE.json': ['layer_count'],
    }
    out: dict[str, Any] = {}
    for filename, keys in files.items():
        payload = read_json(base / filename)
        summary = payload.get('summary') or {}
        for key in keys:
            out[f'{filename}:{key}'] = summary.get(key)
    return out


def _collect_failures(base: Path) -> list[dict[str, Any]]:
    failure_dir = base / 'failures'
    rows: list[dict[str, Any]] = []
    if not failure_dir.exists():
        return rows
    for path in sorted(failure_dir.glob('*.json')):
        payload = read_json(path)
        rows.append({
            'file': str(path),
            'error_type': payload.get('error_type') or payload.get('type'),
            'engine': payload.get('engine'),
            'message': str(payload.get('message') or payload.get('reason') or '')[:500],
        })
    return rows


def _maybe_len(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        for key in ['runs', 'items', 'events']:
            if isinstance(value.get(key), list):
                return len(value[key])
        return len(value)
    return 0


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Batch Validation Summary',
        '',
        f"- Expected artifacts: `{s.get('expected_artifact_count')}`",
        f"- Existing artifacts: `{s.get('existing_artifact_count')}`",
        f"- Missing artifacts: `{s.get('missing_artifact_count')}`",
        f"- Failure count: `{s.get('failure_count')}`",
        '',
        '## Artifacts',
        '',
        '| Artifact | Exists | Warnings |',
        '|---|---:|---:|',
    ]
    for row in payload.get('artifacts') or []:
        lines.append(f"| {row.get('artifact')} | {row.get('exists')} | {row.get('warning_count')} |")
    lines.append('')
    return '\n'.join(lines)
