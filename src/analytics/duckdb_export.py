from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


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
        if not available:
            result = _empty_result(base, 'unavailable', reason)
            report_path.write_text(_markdown(result), encoding='utf-8')
            return result

        import duckdb

        analytics_dir.mkdir(parents=True, exist_ok=True)
        tables = _load_workspace_tables(base)
        con = duckdb.connect(str(db_path))
        try:
            table_counts: dict[str, int] = {}
            parquet_paths: dict[str, str] = {}
            for table_name, rows in tables.items():
                _create_table(con, table_name, rows)
                table_counts[table_name] = len(rows)
                parquet_path = analytics_dir / f'{table_name}.parquet'
                if rows:
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


def _load_workspace_tables(base: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        'files': _rows_files(base),
        'layers': _rows_layers(base),
        'texts': _rows_texts(base),
        'areas': _rows_areas(base),
        'graph_nodes': _rows_graph_nodes(base),
        'graph_edges': _rows_graph_edges(base),
        'cross_validation_results': _rows_cross_validation(base),
        'graph_audit_findings': _rows_graph_audit(base),
    }


def _rows_files(base: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((base / 'fileized' / 'json').glob('*.json')):
        payload = _read_json(path)
        rows.append({
            'file_id': str(payload.get('file_id') or path.stem),
            'relative_path': str(payload.get('relative_path') or ''),
            'engine': str(payload.get('engine') or payload.get('metadata', {}).get('engine') or ''),
            'entity_count': len(payload.get('entities') or []),
            'text_count': len(payload.get('texts') or []),
            'source_json': str(path),
        })
    return rows


def _rows_layers(base: Path) -> list[dict[str, Any]]:
    path = base / 'LAYER_SEMANTICS.json'
    payload = _read_json(path)
    rows = []
    for layer in payload.get('layers') or []:
        rows.append({
            'layer': str(layer.get('layer') or ''),
            'predicted_semantic': str(layer.get('predicted_semantic') or layer.get('semantic') or ''),
            'confidence': float(layer.get('confidence') or 0.0),
            'counts_json': json.dumps(layer.get('counts') or {}, ensure_ascii=False),
            'evidence_json': json.dumps(layer.get('evidence') or [], ensure_ascii=False),
        })
    return rows


def _rows_texts(base: Path) -> list[dict[str, Any]]:
    path = base / 'TEXT_ROLE_INFERENCE.json'
    payload = _read_json(path)
    rows = []
    for role in payload.get('roles') or []:
        rows.append({
            'file_id': str(role.get('file_id') or ''),
            'handle': str(role.get('handle') or ''),
            'text': str(role.get('text') or ''),
            'role': str(role.get('role') or ''),
            'layer': str(role.get('layer') or ''),
            'confidence': float(role.get('confidence') or 0.0),
            'bbox_json': json.dumps(role.get('bbox') or [], ensure_ascii=False),
            'evidence_json': json.dumps(role.get('evidence') or [], ensure_ascii=False),
        })
    return rows


def _rows_areas(base: Path) -> list[dict[str, Any]]:
    path = base / 'AREA_ELEMENTS.json'
    payload = _read_json(path)
    rows = []
    for area in payload.get('areas') or []:
        rows.append({
            'file_id': str(area.get('file_id') or ''),
            'handle': str(area.get('handle') or ''),
            'label': str(area.get('label') or ''),
            'source_type': str(area.get('source_type') or ''),
            'area': float(area.get('area') or 0.0),
            'confidence': float(area.get('confidence') or 0.0),
            'bbox_json': json.dumps(area.get('bbox') or [], ensure_ascii=False),
            'evidence_json': json.dumps(area.get('evidence') or [], ensure_ascii=False),
        })
    return rows


def _rows_graph_nodes(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'SPATIAL_GRAPH.json')
    nodes = payload.get('nodes') or []
    rows = []
    if isinstance(nodes, dict):
        iterable = [dict(value, id=key) if isinstance(value, dict) else {'id': key} for key, value in nodes.items()]
    else:
        iterable = [node for node in nodes if isinstance(node, dict)]
    for node in iterable:
        rows.append({
            'node_id': str(node.get('id') or node.get('node_id') or ''),
            'kind': str(node.get('kind') or node.get('type') or ''),
            'payload_json': json.dumps(node, ensure_ascii=False),
        })
    return rows


def _rows_graph_edges(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'SPATIAL_GRAPH.json')
    rows = []
    for edge in payload.get('edges') or []:
        if not isinstance(edge, dict):
            continue
        rows.append({
            'source': str(edge.get('source') or edge.get('from') or edge.get('src') or ''),
            'target': str(edge.get('target') or edge.get('to') or edge.get('dst') or ''),
            'relation': str(edge.get('relation') or edge.get('type') or edge.get('label') or ''),
            'payload_json': json.dumps(edge, ensure_ascii=False),
        })
    return rows


def _rows_cross_validation(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'CROSS_VALIDATION.json')
    rows = []
    for item in payload.get('results') or []:
        if not isinstance(item, dict):
            continue
        rows.append({
            'target_type': str(item.get('target_type') or ''),
            'target_id': str(item.get('target_id') or ''),
            'agreement_score': float(item.get('agreement_score') or 0.0),
            'confidence': float(item.get('confidence') or 0.0),
            'warnings_json': json.dumps(item.get('warnings') or [], ensure_ascii=False),
            'signals_json': json.dumps(item.get('signals') or {}, ensure_ascii=False),
        })
    return rows


def _rows_graph_audit(base: Path) -> list[dict[str, Any]]:
    payload = _read_json(base / 'GRAPH_AUDIT.json')
    rows = []
    for finding in payload.get('findings') or []:
        if not isinstance(finding, dict):
            continue
        rows.append({
            'finding_type': str(finding.get('type') or ''),
            'severity': str(finding.get('severity') or ''),
            'node_id': str(finding.get('node_id') or ''),
            'message': str(finding.get('message') or ''),
            'evidence_json': json.dumps(finding.get('evidence') or [], ensure_ascii=False),
        })
    return rows


def _create_table(con: Any, table_name: str, rows: list[dict[str, Any]]) -> None:
    con.execute(f'DROP TABLE IF EXISTS {table_name}')
    if rows:
        con.execute(f'CREATE TABLE {table_name} AS SELECT * FROM rows')
        return
    # Empty fallback: keep a predictable table name with one JSON column.
    con.execute(f'CREATE TABLE {table_name} (empty_json VARCHAR)')


def _build_sql_reports(con: Any) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    reports['file_count'] = _scalar(con, 'SELECT COUNT(*) FROM files')
    reports['total_entities'] = _scalar(con, 'SELECT COALESCE(SUM(entity_count), 0) FROM files')
    reports['area_count'] = _scalar(con, 'SELECT COUNT(*) FROM areas')
    reports['text_count'] = _scalar(con, 'SELECT COUNT(*) FROM texts')
    reports['graph_node_count'] = _scalar(con, 'SELECT COUNT(*) FROM graph_nodes')
    reports['graph_edge_count'] = _scalar(con, 'SELECT COUNT(*) FROM graph_edges')
    reports['low_confidence_cross_validation'] = _scalar(con, 'SELECT COUNT(*) FROM cross_validation_results WHERE confidence < 0.7')
    reports['graph_audit_findings'] = _scalar(con, 'SELECT COUNT(*) FROM graph_audit_findings')
    reports['layer_semantic_counts'] = _fetchall(con, 'SELECT predicted_semantic, COUNT(*) AS count FROM layers GROUP BY predicted_semantic ORDER BY count DESC')
    reports['area_source_type_counts'] = _fetchall(con, 'SELECT source_type, COUNT(*) AS count FROM areas GROUP BY source_type ORDER BY count DESC')
    return reports


def _detect_spatial_capability(db_path: Path) -> dict[str, Any]:
    try:
        import duckdb
        con = duckdb.connect(str(db_path))
        try:
            con.execute('SELECT 1')
            return {'status': 'not_loaded', 'reason': 'spatial extension not required by PR #9 initial export'}
        finally:
            con.close()
    except Exception as exc:  # pragma: no cover
        return {'status': 'unknown', 'reason': str(exc)}


def _scalar(con: Any, sql: str) -> Any:
    try:
        return con.execute(sql).fetchone()[0]
    except Exception:
        return None


def _fetchall(con: Any, sql: str) -> list[dict[str, Any]]:
    try:
        columns = [item[0] for item in con.execute(sql).description]
        return [dict(zip(columns, row)) for row in con.fetchall()]
    except Exception:
        return []


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _empty_result(base: Path, status: str, reason: str) -> dict[str, Any]:
    return {
        'backend': DuckDBAnalyticsExporter.backend_id,
        'status': status,
        'reason': reason,
        'workspace': str(base),
        'duckdb_path': str(base / 'hscad_analysis.duckdb'),
        'analytics_dir': str(base / 'analytics'),
        'table_counts': {},
        'parquet_paths': {},
        'sql_reports': {},
        'spatial_capability': {'status': 'unavailable', 'reason': reason},
    }


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        '# DuckDB Export Report',
        '',
        f"- Backend: `{result.get('backend')}`",
        f"- Status: `{result.get('status')}`",
        f"- Reason: `{result.get('reason')}`",
        f"- DuckDB: `{result.get('duckdb_path')}`",
        f"- Analytics dir: `{result.get('analytics_dir')}`",
        '',
        '## Table Counts',
        '',
    ]
    for name, count in (result.get('table_counts') or {}).items():
        lines.append(f'- `{name}`: `{count}`')
    lines.extend(['', '## SQL Reports', ''])
    for name, value in (result.get('sql_reports') or {}).items():
        lines.append(f'- `{name}`: `{value}`')
    lines.append('')
    return '\n'.join(lines)
