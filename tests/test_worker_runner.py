from __future__ import annotations

from src.workers.contracts import WorkerInput
from src.workers.registry import WorkerRegistry
from src.workers.runner import WorkerRunner


def test_worker_runner_dry_run_for_shapely_worker():
    runner = WorkerRunner(WorkerRegistry('config/worker_manifest.json'))
    worker_input = WorkerInput(
        worker_name='shapely_topology',
        task='run',
        workspace='outputs/sample',
        input_artifacts=['fileized/json'],
    )
    plan = runner.dry_run('shapely_topology', worker_input)
    assert plan['worker']['name'] == 'shapely_topology'
    assert '-m' in plan['command']
    assert 'src.workers.shapely_topology_worker' in plan['command']


def test_worker_runner_returns_unavailable_for_missing_worker():
    runner = WorkerRunner(WorkerRegistry('config/worker_manifest.json'))
    output = runner.run('missing_worker', WorkerInput(worker_name='missing_worker', task='run', workspace='outputs/sample'))
    assert output.status == 'unavailable'
    assert output.warnings


def test_worker_runner_returns_unavailable_for_planned_worker():
    runner = WorkerRunner(WorkerRegistry('config/worker_manifest.json'))
    output = runner.run('bim_projection', WorkerInput(worker_name='bim_projection', task='run', workspace='outputs/sample'))
    assert output.status == 'unavailable'
    assert 'not implemented' in output.warnings[0]
