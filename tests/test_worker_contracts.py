from __future__ import annotations

from pathlib import Path

from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance
from src.workers.registry import WorkerRegistry


def test_worker_input_output_roundtrip(tmp_path: Path):
    worker_input = WorkerInput(
        worker_name='shapely_topology',
        task='run',
        workspace='outputs/sample',
        input_artifacts=['fileized/json'],
        options={'snap_tolerance': 0.001},
    )
    path = worker_input.write_json(tmp_path / 'input.json')
    loaded = WorkerInput.from_json_file(path)
    assert loaded.worker_name == 'shapely_topology'
    assert loaded.options['snap_tolerance'] == 0.001

    output = WorkerOutput.ok(
        worker_name='shapely_topology',
        backend='shapely_topology',
        artifacts=['SHAPELY_TOPOLOGY.json'],
    )
    assert output.status == 'ok'
    assert 'SHAPELY_TOPOLOGY.json' in output.artifacts


def test_worker_registry_loads_manifest():
    summary = WorkerRegistry('config/worker_manifest.json').summary()
    assert summary['worker_count'] >= 3
    assert 'topology' in summary['type_counts']
    spec = WorkerRegistry('config/worker_manifest.json').get('shapely_topology')
    assert spec is not None
    assert spec.env_manager == 'current_python'
    assert 'SHAPELY_TOPOLOGY.json' in spec.outputs


def test_build_provenance_contains_runtime_fields():
    provenance = build_provenance(
        workspace='outputs/sample',
        backend='test_backend',
        algorithm='unit_test',
        source_artifacts=['a.json'],
        worker_name='worker',
    )
    assert provenance['workspace'] == 'outputs/sample'
    assert provenance['backend'] == 'test_backend'
    assert provenance['runtime']['python']
