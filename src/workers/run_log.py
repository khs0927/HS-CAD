from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.registry import WorkerSpec


RUNS_FILENAME = 'WORKER_RUNS.json'
AUDIT_FILENAME = 'WORKER_AUDIT.json'
LOG_DIRNAME = 'worker_logs'


def append_worker_run(
    *,
    workspace: str | Path,
    worker_input: WorkerInput,
    worker_output: WorkerOutput,
    command: list[str] | None = None,
    duration_ms: float | None = None,
    returncode: int | None = None,
) -> dict[str, Any]:
    base = Path(workspace)
    base.mkdir(parents=True, exist_ok=True)
    run = worker_run_record(
        worker_input=worker_input,
        worker_output=worker_output,
        command=command,
        duration_ms=duration_ms,
        returncode=returncode,
    )
    runs_path = base / RUNS_FILENAME
    runs = _load_list(runs_path)
    runs.append(run)
    runs_path.write_text(json.dumps({'run_count': len(runs), 'runs': runs}, ensure_ascii=False, indent=2), encoding='utf-8')
    _append_jsonl(base / LOG_DIRNAME / f'{worker_input.worker_name}.jsonl', run)
    audit = build_worker_audit(runs)
    (base / AUDIT_FILENAME).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    return run


def worker_run_record(
    *,
    worker_input: WorkerInput,
    worker_output: WorkerOutput,
    command: list[str] | None = None,
    duration_ms: float | None = None,
    returncode: int | None = None,
) -> dict[str, Any]:
    return {
        'run_id': f"{worker_input.worker_name}:{datetime.now(timezone.utc).isoformat()}",
        'created_at': datetime.now(timezone.utc).isoformat(),
        'worker_name': worker_input.worker_name,
        'task': worker_input.task,
        'workspace': worker_input.workspace,
        'status': worker_output.status,
        'backend': worker_output.backend,
        'artifacts': worker_output.artifacts,
        'warning_count': len(worker_output.warnings),
        'warnings': worker_output.warnings,
        'metrics': worker_output.metrics,
        'signals_count': len(worker_output.signals),
        'command': command or [],
        'duration_ms': round(duration_ms, 3) if duration_ms is not None else None,
        'returncode': returncode,
        'provenance_present': bool(worker_output.provenance),
        'artifact_provenance': artifact_provenance_summary(worker_output.artifacts),
    }


def build_worker_audit(runs: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    worker_counts: dict[str, int] = {}
    findings: list[dict[str, Any]] = []
    for run in runs:
        status = str(run.get('status') or 'unknown')
        worker = str(run.get('worker_name') or 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
        worker_counts[worker] = worker_counts.get(worker, 0) + 1
        if status in {'error', 'timeout'}:
            findings.append({
                'type': f'worker_{status}',
                'severity': 'high',
                'worker_name': worker,
                'message': f'Worker finished with status={status}',
                'warnings': run.get('warnings') or [],
            })
        elif status == 'unavailable':
            findings.append({
                'type': 'worker_unavailable',
                'severity': 'medium',
                'worker_name': worker,
                'message': 'Worker is unavailable or planned but not implemented.',
                'warnings': run.get('warnings') or [],
            })
        if not run.get('provenance_present'):
            findings.append({
                'type': 'worker_output_missing_provenance',
                'severity': 'medium',
                'worker_name': worker,
                'message': 'WorkerOutput did not include provenance.',
            })
        for item in run.get('artifact_provenance') or []:
            if item.get('exists') and not item.get('provenance_present'):
                findings.append({
                    'type': 'artifact_missing_provenance',
                    'severity': 'medium',
                    'worker_name': worker,
                    'artifact': item.get('path'),
                    'message': 'Worker artifact exists but does not include top-level provenance.',
                })
    return {
        'run_count': len(runs),
        'status_counts': status_counts,
        'worker_counts': worker_counts,
        'finding_count': len(findings),
        'findings': findings,
    }


def artifact_provenance_summary(artifacts: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in artifacts:
        path = Path(artifact)
        row = {'path': artifact, 'exists': path.exists(), 'provenance_present': False}
        if path.exists() and path.suffix.lower() == '.json':
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
                row['provenance_present'] = bool(payload.get('provenance'))
            except Exception as exc:  # pragma: no cover
                row['error'] = str(exc)
        rows.append(row)
    return rows


def planned_worker_output(worker_name: str, spec: WorkerSpec) -> WorkerOutput:
    return WorkerOutput.error(
        worker_name=worker_name,
        backend=worker_name,
        message=f'worker is not implemented yet: {spec.status}',
        status='unavailable',
    )


def _load_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, list):
        return payload
    return list(payload.get('runs') or [])


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + '\n')
