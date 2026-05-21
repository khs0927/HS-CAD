from src.semantics.layer_taxonomy import canonical_layer_name, classify_layer, get_layer_rule, layer_rules_as_rows
from src.semantics.object_classifier import classify_object, classify_objects, summarize_semantics


def test_user_layer_taxonomy_core_layers():
    assert classify_layer('COL')['structural'] is True
    assert classify_layer('WAL1')['role'] == 'lightweight_wall'
    assert classify_layer('WAL2')['material'] == 'masonry'
    assert classify_layer('ELE1')['expected_color_index'] == 251
    assert classify_layer('ETC4')['expected_color_index'] == 254
    assert classify_layer('HAT')['category'] == 'hatch'
    assert classify_layer('HID')['role'] == 'hidden_dashed_line'
    assert classify_layer('HID')['linetype'] == 'HID'
    assert classify_layer('INS')['linetype'] == 'BATTING'
    assert classify_layer('SYM_TEXT')['role'] == 'symbol_line'
    assert classify_layer('ZONE')['role'] == 'zone_boundary'
    assert classify_layer('SEC1')['category'] == 'section'
    assert classify_layer('FIN2')['category'] == 'finish'
    assert classify_layer('TXT1')['role'] == 'extra_text'
    assert classify_layer('MEP')['category'] == 'mep'
    assert classify_layer('NOTE')['role'] == 'note'
    assert classify_layer('CEN3')['category'] == 'grid_centerline'
    assert classify_layer('DEFPOINTS')['visible'] is False
    assert get_layer_rule('WAL7').category == 'wall'
    assert get_layer_rule('HAT-1').category == 'hatch'
    assert get_layer_rule('HID2').category == 'hidden_line'
    assert len(layer_rules_as_rows()) >= 30


def test_canonical_layer_name_user_mappings():
    assert canonical_layer_name('\uad6c\uc5ed\uacc4') == 'ZONE'
    assert canonical_layer_name('\uc870\uc801') == 'WAL2'
    assert canonical_layer_name('\ubb38\uc790-\uae30\ud0c0') == 'TXT1'
    assert canonical_layer_name('\ubd80\ud638\ub3c4') == 'SYM'
    assert canonical_layer_name('\uc124\ube44') == 'MEP'
    assert canonical_layer_name('\uc810\uc120') == 'HID'
    assert canonical_layer_name('\ud574\uce58\uc120') == 'HAT'
    assert canonical_layer_name('DOORELE') == 'DOOR_ELE'
    assert canonical_layer_name('0') == 'ETC'
    assert canonical_layer_name('@text') == 'TXT'
    assert canonical_layer_name('@tree') == 'ETC'
    assert canonical_layer_name('A-\ub808\ubca8') == 'NOTE'
    assert canonical_layer_name('06-A31- 001~ sample$0$A-TOLDOOR') == 'DOOR'
    assert canonical_layer_name('06-A31- 001~ sample$0$FUR') == 'FUR'
    assert canonical_layer_name('INSUL') == 'INS'
    assert canonical_layer_name('FORM') == 'A-FORM'
    assert canonical_layer_name('PAPER') == 'A-FORM'
    assert canonical_layer_name('TITLE') == 'TIT'
    assert canonical_layer_name('WALL3') == 'WAL3'


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
