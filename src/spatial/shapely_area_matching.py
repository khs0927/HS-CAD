from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def match_shapely_areas(workspace: str | Path, *, min_score: float = 0.25) -> dict[str, Any]:
    base = Path(workspace)
    area_path = base / 'AREA_ELEMENTS.json'
    shapely_path = base / 'SHAPELY_TOPOLOGY.json'
    if not area_path.exists() or not shapely_path.exists():
        return {
            'workspace': str(base),
            'status': 'missing_inputs',
            'reason': 'AREA_ELEMENTS.json or SHAPELY_TOPOLOGY.json not found',
            'match_count': 0,
            'matches': [],
        }
    areas = json.loads(area_path.read_text(encoding='utf-8'))
    shapely = json.loads(shapely_path.read_text(encoding='utf-8'))
    polygons = shapely.get('polygons') or []
    matches = []
    for area in areas.get('areas') or []:
        best = _best_match(area, polygons)
        if best and best['score'] >= min_score:
            matches.append(best)
    return {
        'workspace': str(base),
        'status': 'ok',
        'area_count': len(areas.get('areas') or []),
        'shapely_polygon_count': len(polygons),
        'match_count': len(matches),
        'matches': matches,
    }


def write_shapely_area_matches(
    workspace: str | Path,
    *,
    out_json: str | Path | None = None,
    min_score: float = 0.25,
) -> dict[str, Any]:
    result = match_shapely_areas(workspace, min_score=min_score)
    path = Path(out_json) if out_json else Path(workspace) / 'SHAPELY_AREA_MATCHES.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def _best_match(area: dict[str, Any], polygons: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    area_bbox = area.get('bbox') or []
    area_value = float(area.get('area') or 0.0)
    for polygon in polygons:
        polygon_bbox = polygon.get('bbox') or []
        polygon_area = float(polygon.get('area') or 0.0)
        bbox_iou = _bbox_iou(area_bbox, polygon_bbox)
        area_similarity = _area_similarity(area_value, polygon_area)
        score = round(bbox_iou * 0.6 + area_similarity * 0.4, 6)
        row = {
            'target_id': _area_id(area),
            'area_handle': area.get('handle'),
            'area_label': area.get('label'),
            'area_source_type': area.get('source_type'),
            'area': area_value,
            'area_bbox': area_bbox,
            'shapely_polygon_id': polygon.get('id'),
            'shapely_area': polygon_area,
            'shapely_bbox': polygon_bbox,
            'bbox_iou': round(bbox_iou, 6),
            'area_similarity': round(area_similarity, 6),
            'score': score,
            'evidence': [
                f'bbox_iou={round(bbox_iou, 6)}',
                f'area_similarity={round(area_similarity, 6)}',
                f'shapely_polygon_id={polygon.get("id")}',
            ],
        }
        if best is None or row['score'] > best['score']:
            best = row
    return best


def _area_id(area: dict[str, Any]) -> str:
    return f"area:{area.get('file_id')}:{area.get('handle') or area.get('label') or 'unknown'}"


def _area_similarity(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    return min(a, b) / max(a, b)


def _bbox_iou(a: list[Any], b: list[Any]) -> float:
    if len(a) < 4 or len(b) < 4:
        return 0.0
    ax1, ay1, ax2, ay2 = map(float, a[:4])
    bx1, by1, bx2, by2 = map(float, b[:4])
    inter_x1 = max(min(ax1, ax2), min(bx1, bx2))
    inter_y1 = max(min(ay1, ay2), min(by1, by2))
    inter_x2 = min(max(ax1, ax2), max(bx1, bx2))
    inter_y2 = min(max(ay1, ay2), max(by1, by2))
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_a = abs((ax2 - ax1) * (ay2 - ay1))
    area_b = abs((bx2 - bx1) * (by2 - by1))
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0
