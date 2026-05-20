from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Iterable

from src.semantics.layer_taxonomy import classify_layer, normalize_layer_name


def _entity(obj: dict[str, Any]) -> str:
    return str(obj.get('entity_type') or obj.get('object_name') or 'UNKNOWN').upper()


def _points(obj: dict[str, Any]) -> list[list[float]]:
    pts = obj.get('points') or []
    if pts:
        return pts
    coords = obj.get('coordinates') or []
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        step = 3 if len(coords) % 3 == 0 else 2
        out = []
        for i in range(0, len(coords), step):
            chunk = coords[i:i + step]
            if len(chunk) >= 2:
                out.append([float(chunk[0]), float(chunk[1]), float(chunk[2]) if len(chunk) > 2 else 0.0])
        return out
    return []


def _line_length(obj: dict[str, Any]) -> float | None:
    start = obj.get('start') or []
    end = obj.get('end') or []
    if len(start) >= 2 and len(end) >= 2:
        z1 = float(start[2]) if len(start) > 2 else 0.0
        z2 = float(end[2]) if len(end) > 2 else 0.0
        return math.dist((float(start[0]), float(start[1]), z1), (float(end[0]), float(end[1]), z2))
    return None


def _bbox_from_points(points: list[list[float]]) -> dict[str, float] | None:
    if not points:
        return None
    xs = [float(p[0]) for p in points if len(p) >= 2]
    ys = [float(p[1]) for p in points if len(p) >= 2]
    if not xs or not ys:
        return None
    return {'min_x': min(xs), 'max_x': max(xs), 'min_y': min(ys), 'max_y': max(ys), 'width': max(xs)-min(xs), 'height': max(ys)-min(ys)}


def _infer_geometry(obj: dict[str, Any]) -> dict[str, Any]:
    ent = _entity(obj)
    if 'LINE' in ent and 'POLYLINE' not in ent:
        length = obj.get('length') or _line_length(obj)
        return {'geometry_kind': 'line', 'length': length, 'bbox': None, 'closed': False}
    if 'POLYLINE' in ent:
        pts = _points(obj)
        return {'geometry_kind': 'polyline', 'point_count': len(pts), 'bbox': _bbox_from_points(pts), 'closed': bool(obj.get('closed')), 'area': obj.get('area')}
    if ent in {'TEXT', 'MTEXT'} or 'TEXT' in ent:
        return {'geometry_kind': 'text', 'text_length': len(str(obj.get('text') or ''))}
    if 'INSERT' in ent or 'BLOCK' in ent:
        return {'geometry_kind': 'block_reference', 'block_name': obj.get('effective_name') or obj.get('name')}
    if 'CIRCLE' in ent:
        return {'geometry_kind': 'circle', 'radius': obj.get('radius'), 'area': obj.get('area')}
    if 'ARC' in ent:
        return {'geometry_kind': 'arc', 'radius': obj.get('radius')}
    return {'geometry_kind': 'unknown'}


ROLE_TO_SEMANTIC = {
    'structural_member': 'structural_member',
    'lightweight_wall': 'nonstructural_wall',
    'masonry_wall': 'nonstructural_wall',
    'nonstructural_wall': 'nonstructural_wall',
    'nonstructural_wall_variant': 'nonstructural_wall',
    'elevation_line': 'elevation_line',
    'elevation_line_variant': 'elevation_line',
    'door_plan': 'door',
    'door_elevation': 'door_elevation',
    'window_plan': 'window',
    'window_frame': 'window_frame',
    'window_elevation': 'window_elevation',
    'stair': 'stair',
    'dimension': 'dimension',
    'leader': 'leader',
    'main_column_centerline': 'centerline_main',
    'wall_aux_centerline': 'centerline_aux_wall',
    'other_aux_centerline': 'centerline_aux_other',
    'nonplot_guide': 'guide_nonplot',
    'built_in_fixture': 'fixed_furniture',
    'loose_furniture': 'loose_furniture',
    'symbol_line': 'symbol_line',
    'symbol_text': 'symbol_text',
    'title_text': 'title_text',
    'cadastral_line': 'site_boundary',
    'parking_line': 'parking_line',
    'insulation': 'insulation',
    'zone_boundary': 'zone_boundary',
    'drawing_border': 'title_block',
    'shared_mark': 'markup',
    'etc_line': 'elevation_line',
    'etc_line_variant': 'elevation_line',
}


def _semantic_type(category: str, role: str) -> str:
    if role in ROLE_TO_SEMANTIC:
        return ROLE_TO_SEMANTIC[role]
    if category == 'wall':
        return 'nonstructural_wall'
    if category == 'structure':
        return 'structural_member'
    return 'unknown' if category == 'unknown' else str(role or category)


def _structural_role(semantic_type: str, category: str) -> str:
    if semantic_type == 'structural_member' or category == 'structure':
        return 'structural'
    if semantic_type == 'nonstructural_wall':
        return 'nonstructural'
    if semantic_type in {'dimension', 'leader', 'symbol_line', 'symbol_text', 'title_text'}:
        return 'annotation'
    if semantic_type == 'guide_nonplot':
        return 'guide'
    if semantic_type in {'fixed_furniture', 'loose_furniture'}:
        return 'furniture'
    if semantic_type in {'door', 'window', 'window_frame', 'door_elevation', 'window_elevation'}:
        return 'opening'
    if semantic_type in {'site_boundary', 'parking_line', 'zone_boundary'}:
        return 'site'
    return 'unknown'


def _discipline(semantic_type: str, structural_role: str) -> str:
    if structural_role == 'structural':
        return 'structure'
    if structural_role in {'annotation', 'guide'}:
        return 'annotation'
    if structural_role == 'site':
        return 'site'
    if structural_role == 'furniture':
        return 'furniture'
    if semantic_type != 'unknown':
        return 'architecture'
    return 'unknown'


def _hints(obj: dict[str, Any], geom: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    geometry_hint = geom.get('geometry_kind')
    block_hint = None
    text_hint = None
    if geometry_hint == 'block_reference':
        block_hint = str(obj.get('effective_name') or obj.get('name') or '')
    if geometry_hint == 'text':
        text = str(obj.get('text') or '')
        if any(token in text for token in ('㎡', 'm2', 'M2', '평')):
            text_hint = 'area_text_hint'
        elif any(token in text.upper() for token in ('ROOM', '사무실', '창고', '화장실', '복도', '계단실', '기계실')):
            text_hint = 'room_name_hint'
        elif text:
            text_hint = 'text'
    return geometry_hint, block_hint, text_hint


def classify_object(obj: dict[str, Any]) -> dict[str, Any]:
    layer_name = normalize_layer_name(obj.get('layer'))
    layer_sem = classify_layer(layer_name, obj.get('color'))
    geom = _infer_geometry(obj)
    ent = _entity(obj)
    role = layer_sem['role']
    category = layer_sem['category']
    confidence = float(layer_sem.get('confidence') or 0.2)
    reason = ['layer_rule' if category != 'unknown' else 'unknown_layer']
    evidence: list[dict[str, Any]] = [
        {
            'stage': 'layer',
            'input': layer_name,
            'category': category,
            'role': role,
            'confidence': confidence,
            'note': 'primary semantic source',
        },
        {
            'stage': 'geometry',
            'input': ent,
            'geometry_kind': geom.get('geometry_kind'),
            'note': 'supporting refinement; does not override strong layer rules',
        },
    ]

    # Geometry/entity refinements without overriding strong layer rules too much.
    if ent in {'TEXT', 'MTEXT'} or 'TEXT' in ent:
        if category == 'unknown':
            category, role, confidence = 'annotation', 'text_unknown_layer', 0.55
            reason.append('entity_text')
        elif category not in {'symbol', 'title', 'annotation'}:
            reason.append('text_on_non_text_layer')
    elif 'INSERT' in ent or 'BLOCK' in ent:
        block_name = str(obj.get('effective_name') or obj.get('name') or '').upper()
        if category == 'unknown':
            if block_name.startswith('D') or 'DOOR' in block_name:
                category, role, confidence = 'opening', 'door_block_by_name', 0.72
            elif block_name.startswith('W') or 'WIN' in block_name:
                category, role, confidence = 'opening', 'window_block_by_name', 0.72
            elif block_name.startswith('C') or 'COL' in block_name:
                category, role, confidence = 'structure', 'column_block_by_name', 0.72
            else:
                category, role, confidence = 'block', 'generic_block', 0.45
            reason.append('block_name_heuristic')
            evidence.append({'stage': 'block_name', 'input': block_name, 'category': category, 'role': role, 'confidence': confidence})
    elif 'POLYLINE' in ent and obj.get('closed') and category == 'unknown':
        category, role, confidence = 'boundary_candidate', 'closed_polyline_unknown_layer', 0.58
        reason.append('closed_polyline')
        evidence.append({'stage': 'geometry', 'input': 'closed_polyline', 'category': category, 'role': role, 'confidence': confidence})

    if layer_name == 'DEFPOINTS':
        reason.append('nonplot')
    if layer_sem.get('color_matches_rule') is False:
        confidence = max(0.3, confidence - 0.15)
        reason.append('color_mismatch')
    semantic_type = _semantic_type(category, role)
    structural_role = _structural_role(semantic_type, category)
    discipline = _discipline(semantic_type, structural_role)
    geometry_hint, block_hint, text_hint = _hints(obj, geom)
    warnings: list[str] = []
    if layer_sem.get('color_matches_rule') is False:
        warnings.append(
            f"Layer {layer_name} recommends color {layer_sem.get('expected_color_index')}, actual color is {layer_sem.get('actual_color')}."
        )
    if semantic_type == 'unknown':
        warnings.append('Object could not be confidently classified by layer, geometry, block name, or text.')
    if confidence < 0.5:
        warnings.append('Low confidence classification; review before using this object in modification commands.')

    return {
        'handle': obj.get('handle'),
        'raw': obj,
        'layer': obj.get('layer'),
        'normalized_layer': layer_name,
        'object_name': obj.get('object_name'),
        'entity_type': obj.get('entity_type'),
        'layer_category': category,
        'semantic_type': semantic_type,
        'semantic_subtype': role,
        'structural_role': structural_role,
        'discipline': discipline,
        'is_structural': structural_role == 'structural',
        'is_nonstructural': structural_role == 'nonstructural',
        'is_annotation': structural_role == 'annotation',
        'is_dimension': semantic_type == 'dimension',
        'is_furniture': structural_role == 'furniture',
        'is_opening': structural_role == 'opening',
        'is_guide': structural_role == 'guide',
        'is_title': semantic_type in {'title_text', 'title_block'},
        'is_boundary': semantic_type in {'site_boundary', 'zone_boundary'},
        'is_elevation': semantic_type in {'elevation_line', 'door_elevation', 'window_elevation'},
        'recommended_color': layer_sem.get('expected_color_index'),
        'actual_color': layer_sem.get('actual_color'),
        'color_matches_standard': layer_sem.get('color_matches_rule'),
        'geometry_hint': geometry_hint,
        'block_hint': block_hint,
        'text_hint': text_hint,
        'category': category,
        'role': role,
        'structural': bool(layer_sem.get('structural')),
        'material': layer_sem.get('material'),
        'confidence': round(confidence, 3),
        'reason': '; '.join(reason),
        'reason_codes': reason,
        'warnings': warnings,
        'evidence': evidence,
        'analysis_order': ['layer', 'geometry_or_entity_type', 'block_name_or_text', 'screen_capture_support_only'],
        'layer_semantic': layer_sem,
        'geometry': geom,
        'source': 'layer_then_geometry_then_name_text',
    }


def classify_objects(objects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [classify_object(obj) for obj in objects]


def summarize_semantics(classifications: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(classifications)
    by_category = Counter(row.get('category', 'unknown') for row in rows)
    by_role = Counter(row.get('role', 'unknown') for row in rows)
    by_semantic_type = Counter(row.get('semantic_type', 'unknown') for row in rows)
    by_structural_role = Counter(row.get('structural_role', 'unknown') for row in rows)
    by_discipline = Counter(row.get('discipline', 'unknown') for row in rows)
    by_layer = defaultdict(Counter)
    low_confidence = []
    color_mismatches = []
    by_source = Counter()
    for row in rows:
        by_layer[str(row.get('layer') or '<none>')][str(row.get('category') or 'unknown')] += 1
        if float(row.get('confidence') or 0) < 0.5:
            low_confidence.append(row)
        if row.get('layer_semantic', {}).get('color_matches_rule') is False:
            color_mismatches.append(row)
        by_source[str(row.get('source') or 'unknown')] += 1
    return {
        'object_count': len(rows),
        'total_objects': len(rows),
        'classified_objects': sum(1 for row in rows if row.get('semantic_type') != 'unknown'),
        'unknown_objects': sum(1 for row in rows if row.get('semantic_type') == 'unknown'),
        'by_category': dict(by_category),
        'by_role': dict(by_role),
        'by_semantic_type': dict(by_semantic_type),
        'by_layer_category_flat': dict(by_category),
        'by_structural_role': dict(by_structural_role),
        'by_discipline': dict(by_discipline),
        'by_layer_category': {layer: dict(counter) for layer, counter in sorted(by_layer.items())},
        'low_confidence_count': len(low_confidence),
        'low_confidence_samples': low_confidence[:100],
        'color_mismatch_count': len(color_mismatches),
        'color_mismatch_samples': color_mismatches[:100],
        'warnings_count': sum(len(row.get('warnings') or []) for row in rows),
        'by_source': dict(by_source),
        'analysis_order': ['layer', 'geometry_or_entity_type', 'block_name_or_text', 'screen_capture_support_only'],
    }
