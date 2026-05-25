from __future__ import annotations

import json
from pathlib import Path

from src.analysis.layer_semantics import LayerSemanticInferer


def _by_layer(result: dict):
    return {item['layer']: item for item in result['layers']}


def test_layer_semantics_infers_by_layer_name_and_entities():
    record = {
        'file_id': 'sample',
        'entities': [
            {'entity_type': 'LINE', 'layer': 'A-WALL', 'color': 1, 'linetype': 'CONTINUOUS'},
            {'entity_type': 'POLYLINE', 'layer': 'A-WALL', 'color': 1, 'linetype': 'CONTINUOUS'},
            {'entity_type': 'DIMENSION', 'layer': 'DIM', 'color': 2, 'linetype': 'CONTINUOUS'},
            {'entity_type': 'TEXT', 'layer': 'TEXT', 'text': '사무실', 'color': 7, 'linetype': 'CONTINUOUS'},
            {'entity_type': 'HATCH', 'layer': 'A-HATCH', 'color': 8, 'linetype': 'CONTINUOUS'},
        ],
    }
    result = LayerSemanticInferer().infer_record(record)
    layers = _by_layer(result)
    assert layers['A-WALL']['predicted_semantic'] == 'wall'
    assert layers['DIM']['predicted_semantic'] == 'dimension'
    assert layers['TEXT']['predicted_semantic'] == 'text_note'
    assert layers['A-HATCH']['predicted_semantic'] == 'hatch_area'


def test_layer_semantics_uses_block_and_text_signals():
    record = {
        'file_id': 'sample',
        'entities': [
            {'entity_type': 'INSERT', 'layer': 'SYM', 'name': 'DOOR_900'},
            {'entity_type': 'TEXT', 'layer': 'ANNO', 'text': '방화문'},
        ],
    }
    result = LayerSemanticInferer().infer_record(record)
    layers = _by_layer(result)
    assert layers['SYM']['predicted_semantic'] == 'block_symbol'
    assert layers['ANNO']['predicted_semantic'] in {'door', 'text_note'}


def test_layer_semantics_json_dir_merges_layers(tmp_path: Path):
    json_dir = tmp_path / 'fileized' / 'json'
    json_dir.mkdir(parents=True)
    first = {'file_id': 'a', 'entities': [{'entity_type': 'LINE', 'layer': 'WAL1'}, {'entity_type': 'POLYLINE', 'layer': 'WAL1'}]}
    second = {'file_id': 'b', 'entities': [{'entity_type': 'LINE', 'layer': 'WAL1'}, {'entity_type': 'TEXT', 'layer': 'NOTE', 'text': '주기'}]}
    (json_dir / 'a.json').write_text(json.dumps(first, ensure_ascii=False), encoding='utf-8')
    (json_dir / 'b.json').write_text(json.dumps(second, ensure_ascii=False), encoding='utf-8')
    result = LayerSemanticInferer().infer_json_dir(json_dir)
    layers = _by_layer(result)
    assert result['file_count'] == 2
    assert 'WAL1' in layers
    assert layers['WAL1']['counts']['entity_types']['LINE'] == 2
    assert layers['WAL1']['predicted_semantic'] == 'wall'
