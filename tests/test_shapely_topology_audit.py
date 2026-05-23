from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.spatial.shapely_topology_audit import ShapelyTopologyAuditor


def _open_line_record():
    return {
        'file_id': 'open_lines',
        'relative_path': 'open_lines.dxf',
        'entities': [
            {'handle': 'L1', 'entity_type': 'LINE', 'layer': 'WALL', 'start': [0, 0], 'end': [10, 0]},
            {'handle': 'L2', 'entity_type': 'LINE', 'layer': 'WALL', 'start': [10, 0], 'end': [10, 10]},
        ],
    }


def test_shapely_topology_audit_never_raises_for_record():
    result = ShapelyTopologyAuditor().audit_record(_open_line_record())
    assert result['backend'] == 'shapely_topology_audit'
    assert result['status'] in {'ok', 'unavailable'}
    assert 'quality_score' in result
    assert 'findings' in result


def test_shapely_topology_audit_json_dir(tmp_path: Path):
    json_dir = tmp_path / 'fileized' / 'json'
    json_dir.mkdir(parents=True)
    (json_dir / 'open_lines.json').write_text(json.dumps(_open_line_record(), ensure_ascii=False), encoding='utf-8')
    result = ShapelyTopologyAuditor().audit_json_dir(json_dir)
    assert result['file_count'] == 1
    assert 'totals' in result
    assert 'finding_count' in result


@pytest.mark.skipif(importlib.util.find_spec('shapely') is None, reason='shapely not installed')
def test_shapely_topology_audit_detects_dangles_when_available():
    result = ShapelyTopologyAuditor().audit_record(_open_line_record())
    assert result['status'] == 'ok'
    assert result['dangle_count'] >= 1 or result['cut_count'] >= 1
    assert result['quality_score'] <= 1.0
