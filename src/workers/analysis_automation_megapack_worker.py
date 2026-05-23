from __future__ import annotations

import sys
from pathlib import Path

from src.analysis.drawing_set_indexer import build_drawing_set_index
from src.analysis.executable_worker_pipeline_runner import execute_worker_pipeline_plan
from src.analysis.html_validation_dashboard import build_html_validation_dashboard
from src.analysis.strtree_spatial_join_backend import run_strtree_spatial_join
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'analysis_automation_megapack'
BACKEND = 'analysis_automation_megapack'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='analysis_automation_megapack_v0',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    artifacts: list[str] = []
    warnings: list[str] = []
    metrics = {}
    try:
        pipeline = execute_worker_pipeline_plan(workspace, dry_run=bool(worker_input.options.get('dry_run', True)))
        strtree = run_strtree_spatial_join(workspace)
        drawing_set = build_drawing_set_index(workspace)
        dashboard = build_html_validation_dashboard(workspace)
        artifacts.extend([
            str(workspace / 'EXECUTABLE_WORKER_PIPELINE_RUN.json'),
            str(workspace / 'EXECUTABLE_WORKER_PIPELINE_RUN.md'),
            str(workspace / 'STRTREE_SPATIAL_JOIN.json'),
            str(workspace / 'STRTREE_SPATIAL_JOIN.md'),
            str(workspace / 'DRAWING_SET_INDEX.json'),
            str(workspace / 'DRAWING_SET_INDEX.md'),
            str(workspace / 'HTML_VALIDATION_DASHBOARD.json'),
            str(workspace / 'HTML_VALIDATION_DASHBOARD.md'),
            str(workspace / 'VALIDATION_DASHBOARD.html'),
        ])
        metrics.update({
            'pipeline_error_count': (pipeline.get('summary') or {}).get('error_count', 0),
            'pipeline_dry_run_count': (pipeline.get('summary') or {}).get('dry_run_count', 0),
            'strtree_join_count': (strtree.get('summary') or {}).get('join_count', 0),
            'drawing_set_file_count': (drawing_set.get('summary') or {}).get('file_count', 0),
            'dashboard_section_count': (dashboard.get('summary') or {}).get('section_count', 0),
        })
        warnings.extend(pipeline.get('warnings') or [])
        warnings.extend(strtree.get('warnings') or [])
        warnings.extend(drawing_set.get('warnings') or [])
        warnings.extend(dashboard.get('warnings') or [])
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=provenance)

    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='warning',
        artifacts=artifacts,
        signals=[
            {
                'id': 'analysis_automation_megapack',
                'score': 0.6,
                'evidence': ['automation artifacts generated', 'pipeline execution defaults to dry-run'],
            }
        ],
        warnings=warnings,
        metrics=metrics,
        provenance=provenance,
    )


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        output = WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message='missing WorkerInput path argument')
        print(output.to_json())
        return 2
    worker_input = WorkerInput.from_json_file(args[0])
    output = run_worker(worker_input)
    print(output.to_json())
    return 0 if output.status in {'ok', 'warning', 'unavailable'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
