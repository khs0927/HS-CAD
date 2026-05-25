from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.spatial.shapely_topology import ShapelyTopologyAnalyzer


def _record():
    return {
        'file_id': 'square',
        'relative_path': 'square.dxf',
        'entities': [
            {'handle': 'L1', 'entity_type': 'LINE', 'layer': 'WALL', 'start': [0, 0], 'end': [10, 0]},
            {'handle': 'L2', 'entity_type': 'LINE', 'layer': 'WALL', 'start': [10, 0], 'end': [10, 10]},
            {'handle': 'L3', 'entity_type': 'LINE', 'layer': 'WALL', 'start': [10, 10], 'end': [0, 10]},
            {'handle': 'L4', 'entity_type': 'LINE', 'layer': 'WALL', 'start': [0, 10], 'end': [0, 0]},
        ],
    }


def test_shapely_topology_analyzer_never_raises_for_record():
    result = ShapelyTopologyAnalyzer().analyze_record(_record())
    assert result['backend'] == 'shapely_topology'
    assert result['status'] in {'ok', 'unavailable'}
    assert 'polygon_count' in result
    assert 'signals' in result


def test_shapely_topology_json_dir(tmp_path: Path):
    json_dir = tmp_path / 'fileized' / 'json'
    json_dir.mkdir(parents=True)
    (json_dir / 'square.json').write_text(json.dumps(_record(), ensure_ascii=False), encoding='utf-8')
    result = ShapelyTopologyAnalyzer().analyze_json_dir(json_dir)
    assert result['file_count'] == 1
    assert result['backend'] == 'shapely_topology'
    assert 'status_counts' in result


@pytest.mark.skipif(importlib.util.find_spec('shapely') is None, reason='shapely not installed')
def test_shapely_topology_polygonizes_square_when_available():
    result = ShapelyTopologyAnalyzer().analyze_record(_record())
    assert result['status'] == 'ok'
    assert result['polygon_count'] >= 1
    assert result['polygons'][0]['area'] == 100
