from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_TEXT_POLICY = {
    'weights': {
        'ocr_confidence': 0.45,
        'vector_match': 0.30,
        'cad_match': 0.20,
        'coverage': 0.05,
        'conflict_penalty': 0.25,
    },
    'review_threshold': 0.55,
    'conflict_threshold': 0.35,
}


def load_text_fusion_policy(workspace: str | Path, *, allow_suggestions: bool = True) -> dict[str, Any]:
    """Load text evidence fusion policy.

    Priority:
    1. TEXT_FUSION_POLICY.json
    2. TEXT_FUSION_WEIGHT_SUGGESTIONS.json policy_patch, when allow_suggestions=True
    3. DEFAULT_TEXT_POLICY

    This module intentionally does not mutate source artifacts. It returns a policy payload that callers may apply.
    """
    base = Path(workspace)
    explicit = _read_json(base / 'TEXT_FUSION_POLICY.json')
    if explicit:
        return _normalized_policy(explicit, source='TEXT_FUSION_POLICY.json')

    if allow_suggestions:
        suggestions = _read_json(base / 'TEXT_FUSION_WEIGHT_SUGGESTIONS.json')
        patch = (((suggestions.get('policy_patch') or {}).get('text_evidence_fusion') or {}).get('weights') or {})
        if patch:
            return _normalized_policy({'weights': patch}, source='TEXT_FUSION_WEIGHT_SUGGESTIONS.json')

    return _normalized_policy(DEFAULT_TEXT_POLICY, source='default')


def _normalized_policy(payload: dict[str, Any], *, source: str) -> dict[str, Any]:
    weights = dict(DEFAULT_TEXT_POLICY['weights'])
    weights.update({k: _safe_float(v, weights.get(k, 0.0)) for k, v in (payload.get('weights') or {}).items()})
    return {
        'source': source,
        'weights': weights,
        'review_threshold': _safe_float(payload.get('review_threshold'), DEFAULT_TEXT_POLICY['review_threshold']),
        'conflict_threshold': _safe_float(payload.get('conflict_threshold'), DEFAULT_TEXT_POLICY['conflict_threshold']),
    }


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
