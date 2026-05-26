from __future__ import annotations

import importlib
import json
from pathlib import Path

from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.registry import WorkerRegistry
from src.workers.runner import WorkerRunner


WORKER_CANDIDATES = {
    'pdf_raster': 'src.workers.pdf_raster_worker',
    'ocr_text_region': 'src.workers.ocr_text_region_worker',
    'ocr_vector_text_match': 'src.workers.ocr_vector_text_match_worker',
    'ocr_cad_text_match': 'src.workers.ocr_cad_text_match_worker',
    'text_evidence_fusion': 'src.workers.text_evidence_fusion_worker',
    'text_review_queue': 'src.workers.text_review_queue_worker',
    'text_corrections_export': 'src.workers.text_corrections_export_worker',
    'text_calibration_report': 'src.workers.text_calibration_report_worker',
    'text_weight_suggestions': 'src.workers.text_weight_suggestions_worker',
    'networkx_graph_audit': 'src.workers.networkx_graph_audit_worker',
    'duckdb_export': 'src.workers.duckdb_export_worker',
}

CLI_CANDIDATES = [
    'src.app.analysis_shortcut_cli',
    'src.app.cad_platforms_cli',
    'src.app.cross_validate_cli',
    'src.app.fusion_matrix_cli',
    'src.app.layer_analysis_cli',
    'src.app.layer_audit_cli',
    'src.app.open_backends_cli',
    'src.app.shapely_area_match_cli',
    'src.app.shapely_topology_audit_cli',
    'src.app.shapely_topology_cli',
    'src.app.spatial_cli',
    'src.app.spatial_graph_cli',
    'src.app.text_roles_cli',
    'src.app.worker_cli',
]


def test_agent2_worker_candidate_modules_import_and_expose_run_worker():
    missing: list[str] = []
    for worker_name, module_name in WORKER_CANDIDATES.items():
        module = importlib.import_module(module_name)
        if getattr(module, 'run_worker', None) is None:
            missing.append(worker_name)
    assert not missing


def test_agent2_cli_candidate_modules_import_without_entrypoint_registration():
    failed: list[str] = []
    for module_name in CLI_CANDIDATES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - assertion prints exact failures
            failed.append(f'{module_name}: {type(exc).__name__}: {exc}')
    assert not failed


def test_agent2_worker_runner_uses_temp_manifest_without_touching_real_manifest(tmp_path: Path):
    manifest = tmp_path / 'candidate_worker_manifest.json'
    manifest.write_text(
        json.dumps(
            {
                'workers': {
                    name: {
                        'path': module,
                        'description': 'Agent 2 candidate validation only',
                    }
                    for name, module in WORKER_CANDIDATES.items()
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    registry = WorkerRegistry(manifest)
    runner = WorkerRunner(registry)
    assert registry.names() == sorted(WORKER_CANDIDATES)

    for worker_name in WORKER_CANDIDATES:
        planned = runner.dry_run(
            worker_name,
            WorkerInput(
                worker_name=worker_name,
                task='dry-run-contract-check',
                workspace=str(tmp_path / worker_name),
                input_artifacts=[],
                options={'agent2_validation': True},
            ),
        )
        assert planned['status'] == 'planned'
        assert planned['worker_name'] == worker_name
        assert planned['module'] == WORKER_CANDIDATES[worker_name]


def test_agent2_review_only_workers_return_worker_output_or_safe_error(tmp_path: Path):
    safe_run_workers = {
        'ocr_text_region',
        'networkx_graph_audit',
    }
    for worker_name in sorted(safe_run_workers):
        module = importlib.import_module(WORKER_CANDIDATES[worker_name])
        output = module.run_worker(
            WorkerInput(
                worker_name=worker_name,
                task='review-only-empty-workspace-check',
                workspace=str(tmp_path / worker_name),
                input_artifacts=[],
                options={'agent2_validation': True},
            )
        )
        assert isinstance(output, WorkerOutput)
        assert output.worker_name == worker_name
        assert output.status in {'ok', 'warning', 'unavailable', 'error'}
        assert output.status != 'error' or output.error


def test_agent2_does_not_require_real_manifest_or_main_registration():
    assert Path('config/worker_manifest.json').exists()
    assert Path('src/main.py').exists()
    assert not Path('outputs/agent2_candidate_validation_result.md').exists()
