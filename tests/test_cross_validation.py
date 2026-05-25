from __future__ import annotations

from src.analysis.cross_validation import CrossValidationScorer


def test_cross_validation_scores_observed_area_signals():
    result = CrossValidationScorer().score(
        'area_element',
        'area:sample:P1',
        {
            'closed_polyline_area': {'score': 1.0, 'evidence': ['closed polyline exists']},
            'hatch_boundary_area': {'score': 0.9, 'evidence': ['hatch boundary agrees']},
            'room_label_inside': {'score': 0.8, 'evidence': ['label inside']},
        },
    )
    assert result['target_type'] == 'area_element'
    assert result['agreement_score'] > 0
    assert result['confidence'] > 0
    signals = {signal['id']: signal for signal in result['signals']}
    assert signals['closed_polyline_area']['observed'] is True
    assert signals['shapely_polygonize_area']['observed'] is False


def test_cross_validation_unknown_target_returns_warning():
    result = CrossValidationScorer().score('missing_target', 'x', {})
    assert result['agreement_score'] == 0.0
    assert result['confidence'] == 0.0
    assert result['warnings']
