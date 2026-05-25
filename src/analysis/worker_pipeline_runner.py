from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import write_json_and_md

DEFAULT_ANALYSIS_PIPELINE = [
    'analysis_core_megapack',
    'analysis_graph_megapack',
    'analysis_advanced_megapack',
    'analysis_ops_megapack',
]


def build_worker_pipeline_plan(workspace: str | Path, *, include_self: bool = False) -> dict[str, Any]:
    """Create an ordered analysis pipeline plan.

    This does not execute subprocesses yet. It creates a stable plan artifact that a future CLI can consume.
    """
    base = Path(workspace)
    steps = []
    pipeline = list(DEFAULT_ANALYSIS_PIPELINE)
    if not include_self:
        pipeline = [name for name in pipeline if name != 'analysis_ops_megapack']
    for idx, worker_name in enumerate(pipeline, start=1):
        steps.append({
            'order': idx,
            'worker_name': worker_name,
            'command': f'python -X utf8 -m src.main hscad-worker-run {worker_name} --workspace {base}',
            'status': 'planned',
            'continue_on_warning': True,
            'continue_on_error': False,
        })
    payload = {
        'backend': 'worker_pipeline_runner',
        'schema_version': '0.1',
        'summary': {
            'step_count': len(steps),
            'workspace': str(base),
        },
        'steps': steps,
        'todo': [
            'Add CLI command to execute this plan with subprocess and stop/continue policy.',
            'Record per-step runtime, return code, stdout/stderr path, and generated artifacts.',
            'Add resume-from-step and retry support.',
            'Add YAML/JSON custom pipeline definitions.',
        ],
        'warnings': ['pipeline plan only; execution is not implemented here'],
    }
    return write_json_and_md(base, 'WORKER_PIPELINE_PLAN', payload, _markdown(payload))


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Worker Pipeline Plan',
        '',
        f"- Workspace: `{s.get('workspace')}`",
        f"- Step count: `{s.get('step_count')}`",
        '',
        '| Order | Worker | Command |',
        '|---:|---|---|',
    ]
    for row in payload.get('steps') or []:
        lines.append(f"| {row.get('order')} | {row.get('worker_name')} | `{row.get('command')}` |")
    lines.append('')
    return '\n'.join(lines)
