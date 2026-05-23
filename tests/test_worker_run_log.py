from __future__ import annotations

import json
from pathlib import Path

from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.run_log import append_worker_run, build_worker_audit, artifact_provenance_summary


def test_append_worker_run_creates_runs_audit_and_jsonl(tmp_path: Path):
    artifact = tmp_path / 'artifact.json'
    artifact.write_text(json.dumps({'provenance': {'backend': 'test'}}), encoding='utf-8')
    worker_input = WorkerInput(worker_name='test_worker', task='run', workspace=str(tmp_path))
    worker_output = WorkerOutput.ok(
        worker_name='test_worker',
        backend='test_backend',
        artifacts=[str(artifact)],
        provenance={'backend': 'test_backend'},
    )
    append_worker_run(
        workspace=tmp_path,
        worker_input=worker_input,
        worker_output=worker_output,
        command=['python', '-m', 'worker'],
        duration_ms=12.3,
        returncode=0,
    )
    runs_path = tmp_path / 'WORKER_RUNS.json'
    audit_path = tmp_path / 'WORKER_AUDIT.json'
    jsonl_path = tmp_path / 'worker_logs' / 'test_worker.jsonl'
    assert runs_path.exists()
    assert audit_path.exists()
    assert jsonl_path.exists()
    runs = json.loads(runs_path.read_text(encoding='utf-8'))
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    assert runs['run_count'] == 1
    assert audit['run_count'] == 1
    assert audit['finding_count'] == 0


def test_worker_audit_flags_unavailable_and_missing_provenance():
    runs = [
        {
            'worker_name': 'planned_worker',
            'status': 'unavailable',
            'warnings': ['not implemented'],
            'provenance_present': False,
            'artifact_provenance': [],
        }
    ]
    audit = build_worker_audit(runs)
    types = {item['type'] for item in audit['findings']}
    assert 'worker_unavailable' in types
    assert 'worker_output_missing_provenance' in types


def test_artifact_provenance_summary_detects_missing_provenance(tmp_path: Path):
    with_prov = tmp_path / 'with.json'
    without_prov = tmp_path / 'without.json'
    with_prov.write_text(json.dumps({'provenance': {'x': 1}}), encoding='utf-8')
    without_prov.write_text(json.dumps({'x': 1}), encoding='utf-8')
    rows = artifact_provenance_summary([str(with_prov), str(without_prov), str(tmp_path / 'missing.json')])
    assert rows[0]['provenance_present'] is True
    assert rows[1]['provenance_present'] is False
    assert rows[2]['exists'] is False
