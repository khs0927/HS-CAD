from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.spatial.boundary_extractor import BoundaryCandidate, extract_boundary_candidates
from src.spatial.geometry import Point2D, bbox_from_points
from src.spatial.polygon import point_in_polygon
from src.spatial.text_entities import iter_texts, text_content
from src.spatial.text_roles import TextRoleInferer


@dataclass
class AreaElement:
    file_id: str
    source_type: str
    handle: str | None
    layer: str | None
    area: float
    bbox: list[float]
    label: str | None = None
    label_handle: str | None = None
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AreaElementInferer:
    """Infer room/area-like elements from fileized vector CAD JSON.

    This is a deterministic foundation. It handles explicit and reconstructed
    boundaries first, and records evidence so optional Shapely/vision/LLM
    backends can improve the result later.
    """

    def __init__(self, *, tolerance: float = 1e-3, circle_segments: int = 64, min_area: float = 1.0):
        self.tolerance = tolerance
        self.circle_segments = circle_segments
        self.min_area = min_area

    def infer_record(self, record: dict[str, Any]) -> dict[str, Any]:
        file_id = str(record.get('file_id') or '')
        entities = record.get('entities') or []
        boundaries = extract_boundary_candidates(entities, tolerance=self.tolerance, circle_segments=self.circle_segments)
        text_roles = TextRoleInferer().infer_record(record)
        role_by_handle = {role.get('handle'): role for role in text_roles.get('roles') or []}
        texts = iter_texts(entities)
        area_elements: list[AreaElement] = []
        for candidate in boundaries:
            area = abs(polygon_area(candidate.polygon))
            bbox = bbox_from_points(candidate.polygon)
            if bbox is None or area < self.min_area:
                continue
            label_entity, label_role = self._best_label(candidate, texts, role_by_handle)
            evidence = [f'boundary_source={candidate.source_type}', f'computed_polygon_area={round(area, 3)}']
            confidence = self._confidence(candidate, label_role, area)
            if label_role:
                evidence.append(f'label_role={label_role.get("role")}; label_confidence={label_role.get("confidence")}')
            area_elements.append(AreaElement(
                file_id=file_id,
                source_type=candidate.source_type,
                handle=candidate.entity.get('handle'),
                layer=candidate.entity.get('layer'),
                area=round(area, 3),
                bbox=[bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                label=text_content(label_entity) if label_entity else None,
                label_handle=label_entity.get('handle') if label_entity else None,
                confidence=confidence,
                evidence=evidence,
            ))
        source_counts: dict[str, int] = {}
        for item in area_elements:
            source_counts[item.source_type] = source_counts.get(item.source_type, 0) + 1
        return {
            'file_id': file_id,
            'relative_path': record.get('relative_path'),
            'area_count': len(area_elements),
            'source_counts': source_counts,
            'areas': [item.to_dict() for item in area_elements],
        }

    def infer_json_file(self, path: str | Path) -> dict[str, Any]:
        source = Path(path)
        record = json.loads(source.read_text(encoding='utf-8'))
        result = self.infer_record(record)
        result['source_json'] = str(source)
        return result

    def infer_json_dir(self, json_dir: str | Path) -> dict[str, Any]:
        base = Path(json_dir)
        files = [self.infer_json_file(path) for path in sorted(base.glob('*.json'))]
        areas: list[dict[str, Any]] = []
        source_counts: dict[str, int] = {}
        for file_result in files:
            for area in file_result.get('areas') or []:
                areas.append(area)
                source_counts[area['source_type']] = source_counts.get(area['source_type'], 0) + 1
        return {
            'json_dir': str(base),
            'file_count': len(files),
            'area_count': len(areas),
            'source_counts': source_counts,
            'files': files,
            'areas': areas,
        }

    def _best_label(
        self,
        candidate: BoundaryCandidate,
        texts: list[tuple[dict[str, Any], Point2D]],
        role_by_handle: dict[Any, dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        best_entity = None
        best_role = None
        best_score = -1.0
        for entity, point in texts:
            if not point_in_polygon(point, candidate.polygon):
                continue
            role = role_by_handle.get(entity.get('handle'))
            role_name = role.get('role') if role else None
            score = 0.4
            if role_name == 'room_or_space_name':
                score += 0.5
            elif role_name == 'table_cell_text':
                score -= 0.5
            elif role_name == 'dimension_or_spec_note':
                score -= 0.2
            if score > best_score:
                best_score = score
                best_entity = entity
                best_role = role
        return best_entity, best_role

    @staticmethod
    def _confidence(candidate: BoundaryCandidate, label_role: dict[str, Any] | None, area: float) -> float:
        score = 0.45
        if candidate.source_type == 'closed_polyline':
            score += 0.25
        elif candidate.source_type == 'line_loop':
            score += 0.18
        elif candidate.source_type == 'circle_approx':
            score += 0.12
        if label_role and label_role.get('role') == 'room_or_space_name':
            score += 0.2
        if area > 0:
            score += 0.05
        return round(min(score, 0.98), 3)


def polygon_area(points: list[Point2D]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    previous = points[-1]
    for current in points:
        area += previous.x * current.y - current.x * previous.y
        previous = current
    return area / 2.0
