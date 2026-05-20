from src.semantics.layer_taxonomy import classify_layer, get_layer_rule, layer_rules_as_rows
from src.semantics.object_classifier import classify_object, classify_objects, summarize_semantics


def test_user_layer_taxonomy_core_layers():
    assert classify_layer('COL')['structural'] is True
    assert classify_layer('WAL1')['role'] == 'lightweight_wall'
    assert classify_layer('WAL2')['material'] == 'masonry'
    assert classify_layer('ELE1')['expected_color_index'] == 251
    assert classify_layer('ETC4')['expected_color_index'] == 254
    assert classify_layer('DEFPOINTS')['visible'] is False
    assert get_layer_rule('WAL7').category == 'wall'
    assert len(layer_rules_as_rows()) >= 30


def test_classify_object_by_layer_and_geometry():
    objects = [
        {'handle': '1', 'layer': 'COL', 'entity_type': 'LINE', 'start': [0, 0, 0], 'end': [0, 3000, 0]},
        {'handle': '2', 'layer': 'WAL2', 'entity_type': 'LWPOLYLINE', 'points': [[0,0,0],[1,0,0],[1,1,0]], 'closed': False},
        {'handle': '3', 'layer': 'UNKNOWN', 'entity_type': 'INSERT', 'name': 'D900', 'insert': [0,0,0]},
        {'handle': '4', 'layer': 'BOUND', 'entity_type': 'LWPOLYLINE', 'points': [[0,0,0],[1,0,0],[1,1,0],[0,0,0]], 'closed': True},
    ]
    rows = classify_objects(objects)
    assert rows[0]['category'] == 'structure'
    assert rows[0]['analysis_order'][0] == 'layer'
    assert rows[0]['evidence'][0]['stage'] == 'layer'
    assert rows[1]['role'] == 'masonry_wall'
    assert rows[2]['role'] == 'door_block_by_name'
    assert rows[3]['category'] == 'boundary'
    summary = summarize_semantics(rows)
    assert summary['by_category']['structure'] == 1
    assert summary['object_count'] == 4


def test_color_mismatch_lowers_confidence():
    row = classify_object({'handle': 'E1', 'layer': 'ELE1', 'entity_type': 'LINE', 'color': 7})
    assert row['layer_semantic']['color_matches_rule'] is False
    assert 'color_mismatch' in row['reason']
