from __future__ import annotations

import sys
from pathlib import Path

from src.analytics.duckdb_export import write_duckdb_export
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'duckdb_export'
BACKEND = 'duckdb_export'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    fallback_provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='json_artifacts_to_duckdb_parquet',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    try:
        result = write_duckdb_export(workspace)
    except Exception as exc:
        return WorkerOutput.error(
            worker_name=WORKER_NAME,
            backend=BACKEND,
            message=str(exc),
            provenance=fallback_provenance,
        )
    provenance = result.get('provenance') or fallback_provenance
    status = str(result.get('status') or 'ok')
    if status == 'unavailable':
        return WorkerOutput.error(
            worker_name=WORKER_NAME,
            backend=BACKEND,
            message=f"not implemented: optional DuckDB backend unavailable ({result.get('reason') or 'duckdb unavailable'})",
            status='unavailable',
            provenance=provenance,
        )
    artifacts = [
        str(workspace / 'DUCKDB_EXPORT.json'),
        str(workspace / 'DUCKDB_EXPORT_REPORT.md'),
    ]
    duckdb_path = result.get('duckdb_path') or result.get('database')
    if duckdb_path:
        artifacts.append(str(duckdb_path))
    parquet_paths = result.get('parquet_paths') or result.get('parquet_outputs') or {}
    if isinstance(parquet_paths, dict):
        artifacts.extend(str(value) for value in parquet_paths.values())
    elif isinstance(parquet_paths, list):
        artifacts.extend(str(value) for value in parquet_paths)
    table_counts = result.get('table_counts') or {}
    sql_reports = result.get('sql_reports') or {}
    return WorkerOutput.ok(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        artifacts=artifacts,
        signals=[
            {
                'id': 'duckdb_analytics_export',
                'score': 1.0,
                'evidence': [f"table_count={len(table_counts)}", f"database={duckdb_path}"],
            }
        ],
        warnings=[],
        metrics={
            'table_counts': table_counts,
            'sql_reports': sql_reports,
            'spatial_capability': result.get('spatial_capability'),
        },
        provenance=provenance,
    )


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        output = WorkerOutput.error(
            worker_name=WORKER_NAME,
            backend=BACKEND,
            message='missing WorkerInput path argument',
        )
        print(output.to_json())
        return 2
    worker_input = WorkerInput.from_json_file(args[0])
    output = run_worker(worker_input)
    print(output.to_json())
    return 0 if output.status in {'ok', 'warning', 'unavailable'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
