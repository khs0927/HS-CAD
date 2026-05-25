from __future__ import annotations

# pyrefly: ignore [missing-import]
from src.workers.contracts import WorkerInput
from src.workers.registry import WorkerRegistry
from src.workers.runner import WorkerRunner


import pytest

@pytest.mark.skip(reason="Worker was renamed/removed in PR82 manifest")
def test_worker_runner_dry_run_for_shapely_worker():
    runner = WorkerRunner(WorkerRegistry('config/worker_manifest.json'))
    worker_input = WorkerInput(
        worker_name='analysis_export_megapack',
        task='run',
        workspace='outputs/sample',
        input_artifacts=['fileized/json'],
    )
    plan = runner.dry_run('analysis_export_megapack', worker_input)
    assert plan['worker_name'] == 'analysis_export_megapack'
    assert plan['status'] == 'planned'
    assert plan['module'] == 'src.workers.analysis_export_megapack_worker'


def test_worker_runner_returns_unavailable_for_missing_worker():
    runner = WorkerRunner(WorkerRegistry('config/worker_manifest.json'))
    output = runner.run('missing_worker', WorkerInput(worker_name='missing_worker', task='run', workspace='outputs/sample'))
    assert output.status == 'unavailable'
    assert 'worker is not registered in manifest' in output.warnings[0]


def test_worker_runner_returns_unavailable_for_planned_worker():
    runner = WorkerRunner(WorkerRegistry('config/worker_manifest.json'))
    output = runner.run('bim_projection', WorkerInput(worker_name='bim_projection', task='run', workspace='outputs/sample'))
    assert output.status == 'unavailable'
    assert 'worker is not registered in manifest' in output.warnings[0]

