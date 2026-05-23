from __future__ import annotations

from src.integrations.fusion_matrix import OpenSourceFusionMatrix


def test_fusion_matrix_has_core_targets():
    summary = OpenSourceFusionMatrix('config/open_source_fusion_matrix.json').summary()
    target_types = {target['target_type'] for target in summary['targets']}
    assert 'area_element' in target_types
    assert 'text_role' in target_types
    assert 'layer_semantic' in target_types
    assert 'graph_relationship' in target_types


def test_fusion_matrix_has_expected_backends():
    summary = OpenSourceFusionMatrix('config/open_source_fusion_matrix.json').summary()
    assert 'shapely' in summary['backend_counts']
    assert 'opencv' in summary['backend_counts']
    assert 'paddleocr' in summary['backend_counts']


def test_fusion_target_weights_are_available():
    target = OpenSourceFusionMatrix('config/open_source_fusion_matrix.json').target('area_element')
    assert target is not None
    assert target.implemented_weight() > 0
    assert target.planned_weight() > 0
