from __future__ import annotations

import json
from pathlib import Path

from src.spatial.shapely_area_matching import match_shapely_areas, write_shapely_area_matches


def test_match_shapely_areas_missing_inputs(tmp_path: Path):
    result = match_shapely_areas(tmp_path)
    assert result['status'] == 'missing_inputs'
    assert result['match_count'] == 0


def test_match_shapely_areas_matches_by_bbox_and_area(tmp_path: Path):
    area_payload = {
        'areas': [
            {
                'file_id': 'sample',
                'handle': 'P1',
                'label': '사무실',
                'source_type': 'closed_polyline',
                'area': 100,
                'bbox': [0, 0, 10, 10],
            }
        ]
    }
    shapely_payload = {
        'polygons': [
            {'id': 'shape:bad', 'area': 50, 'bbox': [100, 100, 110, 110]},
            {'id': 'shape:good', 'area': 100, 'bbox': [0, 0, 10, 10]},
        ]
    }
    (tmp_path / 'AREA_ELEMENTS.json').write_text(json.dumps(area_payload, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'SHAPELY_TOPOLOGY.json').write_text(json.dumps(shapely_payload, ensure_ascii=False), encoding='utf-8')
    result = match_shapely_areas(tmp_path)
    assert result['status'] == 'ok'
    assert result['match_count'] == 1
    match = result['matches'][0]
    assert match['shapely_polygon_id'] == 'shape:good'
    assert match['score'] == 1.0


def test_write_shapely_area_matches_creates_json(tmp_path: Path):
    (tmp_path / 'AREA_ELEMENTS.json').write_text(json.dumps({'areas': []}), encoding='utf-8')
    (tmp_path / 'SHAPELY_TOPOLOGY.json').write_text(json.dumps({'polygons': []}), encoding='utf-8')
    result = write_shapely_area_matches(tmp_path)
    assert result['status'] == 'ok'
    assert (tmp_path / 'SHAPELY_AREA_MATCHES.json').exists()
