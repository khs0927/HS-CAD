from __future__ import annotations

import pytest

import importlib.util
import json
from pathlib import Path

from src.analytics.duckdb_export import DuckDBAnalyticsExporter, _load_workspace_tables, write_duckdb_export
from src.workers.contracts import WorkerInput
from src.workers.registry import WorkerRegistry
from src.workers.runner import WorkerRunner


def _sample_workspace(tmp_path: Path) -> Path:
    json_dir = tmp_path / 'fileized' / 'json'
    json_dir.mkdir(parents=True)
    (json_dir / 'sample.json').write_text(json.dumps({
        'file_id': 'sample',
        'relative_path': 'sample.dxf',
        'engine': 'ezdxf',
        'entities': [
            {'handle': 'L1', 'entity_type': 'LINE', 'layer': 'WALL', 'bbox': [0, 0, 10, 0]},
            {'handle': 'T1', 'entity_type': 'TEXT', 'layer': 'TEXT', 'text': '사무실', 'insert': [5, 5]},
        ],
    }, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'AREA_ELEMENTS.json').write_text(json.dumps({'areas': [
        {'file_id': 'sample', 'handle': 'A1', 'label': '사무실', 'source_type': 'closed_polyline', 'area': 100, 'confidence': 0.9, 'bbox': [0, 0, 10, 10]}
    ]}, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'SPATIAL_GRAPH.json').write_text(json.dumps({
        'nodes': [{'id': 'file:sample', 'kind': 'file'}, {'id': 'area:A1', 'kind': 'area'}],
        'edges': [{'source': 'file:sample', 'target': 'area:A1', 'relation': 'HAS_AREA'}],
    }, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'CROSS_VALIDATION.json').write_text(json.dumps({'results': [
        {'target_type': 'area_element', 'target_id': 'area:sample:A1', 'agreement_score': 0.9, 'confidence': 0.8, 'warnings': [], 'signals': {}}
    ]}, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'GRAPH_AUDIT.json').write_text(json.dumps({'findings': [
        {'type': 'unlabeled_area', 'severity': 'medium', 'node_id': 'area:A1', 'message': 'missing label'}
    ]}, ensure_ascii=False), encoding='utf-8')
    return tmp_path


def test_load_workspace_tables_includes_entities_and_artifacts(tmp_path: Path):
    workspace = _sample_workspace(tmp_path)
    rows = _load_workspace_tables(workspace)
    assert len(rows['files']) == 1
    assert len(rows['entities']) == 2
    assert rows['entities'][0]['payload_json']
    assert len(rows['texts']) == 1
    assert len(rows['areas']) == 1
    assert len(rows['graph_nodes']) == 2
    assert len(rows['graph_edges']) == 1
    assert len(rows['cross_validation_results']) == 1
    assert len(rows['graph_audit_findings']) == 1


def test_duckdb_export_never_crashes_without_duckdb(tmp_path: Path):
    workspace = _sample_workspace(tmp_path)
    result = DuckDBAnalyticsExporter().export_workspace(workspace)
    assert result['status'] in {'ok', 'unavailable'}
    assert 'provenance' in result
    assert (workspace / 'DUCKDB_EXPORT_REPORT.md').exists()


def test_duckdb_export_creates_database_parquet_and_provenance_when_available(tmp_path: Path):
    if importlib.util.find_spec('duckdb') is None:
        return
    workspace = _sample_workspace(tmp_path)
    result = write_duckdb_export(workspace)
    assert result['status'] == 'ok'
    assert (workspace / 'hscad_analysis.duckdb').exists()
    assert (workspace / 'DUCKDB_EXPORT.json').exists()
    assert result['table_counts']['files'] == 1
    assert result['table_counts']['entities'] == 2
    assert result['sql_reports']['entity_rows'] == 2
    assert result['provenance']['backend'] == 'duckdb_export'
    for table_name, parquet_path in result['parquet_paths'].items():
        assert table_name
        assert Path(parquet_path).exists()


def test_duckdb_worker_registered_and_plans_command():
    runner = WorkerRunner(WorkerRegistry('config/worker_manifest.json'))
    worker_input = WorkerInput(worker_name='duckdb_export', task='run', workspace='outputs/sample')
    plan = runner.dry_run('duckdb_export', worker_input)
    assert plan['worker_name'] == 'duckdb_export'
    assert plan['module'] == 'src.workers.duckdb_export_worker'
