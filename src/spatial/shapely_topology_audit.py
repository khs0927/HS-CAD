from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from src.spatial.shapely_topology import _entity_segments


class ShapelyTopologyAuditor:
    """Optional Shapely polygonize_full audit for CAD linework quality."""

    backend_id = 'shapely_topology_audit'

    def is_available(self) -> tuple[bool, str]:
        if importlib.util.find_spec('shapely') is None:
            return False, 'shapely not installed'
        return True, 'shapely installed'

    def audit_record(self, record: dict[str, Any], *, snap_tolerance: float = 0.0) -> dict[str, Any]:
        available, reason = self.is_available()
        file_id = str(record.get('file_id') or '')
        if not available:
            return _empty_result(file_id, record, 'unavailable', reason)

        from shapely.geometry import LineString, MultiLineString
        from shapely.ops import polygonize_full, snap, unary_union

        lines = []
        for entity in record.get('entities') or []:
            for segment in _entity_segments(entity):
                if len(segment) >= 2:
                    lines.append(LineString(segment))
        if not lines:
            return _empty_result(file_id, record, 'ok', 'no linework candidates')

        network = unary_union(lines)
        if snap_tolerance > 0:
            network = snap(network, network, snap_tolerance)
        polygons, cuts, dangles, invalids = polygonize_full(network)
        polygon_count = _geom_count(polygons)
        cut_count = _geom_count(cuts)
        dangle_count = _geom_count(dangles)
        invalid_count = _geom_count(invalids)
        findings = []
        if dangle_count:
            findings.append({
                'type': 'dangling_linework',
                'severity': 'medium',
                'count': dangle_count,
                'message': 'Linework contains dangling edges that may prevent room/area closure.',
            })
        if cut_count:
            findings.append({
                'type': 'cut_edge_linework',
                'severity': 'low',
                'count': cut_count,
                'message': 'Linework contains cut edges not used in polygon faces.',
            })
        if invalid_count:
            findings.append({
                'type': 'invalid_ring_linework',
                'severity': 'high',
                'count': invalid_count,
                'message': 'Linework contains invalid rings from polygonize_full.',
            })
        quality_score = _quality_score(polygon_count, cut_count, dangle_count, invalid_count)
        return {
            'file_id': file_id,
            'relative_path': record.get('relative_path'),
            'backend': self.backend_id,
            'status': 'ok',
            'reason': reason,
            'snap_tolerance': snap_tolerance,
            'line_count': len(lines),
            'polygon_count': polygon_count,
            'cut_count': cut_count,
            'dangle_count': dangle_count,
            'invalid_count': invalid_count,
            'quality_score': quality_score,
            'findings': findings,
        }

    def audit_json_file(self, path: str | Path, *, snap_tolerance: float = 0.0) -> dict[str, Any]:
        source = Path(path)
        record = json.loads(source.read_text(encoding='utf-8'))
        result = self.audit_record(record, snap_tolerance=snap_tolerance)
        result['source_json'] = str(source)
        return result

    def audit_json_dir(self, json_dir: str | Path, *, snap_tolerance: float = 0.0) -> dict[str, Any]:
        base = Path(json_dir)
        files = [self.audit_json_file(path, snap_tolerance=snap_tolerance) for path in sorted(base.glob('*.json'))]
        totals = {
            'line_count': sum(int(item.get('line_count') or 0) for item in files),
            'polygon_count': sum(int(item.get('polygon_count') or 0) for item in files),
            'cut_count': sum(int(item.get('cut_count') or 0) for item in files),
            'dangle_count': sum(int(item.get('dangle_count') or 0) for item in files),
            'invalid_count': sum(int(item.get('invalid_count') or 0) for item in files),
        }
        findings = []
        status_counts: dict[str, int] = {}
        for item in files:
            status = str(item.get('status') or 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            for finding in item.get('findings') or []:
                row = dict(finding)
                row['file_id'] = item.get('file_id')
                row['relative_path'] = item.get('relative_path')
                findings.append(row)
        avg_quality = round(sum(float(item.get('quality_score') or 0) for item in files) / len(files), 6) if files else 0.0
        return {
            'json_dir': str(base),
            'backend': self.backend_id,
            'snap_tolerance': snap_tolerance,
            'file_count': len(files),
            'status_counts': status_counts,
            'totals': totals,
            'avg_quality_score': avg_quality,
            'finding_count': len(findings),
            'findings': findings,
            'files': files,
        }


def _empty_result(file_id: str, record: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        'file_id': file_id,
        'relative_path': record.get('relative_path'),
        'backend': ShapelyTopologyAuditor.backend_id,
        'status': status,
        'reason': reason,
        'snap_tolerance': 0.0,
        'line_count': 0,
        'polygon_count': 0,
        'cut_count': 0,
        'dangle_count': 0,
        'invalid_count': 0,
        'quality_score': 0.0 if status == 'unavailable' else 1.0,
        'findings': [],
    }


def _geom_count(geom: Any) -> int:
    if geom is None or getattr(geom, 'is_empty', False):
        return 0
    if hasattr(geom, 'geoms'):
        return len(list(geom.geoms))
    return 1


def _quality_score(polygons: int, cuts: int, dangles: int, invalids: int) -> float:
    total_issues = cuts + dangles + invalids
    if polygons <= 0 and total_issues <= 0:
        return 1.0
    denominator = polygons + total_issues
    if denominator <= 0:
        return 0.0
    penalty = (cuts * 0.4 + dangles * 0.8 + invalids * 1.0) / denominator
    return round(max(0.0, min(1.0, 1.0 - penalty)), 6)
