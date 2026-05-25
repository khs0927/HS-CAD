from __future__ import annotations

import json
from pathlib import Path

from src.spatial.text_roles import TextRoleInferer


def _roles_by_text(result: dict):
    return {role['text']: role for role in result['roles']}


def test_text_role_inferer_detects_room_name_inside_boundary():
    record = {
        'file_id': 'room',
        'entities': [
            {'handle': 'P1', 'entity_type': 'POLYLINE', 'layer': 'ROOM', 'closed': True, 'points': [[0, 0], [100, 0], [100, 100], [0, 100]]},
            {'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TEXT', 'text': '사무실', 'insert': [50, 50]},
        ],
    }
    result = TextRoleInferer().infer_record(record)
    role = _roles_by_text(result)['사무실']
    assert role['role'] == 'room_or_space_name'
    assert role['confidence'] >= 0.68


def test_text_role_inferer_detects_table_text_from_grid_lines():
    entities = []
    for y in [0, 10, 20, 30]:
        entities.append({'handle': f'H{y}', 'entity_type': 'LINE', 'layer': 'TABLE', 'start': [0, y], 'end': [100, y]})
    for x in [0, 50, 100]:
        entities.append({'handle': f'V{x}', 'entity_type': 'LINE', 'layer': 'TABLE', 'start': [x, 0], 'end': [x, 30]})
    entities.append({'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TEXT', 'text': '품명', 'insert': [10, 5]})
    result = TextRoleInferer().infer_record({'file_id': 'table', 'entities': entities})
    role = _roles_by_text(result)['품명']
    assert role['role'] == 'table_cell_text'
    assert any('grid' in item or 'table' in item for item in role['evidence'])


def test_text_role_inferer_detects_dimension_or_spec_note():
    record = {'file_id': 'spec', 'entities': [{'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TEXT', 'text': 'T180 그라스울 판넬', 'insert': [0, 0]}]}
    result = TextRoleInferer().infer_record(record)
    role = _roles_by_text(result)['T180 그라스울 판넬']
    assert role['role'] == 'dimension_or_spec_note'


def test_text_role_inferer_json_dir(tmp_path: Path):
    json_dir = tmp_path / 'fileized' / 'json'
    json_dir.mkdir(parents=True)
    record = {'file_id': 'sample', 'entities': [{'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TITLE', 'text': '도면명', 'insert': [90, 5]}]}
    (json_dir / 'sample.json').write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    result = TextRoleInferer().infer_json_dir(json_dir)
    assert result['file_count'] == 1
    assert result['text_count'] == 1
    assert sum(result['role_counts'].values()) == 1
