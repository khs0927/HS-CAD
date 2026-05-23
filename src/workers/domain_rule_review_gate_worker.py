from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.domain_rules.review_gate_builder import build_review_gate_package
from src.domain_rules.review_gate_report import render_review_gate_markdown
from src.reports.json_exporter import export_json


def load_command_plan(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'Command plan must be a JSON object: {path}')
    for key in ('task', 'status', 'dry_run_steps', 'review_table', 'execution_queue_candidate'):
        if key not in data:
            raise ValueError(f'Missing command plan key {key!r}: {path}')
    return data


def run_domain_rule_review_gate_worker(
    command_plan_json: str | Path,
    *,
    out_dir: str | Path = 'outputs/domain_rule_review_gate',
) -> dict[str, Any]:
    command_plan = load_command_plan(command_plan_json)
    package = build_review_gate_package(command_plan, source=str(command_plan_json))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    gate_json = out / 'DOMAIN_RULE_REVIEW_GATE.json'
    gate_md = out / 'DOMAIN_RULE_REVIEW_GATE.md'
    signoff_json = out / 'DOMAIN_RULE_SIGNOFF_MANIFEST.json'

    export_json(package.to_dict(), gate_json)
    gate_md.write_text(render_review_gate_markdown(package), encoding='utf-8')
    export_json(
        {
            'status': package.status,
            'source_command_plan': package.source_command_plan,
            'signoff_required': package.signoff_required,
            'allowed_next_steps': package.allowed_next_steps,
            'blocked_reasons': package.blocked_reasons,
            'operator_approved': False,
            'notes': 'This manifest is a review artifact only. It does not authorize execution by itself.',
        },
        signoff_json,
    )
    return {
        'command_plan_json': str(command_plan_json),
        'out_dir': str(out),
        'gate_json': str(gate_json),
        'gate_report': str(gate_md),
        'signoff_manifest': str(signoff_json),
        'status': package.status,
        'check_count': len(package.checks),
        'blocked_count': len(package.blocked_reasons),
    }
