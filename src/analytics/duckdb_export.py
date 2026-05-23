from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from src.workers.provenance import build_provenance


TABLE_ORDER = [
    'files',
    'entities',
    'layers',
    'texts',
    'areas',
    'graph_nodes',
    'graph_edges',
    'cross_validation_results',
    'graph_audit_findings',
]


EMPTY_SCHEMAS: dict[str, dict[str, str]] = {
    'files': {'file_id': 'VARCHAR', 'relative_path': 'VARCHAR', 'engine': 'VARCHAR', 'entity_count': 'INTEGER', 'text_count': 'INTEGER', 'source_json': 'VARCHAR'},
    'entities': {'file_id': 'VARCHAR', 'handle': 'VARCHAR', 'entity_type': 'VARCHAR', 'layer': 'VARCHAR', 'color': 'VARCHAR', 'linetype': 'VARCHAR', 'bbox_min_x': 'DOUBLE', 'bbox_min_y': 'DOUBLE', 'bbox_max_x': 'DOUBLE', 'bbox_max_y': 'DOUBLE', 'payload_json': 'VARCHAR'},
    'layers': {'layer': 'VARCHAR', 'predicted_semantic': 'VARCHAR', 'confidence': 'DOUBLE', 'counts_json': 'VARCHAR', 'evidence_json': 'VARCHAR'},
    'texts': {'file_id': 'VARCHAR', 'handle': 'VARCHAR', 'text': 'VARCHAR', 'role': 'VARCHAR', 'layer': 'VARCHAR', 'confidence': 'DOUBLE', 'bbox_json': 'VARCHAR', 'evidence_json': 'VARCHAR'},
    'areas': {'file_id': 'VARCHAR', 'handle': 'VARCHAR', 'label': 'VARCHAR', 'source_type': 'VARCHAR', 'area': 'DOUBLE', 'confidence': 'DOUBLE', 'bbox_json': 'VARCHAR', 'evidence_json': 'VARCHAR'},
    'graph_nodes': {'node_id': 'VARCHAR', 'kind': 'VARCHAR', 'payload_json': 'VARCHAR'},
    'graph_edges': {'source': 'VARCHAR', 'target': 'VARCHAR', 'relation': 'VARCHAR', 'payload_json': 'VARCHAR'},
    'cross_validation_results': {'target_type': 'VARCHAR', 'target_id': 'VARCHAR', 'agreement_score': 'DOUBLE', 'confidence': 'DOUBLE', 'warnings_json': 'VARCHAR', 'signals_json': 'VARCHAR'},
    'graph_audit_findings': {'finding_type': 'VARCHAR', 'severity': 'VARCHAR', 'node_id': 'VARCHAR', 'message': 'VARCHAR', 'evidence_json': 'VARCHAR'},
}


class DuckDBAnalyticsExporter:
    backend_id = 'duckdb_export'

    def is_available(self) -> tuple[bool, str]:
        if importlib.util.find_spec('duckdb') is None:
            return False, 'duckdb not installed'
        return True, 'duckdb installed'

    def export_workspace(self, workspace: str | Path) -> dict[str, Any]:
        available, reason = self.is_available()
        base = Path(workspace)
        analytics_dir = base / 'analytics'
        db_path = base / 'hscad_analysis.duckdb'
        report_path = base / 'DUCKDB_EXPORT_REPORT.md'
        provenance = build_provenance(
            workspace=base,
            backend=self.backend_id,
            algorithm='json_artifacts_to_duckdb_parquet',
            source_artifacts=_source_artifacts(base),
            worker_name='duckdb_export',
        )
        if not available:
            result = _empty_result(base, 'unavailable', reason, provenance)
            report_path.write_text(_markdown(result), encoding='utf-8')
            return result

        import duckdb

        analytics_dir.mkdir(parents=True, exist_ok=True)
        tables = _load_workspace_tables(base)
        con = duckdb.connect(str(db_path))
        try:
            table_counts: dict[str, int] = {}
            parquet_paths: dict[str, str] = {}
            for table_name in TABLE_ORDER:
                rows = tables.get(table_name, [])
                _create_table(con, table_name, rows)
                table_counts[table_name] = len(rows)
                parquet_path = analytics_dir / f'{table_name}.parquet'
                con.execute(f"COPY {table_name} TO ? (FORMAT PARQUET)", [str(parquet_path)])
                parquet_paths[table_name] = str(parquet_path)
            sql_reports = _build_sql_reports(con)
        finally:
            con.close()
        result = {
            'backend': self.backend_id,
            'status': 'ok',
            'reason': reason,
            'workspace': str(base),
            'duckdb_path': str(db_path),
            'analytics_dir': str(analytics_dir),
            'table_counts': table_counts,
            'parquet_paths': parquet_paths,
            'sql_reports': sql_reports,
            'spatial_capability': _detect_spatial_capability(db_path),
            'provenance': provenance,
        }
        report_path.write_text(_markdown(result), encoding='utf-8')
        return result


def write_duckdb_export(workspace: str | Path, *, out_json: str | Path | None = None) -> dict[str, Any]:
    base = Path(workspace)
    result = DuckDBAnalyticsExporter().export_workspace(base)
    json_path = Path(out_json) if out_json else base / 'DUCKDB_EXPORT.json'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def _source_artifacts(base: Path) -> list[str]:
    candidates = [base / 'fileized' / 'json', base / 'LAYER_SEMANTICS.json', base / 'TEXT_ROLE_INFERENCE.json', base / 'AREA_ELEMENTS.json', base / 'SPATIAL_GRAPH.json', base / 'CROSS_VALIDATION.json', base / 'GRAPH_AUDIT.json']
    return [str(path) for path in candidates if path.exists()]


def _load_workspace_tables(base: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        'files': _rows_files(base),
        'entities': _rows_entities(base),
        'layers': _rows_layers(base),
        'texts': _rows_texts(base),
        'areas': _rows_areas(base),
        'graph_nodes': _rows_graph_nodes(base),
        'graph_edges': _rows_graph_edges(base),
        'cross_validation_results': _rows_cross_validation(base),
        'graph_audit_findings': _rows_graph_audit(base),
    }


def _iter_fileized_records(base: Path) -> list[tuple[Path, dict[str, Any]]]:
    json_dir = base / 'fileized' / 'json'
    return [(path, _read_json(path)) for path in sorted(json_dir.glob('*.json'))] if json_dir.exists() else []


def _rows_files(base: Path) -> list[dict[str, Any]]:
    rows = []
    for path, payload in _iter_fileized_records(base):
        rows.append({'file_id': str(payload.get('file_id') or path.stem), 'relative_path': str(payload.get('relative_path') or ''), 'engine': str(payload.get('engine') or payload.get('metadata', {}).get('engine') or ''), 'entity_count': len(payload.get('entities') or []), 'text_count': len(payload.get('texts') or []), 'source_json': str(path)})
    return rows


def _rows_entities(base: Path) -> list[dict[str, Any]]:
    rows = []
    for path, payload in _iter_fileized_records(base):
        file_id = str(payload.get('file_id') or path.stem)
        for entity in payload.get('entities') or []:
            if not isinstance(entity, dict):
                continue
            bbox = entity.get('bbox') or []
            rows.append({'file_id': file_id, 'handle': str(entity.get('handle') or ''), 'entity_type': str(entity.get('entity_type') or entity.get('type') or ''), 'layer': str(entity.get('layer') or ''), 'color': str(entity.get('color') or ''), 'linetype': str(entity.get('linetype') or ''), 'bbox_min_x': _bbox_value(bbox, 0), 'bbox_min_y': _bbox_value(bbox, 1), 'bbox_max_x': _bbox_value(bbox, 2), 'bbox_max_y': _bbox_value(bbox, 3), 'payload_json': json.dumps(entity, ensure_ascii=False)})
    return rows


def _rows_layers(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'LAYER_SEMANTICS.json')
    return [{'layer': str(layer.get('layer') or ''), 'predicted_semantic': str(layer.get('predicted_semantic') or layer.get('semantic') or ''), 'confidence': float(layer.get('confidence') or 0.0), 'counts_json': json.dumps(layer.get('counts') or {}, ensure_ascii=False), 'evidence_json': json.dumps(layer.get('evidence') or [], ensure_ascii=False)} for layer in payload.get('layers') or []]


def _rows_texts(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'TEXT_ROLE_INFERENCE.json')
    rows = [{'file_id': str(role.get('file_id') or ''), 'handle': str(role.get('handle') or ''), 'text': str(role.get('text') or ''), 'role': str(role.get('role') or ''), 'layer': str(role.get('layer') or ''), 'confidence': float(role.get('confidence') or 0.0), 'bbox_json': json.dumps(role.get('bbox') or [], ensure_ascii=False), 'evidence_json': json.dumps(role.get('evidence') or [], ensure_ascii=False)} for role in payload.get('roles') or []]
    if rows:
        return rows
    for path, payload in _iter_fileized_records(base):
        file_id = str(payload.get('file_id') or path.stem)
        for entity in payload.get('entities') or []:
            if str(entity.get('entity_type') or entity.get('type') or '').upper() not in {'TEXT', 'MTEXT'}:
                continue
            rows.append({'file_id': file_id, 'handle': str(entity.get('handle') or ''), 'text': str(entity.get('text') or entity.get('value') or entity.get('content') or ''), 'role': '', 'layer': str(entity.get('layer') or ''), 'confidence': 0.0, 'bbox_json': json.dumps(entity.get('bbox') or [], ensure_ascii=False), 'evidence_json': json.dumps(['fileized entity fallback'], ensure_ascii=False)})
    return rows


def _rows_areas(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'AREA_ELEMENTS.json')
    return [{'file_id': str(area.get('file_id') or ''), 'handle': str(area.get('handle') or ''), 'label': str(area.get('label') or ''), 'source_type': str(area.get('source_type') or ''), 'area': float(area.get('area') or 0.0), 'confidence': float(area.get('confidence') or 0.0), 'bbox_json': json.dumps(area.get('bbox') or [], ensure_ascii=False), 'evidence_json': json.dumps(area.get('evidence') or [], ensure_ascii=False)} for area in payload.get('areas') or []]


def _rows_graph_nodes(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'SPATIAL_GRAPH.json')
    nodes = payload.get('nodes') or []
    iterable = [dict(value, id=key) if isinstance(value, dict) else {'id': key} for key, value in nodes.items()] if isinstance(nodes, dict) else [node for node in nodes if isinstance(node, dict)]
    return [{'node_id': str(node.get('id') or node.get('node_id') or ''), 'kind': str(node.get('kind') or node.get('type') or ''), 'payload_json': json.dumps(node, ensure_ascii=False)} for node in iterable]


def _rows_graph_edges(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'SPATIAL_GRAPH.json')
    rows = []
    for edge in payload.get('edges') or []:
        if isinstance(edge, dict):
            rows.append({'source': str(edge.get('source') or edge.get('from') or edge.get('src') or ''), 'target': str(edge.get('target') or edge.get('to') or edge.get('dst') or ''), 'relation': str(edge.get('relation') or edge.get('type') or edge.get('label') or ''), 'payload_json': json.dumps(edge, ensure_ascii=False)})
    return rows


def _rows_cross_validation(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'CROSS_VALIDATION.json')
    rows = []
    for item in payload.get('results') or []:
        if isinstance(item, dict):
            rows.append({'target_type': str(item.get('target_type') or ''), 'target_id': str(item.get('target_id') or ''), 'agreement_score': float(item.get('agreement_score') or 0.0), 'confidence': float(item.get('confidence') or 0.0), 'warnings_json': json.dumps(item.get('warnings') or [], ensure_ascii=False), 'signals_json': json.dumps(item.get('signals') or {}, ensure_ascii=False)})
    return rows


def _rows_graph_audit(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'GRAPH_AUDIT.json')
    rows = []
    for finding in payload.get('findings') or []:
        if isinstance(finding, dict):
            rows.append({'finding_type': str(finding.get('type') or ''), 'severity': str(finding.get('severity') or ''), 'node_id': str(finding.get('node_id') or ''), 'message': str(finding.get('message') or ''), 'evidence_json': json.dumps(finding.get('evidence') or [], ensure_ascii=False)})
    return rows


def _create_table(con: Any, table_name: str, rows: list[dict[str, Any]]) -> None:
    con.execute(f'DROP TABLE IF EXISTS {table_name}')
    if rows:
        con.register('_hscad_rows', rows)
        try:
            con.execute(f'CREATE TABLE {table_name} AS SELECT * FROM _hscad_rows')
        finally:
            con.unregister('_hscad_rows')
        return
    schema = EMPTY_SCHEMAS.get(table_name, {'empty_json': 'VARCHAR'})
    columns = ', '.join(f'{name} {dtype}' for name, dtype in schema.items())
    con.execute(f'CREATE TABLE {table_name} ({columns})')


def _build_sql_reports(con: Any) -> dict[str, Any]:
    return {
        'file_count': _scalar(con, 'SELECT COUNT(*) FROM files'),
        'total_entities': _scalar(con, 'SELECT COALESCE(SUM(entity_count), 0) FROM files'),
        'entity_rows': _scalar(con, 'SELECT COUNT(*) FROM entities'),
        'area_count': _scalar(con, 'SELECT COUNT(*) FROM areas'),
        'text_count': _scalar(con, 'SELECT COUNT(*) FROM texts'),
        'graph_node_count': _scalar(con, 'SELECT COUNT(*) FROM graph_nodes'),
        'graph_edge_count': _scalar(con, 'SELECT COUNT(*) FROM graph_edges'),
        'low_confidence_cross_validation': _scalar(con, 'SELECT COUNT(*) FROM cross_validation_results WHERE confidence < 0.7'),
        'graph_audit_findings': _scalar(con, 'SELECT COUNT(*) FROM graph_audit_findings'),
        'layer_semantic_counts': _fetchall(con, 'SELECT predicted_semantic, COUNT(*) AS count FROM layers GROUP BY predicted_semantic ORDER BY count DESC'),
        'entity_type_counts': _fetchall(con, 'SELECT entity_type, COUNT(*) AS count FROM entities GROUP BY entity_type ORDER BY count DESC LIMIT 20'),
        'area_source_type_counts': _fetchall(con, 'SELECT source_type, COUNT(*) AS count FROM areas GROUP BY source_type ORDER BY count DESC'),
    }


def _detect_spatial_capability(db_path: Path) -> dict[str, Any]:
    try:
        import duckdb
        con = duckdb.connect(str(db_path))
        try:
            con.execute('SELECT 1')
            return {'status': 'not_loaded', 'reason': 'spatial extension not required by PR #9 initial export'}
        finally:
            con.close()
    except Exception as exc:
        return {'status': 'unknown', 'reason': str(exc)}


def _scalar(con: Any, sql: str) -> Any:
    try:
        return con.execute(sql).fetchone()[0]
    except Exception:
        return None


def _fetchall(con: Any, sql: str) -> list[dict[str, Any]]:
    try:
        cursor = con.execute(sql)
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception:
        return []


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _empty_result(base: Path, status: str, reason: str, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    return {'backend': DuckDBAnalyticsExporter.backend_id, 'status': status, 'reason': reason, 'workspace': str(base), 'duckdb_path': str(base / 'hscad_analysis.duckdb'), 'analytics_dir': str(base / 'analytics'), 'table_counts': {}, 'parquet_paths': {}, 'sql_reports': {}, 'spatial_capability': {'status': 'unavailable', 'reason': reason}, 'provenance': provenance or {}}


def _markdown(result: dict[str, Any]) -> str:
    lines = ['# DuckDB Export Report', '', f"- Backend: `{result.get('backend')}`", f"- Status: `{result.get('status')}`", f"- Reason: `{result.get('reason')}`", f"- DuckDB: `{result.get('duckdb_path')}`", f"- Analytics dir: `{result.get('analytics_dir')}`", '', '## Table Counts', '']
    for name in TABLE_ORDER:
        count = (result.get('table_counts') or {}).get(name, 0)
        lines.append(f'- `{name}`: `{count}`')
    lines.extend(['', '## SQL Reports', ''])
    for name, value in (result.get('sql_reports') or {}).items():
        lines.append(f'- `{name}`: `{value}`')
    lines.extend(['', '## Parquet Outputs', ''])
    for name, path in (result.get('parquet_paths') or {}).items():
        lines.append(f'- `{name}`: `{path}`')
    lines.extend(['', '## Spatial Capability', '', f"- `{result.get('spatial_capability')}`", ''])
    return '\n'.join(lines)


def _bbox_value(values: Any, index: int) -> float | None:
    if not isinstance(values, (list, tuple)) or len(values) <= index:
        return None
    try:
        return float(values[index])
    except Exception:
        return None
