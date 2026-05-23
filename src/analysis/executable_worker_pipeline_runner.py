from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md


def execute_worker_pipeline_plan(
    workspace: str | Path,
    *,
    plan_path: str | Path | None = None,
    dry_run: bool = True,
    stop_on_error: bool = True,
    timeout_sec: int = 1800,
) -> dict[str, Any]:
    """Execute or dry-run WORKER_PIPELINE_PLAN.json.

    Default is dry-run for safety. Set dry_run=False only in a controlled local environment.
    This runner intentionally writes stdout/stderr logs under worker_pipeline_logs.
    """
    base = Path(workspace)
    plan_file = Path(plan_path) if plan_path else base / 'WORKER_PIPELINE_PLAN.json'
    plan = read_json(plan_file)
    steps = list(plan.get('steps') or [])
    log_dir = base / 'worker_pipeline_logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for step in steps:
        worker_name = str(step.get('worker_name') or f'step_{len(results)+1}')
        command = str(step.get('command') or '').strip()
        started = time.time()
        row: dict[str, Any] = {
            'order': step.get('order'),
            'worker_name': worker_name,
            'command': command,
            'dry_run': dry_run,
            'status': 'planned',
            'returncode': None,
            'duration_sec': 0.0,
            'stdout_log': str(log_dir / f'{worker_name}.stdout.log'),
            'stderr_log': str(log_dir / f'{worker_name}.stderr.log'),
        }
        if dry_run:
            row['status'] = 'dry_run'
        elif not command:
            row['status'] = 'error'
            row['error'] = 'missing command'
        else:
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    capture_output=True,
                    timeout=timeout_sec,
                )
                Path(row['stdout_log']).write_text(result.stdout or '', encoding='utf-8')
                Path(row['stderr_log']).write_text(result.stderr or '', encoding='utf-8')
                row['returncode'] = result.returncode
                row['status'] = 'ok' if result.returncode == 0 else 'error'
            except subprocess.TimeoutExpired as exc:
                row['status'] = 'timeout'
                row['error'] = str(exc)
            except Exception as exc:  # pragma: no cover
                row['status'] = 'error'
                row['error'] = str(exc)
        row['duration_sec'] = round(time.time() - started, 6)
        results.append(row)
        if row['status'] in {'error', 'timeout'} and stop_on_error:
            break
    payload = {
        'backend': 'executable_worker_pipeline_runner',
        'schema_version': '0.1',
        'parameters': {
            'dry_run': dry_run,
            'stop_on_error': stop_on_error,
            'timeout_sec': timeout_sec,
            'plan_path': str(plan_file),
        },
        'summary': {
            'step_count': len(steps),
            'executed_or_planned_count': len(results),
            'ok_count': sum(1 for r in results if r['status'] == 'ok'),
            'dry_run_count': sum(1 for r in results if r['status'] == 'dry_run'),
            'error_count': sum(1 for r in results if r['status'] in {'error', 'timeout'}),
        },
        'results': results,
        'warnings': ['default dry_run=true; actual execution must be explicitly enabled'] if dry_run else [],
        'todo': [
            'Add non-shell argv execution mode for safer Windows path handling.',
            'Add resume-from-step and retry support.',
            'Add generated-artifact diff after each worker step.',
            'Add CI-friendly nonzero status emission after validation rules mature.',
        ],
    }
    return write_json_and_md(base, 'EXECUTABLE_WORKER_PIPELINE_RUN', payload, _markdown(payload))


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Executable Worker Pipeline Run',
        '',
        f"- Steps: `{s.get('step_count')}`",
        f"- Planned/executed: `{s.get('executed_or_planned_count')}`",
        f"- OK: `{s.get('ok_count')}`",
        f"- Dry-run: `{s.get('dry_run_count')}`",
        f"- Errors: `{s.get('error_count')}`",
        '',
        '| Order | Worker | Status | Return code | Duration |',
        '|---:|---|---|---:|---:|',
    ]
    for row in payload.get('results') or []:
        lines.append(f"| {row.get('order')} | {row.get('worker_name')} | {row.get('status')} | {row.get('returncode')} | {row.get('duration_sec')} |")
    lines.append('')
    return '\n'.join(lines)
