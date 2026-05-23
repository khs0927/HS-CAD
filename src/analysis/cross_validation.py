from __future__ import annotations

from typing import Any

from src.integrations.fusion_matrix import OpenSourceFusionMatrix


class CrossValidationScorer:
    def __init__(self, matrix: OpenSourceFusionMatrix | None = None):
        self.matrix = matrix or OpenSourceFusionMatrix()

    def score(self, target_type: str, target_id: str, observed_signals: dict[str, dict[str, Any]]) -> dict[str, Any]:
        target = self.matrix.target(target_type)
        if target is None:
            return {
                'target_type': target_type,
                'target_id': target_id,
                'agreement_score': 0.0,
                'confidence': 0.0,
                'warnings': [f'unknown target_type: {target_type}'],
                'signals': [],
            }
        implemented_weight = 0.0
        weighted_score = 0.0
        signals: list[dict[str, Any]] = []
        for configured in target.signals:
            payload = observed_signals.get(configured.id) or {}
            observed = configured.id in observed_signals
            score = float(payload.get('score', 1.0 if observed else 0.0))
            score = max(0.0, min(1.0, score))
            weighted = configured.weight * score if observed else 0.0
            signals.append({
                'id': configured.id,
                'backend': configured.backend,
                'status': configured.status,
                'weight': configured.weight,
                'observed': observed,
                'score': score,
                'weighted_score': round(weighted, 6),
                'evidence': list(payload.get('evidence') or []),
            })
            if configured.status == 'implemented':
                implemented_weight += configured.weight
                weighted_score += weighted
        agreement = weighted_score / implemented_weight if implemented_weight else 0.0
        confidence = min(0.98, agreement * 0.85 + min(implemented_weight, 1.0) * 0.15)
        return {
            'target_type': target_type,
            'target_id': target_id,
            'agreement_score': round(agreement, 6),
            'confidence': round(confidence, 6),
            'warnings': [] if implemented_weight else ['no implemented signals configured'],
            'signals': signals,
        }
