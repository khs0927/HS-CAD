from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_TEXT_POLICY = {
    'version': 'weighted_text_evidence_score_v1',
    'weights': {
        'ocr_confidence': 0.45,
        'vector_match': 0.30,
        'cad_match': 0.20,
        'coverage': 0.05,
        'conflict_penalty': 0.25,
    },
}


def load_text_fusion_policy(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    explicit = _read_json(base / 'TEXT_FUSION_POLICY.json')
    if explicit:
        return _normalize_policy(explicit, source='TEXT_FUSION_POLICY.json')

    suggestions = _read_json(base / 'TEXT_FUSION_WEIGHT_SUGGESTIONS.json')
    patch = (((suggestions.get('policy_patch') or {}).get('text_evidence_fusion') or {}).get('weights') or {})
    if patch:
        return _normalize_policy({'weights': patch}, source='TEXT_FUSION_WEIGHT_SUGGESTIONS.json')

    return _normalize_policy(DEFAULT_TEXT_POLICY, source='DEFAULT_TEXT_POLICY')


def _normalize_policy(policy: dict[str, Any], *, source: str) -> dict[str, Any]:
    default_weights = DEFAULT_TEXT_POLICY['weights']
    raw_weights = policy.get('weights') or {}
    weights = {
        key: _safe_float(raw_weights.get(key), default)
        for key, default in default_weights.items()
    }
    return {
        'version': str(policy.get('version') or DEFAULT_TEXT_POLICY['version']),
        'source': source,
        'weights': weights,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)
