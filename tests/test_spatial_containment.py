from __future__ import annotations

import json
from pathlib import Path

from src.spatial.containment import TextContainmentAnalyzer
from src.spatial.geometry import Point2D, bbox_from_points
from src.spatial.polygon import point_in_polygon


def test_point_in_polygon_basic_square():
    polygon = [Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10)]
    assert point_in_polygon(Point2D(5, 5), polygon) is True
    assert point_in_polygon(Point2D(15, 5), polygon) is False
    assert point_in_polygon(Point2D(0, 5), polygon) is True


def test_bbox_from_points():
    bbox = bbox_from_points([Point2D(1, 2), Point2D(3, 4), Point2D(-1, 5)])
    assert bbox is not None
    assert bbox.min_x == -1
    assert bbox.max_y == 5
    assert bbox.contains(Point2D(1, 3)) is True


def test_text_containment_analyzer_record():
    record = {
        'file_id': 'sample',
        'relative_path': 'sample.dxf',
        'entities': [
            {
                'handle': 'P1',
                'entity_type': 'POLYLINE',
                'layer': 'ROOM',
                'closed': True,
                'points': [[0, 0, 0], [100, 0, 0], [100, 100, 0], [0, 100, 0]],
            },
            {
                'handle': 'T1',
                'entity_type': 'TEXT',
                'layer': 'TEXT',
                'text': '사무실',
                'insert': [50, 50, 0],
            },
            {
                'handle': 'T2',
                'entity_type': 'TEXT',
                'layer': 'TEXT',
                'text': '외부',
                'insert': [200, 200, 0],
            },
        ],
    }
    result = TextContainmentAnalyzer().analyze_record(record)
    assert result['relation_count'] == 1
    assert result['relations'][0]['text'] == '사무실'
    assert result['relations'][0]['polygon_handle'] == 'P1'


def test_text_containment_analyzer_json_dir(tmp_path: Path):
    json_dir = tmp_path / 'fileized' / 'json'
    json_dir.mkdir(parents=True)
    record = {
        'file_id': 'sample',
        'relative_path': 'sample.dxf',
        'entities': [
            {'handle': 'P1', 'entity_type': 'POLYLINE', 'layer': 'ROOM', 'closed': True, 'points': [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {'handle': 'T1', 'entity_type': 'MTEXT', 'layer': 'TEXT', 'text': '창고', 'insert': [5, 5]},
        ],
    }
    (json_dir / 'sample.json').write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    result = TextContainmentAnalyzer().analyze_json_dir(json_dir)
    assert result['file_count'] == 1
    assert result['relation_count'] == 1
