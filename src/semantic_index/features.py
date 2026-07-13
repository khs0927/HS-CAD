from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable

import numpy as np

from src.corpus.schema import FileizedDrawingRecord
from src.semantic_index.schema import SemanticVector

FEATURE_VERSION = 'geometry-v1'
ENTITY_TYPES = (
    'LINE',
    'LWPOLYLINE',
    'POLYLINE',
    'CIRCLE',
    'ARC',
    'INSERT',
    'DIMENSION',
    'HATCH',
    'SPLINE',
    'ELLIPSE',
    'LEADER',
    'MLEADER',
    'SOLID',
    '3DFACE',
    'POINT',
    'VIEWPORT',
    'OTHER',
)
TEXT_ENTITY_TYPES = {'TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF'}
ANGLE_BIN_COUNT = 12


class GeometryFeatureExtractor:
    """Build a deterministic vector after completely removing text entities."""

    feature_version = FEATURE_VERSION

    def extract(self, record: FileizedDrawingRecord) -> SemanticVector:
        source_entities = list(record.entities or [])
        entities = [item for item in source_entities if not _is_text_entity(item)]
        entity_counts = Counter(_entity_type(item) for item in entities)
        total = max(1, len(entities))

        entity_hist = [entity_counts.get(name, 0) / total for name in ENTITY_TYPES]
        angle_hist, orthogonal_ratio = _angle_features(entities)
        layer_features = _distribution_features(_layer_names(entities))
        block_features = _block_features(record)

        polyline_count = entity_counts['LWPOLYLINE'] + entity_counts['POLYLINE']
        closed_count = sum(1 for item in entities if _entity_type(item) in {'LWPOLYLINE', 'POLYLINE'} and _is_closed(item))
        topology = [
            closed_count / max(1, polyline_count),
            orthogonal_ratio,
            entity_counts['INSERT'] / total,
            entity_counts['DIMENSION'] / total,
            (entity_counts['CIRCLE'] + entity_counts['ARC']) / total,
        ]
        complexity = [math.tanh(math.log1p(len(entities)) / 10.0), _aspect_feature(entities)]

        raw = np.asarray(entity_hist + angle_hist + layer_features + block_features + topology + complexity, dtype=np.float32)
        norm = float(np.linalg.norm(raw))
        vector = raw / norm if norm else raw

        return SemanticVector(
            file_id=record.file_id,
            source_path=record.source_path,
            relative_path=record.relative_path,
            feature_version=self.feature_version,
            vector=vector.astype(float).tolist(),
            metadata={
                'entity_count': len(entities),
                'source_entity_count': len(source_entities),
                'ignored_text_entity_count': len(source_entities) - len(entities),
                'layer_count': len(set(_layer_names(entities))),
                'block_count': len(record.blocks or []),
                'text_ignored': True,
                'vector_dimensions': int(vector.size),
            },
        )


def _raw_entity_type(item: dict[str, Any]) -> str:
    value = str(item.get('entity_type') or item.get('type') or item.get('ObjectName') or '').upper()
    return value.removeprefix('ACDB').removeprefix('ZWCAD.')


def _is_text_entity(item: dict[str, Any]) -> bool:
    value = _raw_entity_type(item)
    return value in TEXT_ENTITY_TYPES or value.endswith('TEXT') or value.endswith('ATTRIBUTE')


def _entity_type(item: dict[str, Any]) -> str:
    value = _raw_entity_type(item)
    aliases = {'INSERTREF': 'INSERT', 'BLOCKREFERENCE': 'INSERT', 'POLYLINE2D': 'POLYLINE'}
    value = aliases.get(value, value)
    return value if value in ENTITY_TYPES else 'OTHER'


def _layer_names(entities: list[dict[str, Any]]) -> list[str]:
    return [str(item.get('layer') or item.get('Layer') or '0') for item in entities]


def _distribution_features(values: Iterable[str]) -> list[float]:
    counts = Counter(values)
    total = sum(counts.values())
    if not total:
        return [0.0, 0.0, 0.0]
    shares = np.asarray([count / total for count in counts.values()], dtype=np.float64)
    entropy = float(-(shares * np.log(shares + 1e-12)).sum())
    max_entropy = math.log(max(1, len(counts)))
    return [
        math.tanh(math.log1p(len(counts)) / 5.0),
        float(shares.max()),
        entropy / max_entropy if max_entropy else 0.0,
    ]


def _block_features(record: FileizedDrawingRecord) -> list[float]:
    counts = [max(0, int(row.get('count') or 0)) for row in record.blocks or []]
    total = sum(counts)
    if not total:
        return [0.0, 0.0, 0.0]
    return [
        math.tanh(math.log1p(total) / 8.0),
        min(1.0, len(counts) / max(1, total)),
        max(counts) / total,
    ]


def _angle_features(entities: list[dict[str, Any]]) -> tuple[list[float], float]:
    bins = np.zeros(ANGLE_BIN_COUNT, dtype=np.float64)
    angles: list[float] = []
    for item in entities:
        if _entity_type(item) != 'LINE':
            continue
        pair = _line_points(item)
        if pair is None:
            continue
        (x1, y1), (x2, y2) = pair
        if math.isclose(x1, x2) and math.isclose(y1, y2):
            continue
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        angles.append(angle)
        index = min(ANGLE_BIN_COUNT - 1, int(angle / (180.0 / ANGLE_BIN_COUNT)))
        bins[index] += 1
    if angles:
        bins /= len(angles)
    orthogonal = sum(1 for angle in angles if _distance_to_axis(angle) <= 5.0) / max(1, len(angles))
    return bins.astype(float).tolist(), orthogonal


def _distance_to_axis(angle: float) -> float:
    return min(abs(angle - candidate) for candidate in (0.0, 90.0, 180.0))


def _line_points(item: dict[str, Any]) -> tuple[tuple[float, float], tuple[float, float]] | None:
    start = item.get('start') or item.get('StartPoint') or item.get('p1')
    end = item.get('end') or item.get('EndPoint') or item.get('p2')
    a = _xy(start)
    b = _xy(end)
    return (a, b) if a and b else None


def _xy(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        try:
            return float(value.get('x')), float(value.get('y'))
        except (TypeError, ValueError):
            return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError):
            return None
    return None


def _is_closed(item: dict[str, Any]) -> bool:
    value = item.get('closed')
    if value is None:
        value = item.get('is_closed')
    if value is None:
        value = item.get('Closed')
    return bool(value)


def _aspect_feature(entities: list[dict[str, Any]]) -> float:
    points: list[tuple[float, float]] = []
    for item in entities:
        pair = _line_points(item)
        if pair:
            points.extend(pair)
        for key in ('center', 'insert', 'point'):
            point = _xy(item.get(key))
            if point:
                points.append(point)
        for point_value in item.get('vertices') or item.get('points') or []:
            point = _xy(point_value)
            if point:
                points.append(point)
    if len(points) < 2:
        return 0.0
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    if width <= 0 or height <= 0:
        return 0.0
    return math.tanh(math.log(width / height))
