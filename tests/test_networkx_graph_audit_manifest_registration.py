from __future__ import annotations

from pathlib import Path

from src.workers.contracts import WorkerInput
from src.workers.registry import WorkerRegistry
from src.workers.runner import WorkerRunner


def test_networkx_graph_audit_registered_with_review_only_safety_metadata():
    registry = WorkerRegistry('config/worker_manifest.json')
    spec = registry.get('networkx_graph_audit')

    assert spec is not None
    assert spec.path == 'src.workers.networkx_graph_audit_worker'


def test_networkx_graph_audit_worker_dry_run_from_manifest(tmp_path: Path):
    runner = WorkerRunner(WorkerRegistry('config/worker_manifest.json'))
    plan = runner.dry_run(
        'networkx_graph_audit',
        WorkerInput(
            worker_name='networkx_graph_audit',
            task='dry-run-registration-check',
            workspace=str(tmp_path),
            input_artifacts=['SPATIAL_GRAPH.json'],
            options={'agent2_small_manifest_pr': True},
        ),
    )

    assert plan['worker_name'] == 'networkx_graph_audit'
    assert plan['status'] == 'planned'
    assert plan['module'] == 'src.workers.networkx_graph_audit_worker'
    assert plan['input_artifact_count'] == 1
