from __future__ import annotations

import json
import math
from pathlib import Path

from src.spatial.area_elements import AreaElementInferer, polygon_area
from src.spatial.geometry import Point2D


def test_polygon_area_square():
    points = [Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10)]
    assert polygon_area(points) == 100


def test_area_element_inferer_labels_closed_polyline_room():
    record = {
        'file_id': 'room',
        'relative_path': 'room.dxf',
        'entities': [
            {'handle': 'P1', 'entity_type': 'POLYLINE', 'layer': 'ROOM', 'closed': True, 'points': [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TEXT', 'text': '사무실', 'insert': [5, 5]},
        ],
    }
    result = AreaElementInferer().infer_record(record)
    assert result['area_count'] == 1
    area = result['areas'][0]
    assert area['area'] == 100
    assert area['label'] == '사무실'
    assert area['source_type'] == 'closed_polyline'
    assert area['confidence'] >= 0.8


def test_area_element_inferer_handles_line_loop():
    entities = [
        {'handle': 'L1', 'entity_type': 'LINE', 'layer': 'WALL', 'start': [0, 0], 'end': [20, 0]},
        {'handle': 'L2', 'entity_type': 'LINE', 'layer': 'WALL', 'start': [20, 0], 'end': [20, 10]},
        {'handle': 'L3', 'entity_type': 'LINE', 'layer': 'WALL', 'start': [20, 10], 'end': [0, 10]},
        {'handle': 'L4', 'entity_type': 'LINE', 'layer': 'WALL', 'start': [0, 10], 'end': [0, 0]},
        {'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TEXT', 'text': '창고', 'insert': [5, 5]},
    ]
    result = AreaElementInferer().infer_record({'file_id': 'loop', 'entities': entities})
    assert result['area_count'] == 1
    area = result['areas'][0]
    assert area['source_type'] == 'line_loop'
    assert area['area'] == 200
    assert area['label'] == '창고'


def test_area_element_inferer_handles_circle():
    entities = [
        {'handle': 'C1', 'entity_type': 'CIRCLE', 'layer': 'AREA', 'center': [0, 0], 'radius': 10},
        {'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TEXT', 'text': '원형실', 'insert': [1, 1]},
    ]
    result = AreaElementInferer(circle_segments=96).infer_record({'file_id': 'circle', 'entities': entities})
    assert result['area_count'] == 1
    area = result['areas'][0]
    assert area['source_type'] == 'circle_approx'
    assert math.isclose(area['area'], math.pi * 100, rel_tol=0.02)
    assert area['label'] == '원형실'


def test_area_element_inferer_json_dir(tmp_path: Path):
    json_dir = tmp_path / 'fileized' / 'json'
    json_dir.mkdir(parents=True)
    record = {
        'file_id': 'sample',
        'entities': [
            {'handle': 'P1', 'entity_type': 'POLYLINE', 'layer': 'ROOM', 'closed': True, 'points': [[0, 0], [5, 0], [5, 5], [0, 5]]},
            {'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TEXT', 'text': '실명', 'insert': [2, 2]},
        ],
    }
    (json_dir / 'sample.json').write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    result = AreaElementInferer().infer_json_dir(json_dir)
    assert result['file_count'] == 1
    assert result['area_count'] == 1
    assert result['source_counts']['closed_polyline'] == 1
