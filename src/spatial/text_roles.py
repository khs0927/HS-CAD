from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.spatial.boundary_extractor import extract_boundary_candidates
from src.spatial.containment import TextContainmentAnalyzer
from src.spatial.geometry import Point2D
from src.spatial.text_entities import distance_point_to_segment, drawing_bbox, iter_lines, iter_texts, text_content


@dataclass
class TextRole:
    file_id: str
    text: str
    handle: str | None
    layer: str | None
    insert: list[float]
    role: str
    confidence: float
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TextRoleInferer:
    """Rule-based CAD text role inference foundation.

    Roles are intentionally conservative and evidence-backed so future LLM or
    vision/layout backends can replace or augment the scoring.
    """

    def infer_record(self, record: dict[str, Any]) -> dict[str, Any]:
        file_id = str(record.get('file_id') or '')
        entities = record.get('entities') or []
        texts = iter_texts(entities)
        containment = TextContainmentAnalyzer().analyze_record(record)
        containment_by_handle = self._containment_by_text_handle(containment)
        table_handles = self._table_like_text_handles(entities, texts)
        leader_handles = self._leader_like_text_handles(entities, texts)
        title_handles = self._titleblock_like_text_handles(entities, texts)
        roles: list[TextRole] = []
        for entity, point in texts:
            roles.append(self._infer_text_role(
                file_id=file_id,
                entity=entity,
                point=point,
                containment=containment_by_handle.get(entity.get('handle'), []),
                is_table=entity.get('handle') in table_handles,
                is_leader=entity.get('handle') in leader_handles,
                is_title=entity.get('handle') in title_handles,
            ))
        counts: dict[str, int] = {}
        for item in roles:
            counts[item.role] = counts.get(item.role, 0) + 1
        return {
            'file_id': file_id,
            'relative_path': record.get('relative_path'),
            'text_count': len(roles),
            'role_counts': counts,
            'roles': [role.to_dict() for role in roles],
            'containment_stats': containment.get('stats'),
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
        roles: list[dict[str, Any]] = []
        role_counts: dict[str, int] = {}
        for file_result in files:
            for role in file_result.get('roles') or []:
                roles.append(role)
                role_counts[role['role']] = role_counts.get(role['role'], 0) + 1
        return {
            'json_dir': str(base),
            'file_count': len(files),
            'text_count': len(roles),
            'role_counts': role_counts,
            'files': files,
            'roles': roles,
        }

    def _infer_text_role(
        self,
        *,
        file_id: str,
        entity: dict[str, Any],
        point: Point2D,
        containment: list[dict[str, Any]],
        is_table: bool,
        is_leader: bool,
        is_title: bool,
    ) -> TextRole:
        text = text_content(entity)
        layer = str(entity.get('layer') or '')
        evidence: list[str] = []
        role = 'general_note'
        confidence = 0.35

        if is_title:
            role, confidence = 'titleblock_text', 0.78
            evidence.append('near drawing lower/right titleblock zone')
        if is_table:
            role, confidence = 'table_cell_text', max(confidence, 0.82)
            evidence.append('inside dense orthogonal line grid/table-like area')
        if _looks_like_dimension_or_spec(text):
            role, confidence = 'dimension_or_spec_note', max(confidence, 0.7)
            evidence.append('text matches dimension/spec pattern')
        if containment and not is_table and not is_leader and not _looks_like_dimension_or_spec(text):
            role, confidence = 'room_or_space_name', max(confidence, 0.68)
            evidence.append(f'inside {len(containment)} boundary candidate(s)')
        if _layer_suggests_table(layer):
            role, confidence = 'table_cell_text', max(confidence, 0.7)
            evidence.append('layer suggests table/title/grid')
        if is_leader and role == 'general_note':
            role, confidence = 'leader_note', max(confidence, 0.74)
            evidence.append('near line endpoint/leader-like segment')
        if _layer_suggests_leader(layer) and role == 'general_note':
            role, confidence = 'leader_note', max(confidence, 0.68)
            evidence.append('layer suggests leader/note')

        return TextRole(
            file_id=file_id,
            text=text,
            handle=entity.get('handle'),
            layer=entity.get('layer'),
            insert=[point.x, point.y],
            role=role,
            confidence=round(confidence, 3),
            evidence=evidence,
        )

    @staticmethod
    def _containment_by_text_handle(containment: dict[str, Any]) -> dict[str | None, list[dict[str, Any]]]:
        rows: dict[str | None, list[dict[str, Any]]] = {}
        for relation in containment.get('relations') or []:
            rows.setdefault(relation.get('text_handle'), []).append(relation)
        return rows

    def _table_like_text_handles(self, entities: list[dict[str, Any]], texts: list[tuple[dict[str, Any], Point2D]]) -> set[str | None]:
        lines = iter_lines(entities)
        if len(lines) < 6:
            return set()
        horizontal = []
        vertical = []
        for _, a, b in lines:
            dx = abs(a.x - b.x)
            dy = abs(a.y - b.y)
            if dx > dy * 6:
                horizontal.append((a, b))
            elif dy > dx * 6:
                vertical.append((a, b))
        if len(horizontal) < 3 or len(vertical) < 3:
            return set()
        table_bbox = self._line_bbox(horizontal + vertical)
        if table_bbox is None:
            return set()
        return {entity.get('handle') for entity, point in texts if table_bbox.contains(point)}

    def _leader_like_text_handles(self, entities: list[dict[str, Any]], texts: list[tuple[dict[str, Any], Point2D]]) -> set[str | None]:
        lines = iter_lines(entities)
        handles: set[str | None] = set()
        for entity, point in texts:
            for _, start, end in lines[:5000]:
                if min(_dist(point, start), _dist(point, end), distance_point_to_segment(point, start, end)) < 20:
                    handles.add(entity.get('handle'))
                    break
        return handles

    def _titleblock_like_text_handles(self, entities: list[dict[str, Any]], texts: list[tuple[dict[str, Any], Point2D]]) -> set[str | None]:
        bbox = drawing_bbox(entities)
        if bbox is None:
            return set()
        width = max(bbox.max_x - bbox.min_x, 1e-9)
        height = max(bbox.max_y - bbox.min_y, 1e-9)
        handles: set[str | None] = set()
        for entity, point in texts:
            lower_band = point.y <= bbox.min_y + height * 0.25
            right_band = point.x >= bbox.min_x + width * 0.55
            if lower_band and right_band:
                handles.add(entity.get('handle'))
        return handles

    @staticmethod
    def _line_bbox(lines: list[tuple[Point2D, Point2D]]):
        from src.spatial.geometry import bbox_from_points

        points = []
        for start, end in lines:
            points.extend([start, end])
        return bbox_from_points(points)


def _dist(a: Point2D, b: Point2D) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _looks_like_dimension_or_spec(text: str) -> bool:
    value = text.upper().replace(' ', '')
    if re.search(r'\b\d+(\.\d+)?\s*(MM|M|T|Ø|DIA)\b', text.upper()):
        return True
    if re.search(r'(T\d+|H[-]?\d+|\d+[X×]\d+|\d+@\d+)', value):
        return True
    if any(token in value for token in ('THK', 'SCALE', 'GL', 'FL', 'EL')):
        return True
    return False


def _layer_suggests_table(layer: str) -> bool:
    value = layer.upper()
    return any(token in value for token in ('TABLE', 'TITLE', 'SHEET', 'GRID'))


def _layer_suggests_leader(layer: str) -> bool:
    value = layer.upper()
    return any(token in value for token in ('LEAD', 'DIM', 'NOTE'))
