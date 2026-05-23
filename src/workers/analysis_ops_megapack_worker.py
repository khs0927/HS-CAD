from __future__ import annotations

import sys
from pathlib import Path

from src.analysis.batch_validation_summary_collector import collect_batch_validation_summary
from src.analysis.drawing_sheet_classifier import classify_drawing_sheets
from src.analysis.layer_profile_sampler import sample_layer_profiles
from src.analysis.quality_dashboard_manifest import build_quality_dashboard_manifest
from src.analysis.worker_pipeline_runner import build_worker_pipeline_plan
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'analysis_ops_megapack'
BACKEND = 'analysis_ops_megapack'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='analysis_ops_megapack_v0',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    artifacts: list[str] = []
    warnings: list[str] = []
    metrics = {}
    try:
        layer = sample_layer_profiles(workspace)
        sheet = classify_drawing_sheets(workspace)
        validation = collect_batch_validation_summary(workspace)
        dashboard = build_quality_dashboard_manifest(workspace)
        pipeline = build_worker_pipeline_plan(workspace)
        artifacts.extend([
            str(workspace / 'LAYER_PROFILE_SAMPLE.json'),
            str(workspace / 'LAYER_PROFILE_SAMPLE.md'),
            str(workspace / 'DRAWING_SHEET_CLASSIFIER.json'),
            str(workspace / 'DRAWING_SHEET_CLASSIFIER.md'),
            str(workspace / 'BATCH_VALIDATION_SUMMARY.json'),
            str(workspace / 'BATCH_VALIDATION_SUMMARY.md'),
            str(workspace / 'VALIDATION_SUMMARY.md'),
            str(workspace / 'QUALITY_DASHBOARD_MANIFEST.json'),
            str(workspace / 'QUALITY_DASHBOARD_MANIFEST.md'),
            str(workspace / 'WORKER_PIPELINE_PLAN.json'),
            str(workspace / 'WORKER_PIPELINE_PLAN.md'),
        ])
        metrics.update({
            'layer_count': (layer.get('summary') or {}).get('layer_count', 0),
            'sheet_discipline': (sheet.get('summary') or {}).get('discipline'),
            'sheet_type': (sheet.get('summary') or {}).get('sheet_type'),
            'missing_artifact_count': (validation.get('summary') or {}).get('missing_artifact_count', 0),
            'dashboard_ready_section_count': (dashboard.get('summary') or {}).get('ready_section_count', 0),
            'pipeline_step_count': (pipeline.get('summary') or {}).get('step_count', 0),
        })
        warnings.extend(layer.get('warnings') or [])
        warnings.extend(sheet.get('warnings') or [])
        warnings.extend(validation.get('warnings') or [])
        warnings.extend(dashboard.get('warnings') or [])
        warnings.extend(pipeline.get('warnings') or [])
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=provenance)

    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='warning',
        artifacts=artifacts,
        signals=[
            {
                'id': 'analysis_ops_megapack',
                'score': 0.6,
                'evidence': ['ops artifacts generated', 'validation summary collected'],
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
