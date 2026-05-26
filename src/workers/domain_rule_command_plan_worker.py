from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.domain_rules.command_plan_builder import build_command_plan
from src.domain_rules.command_plan_report import render_command_plan_markdown
from src.reports.json_exporter import export_json


def load_decision_package(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'Decision package must be a JSON object: {path}')
    for key in ('task', 'status', 'decisions', 'system_prompt'):
        if key not in data:
            raise ValueError(f'Missing decision package key {key!r}: {path}')
    return data


def run_domain_rule_command_plan_worker(
    decision_package_json: str | Path,
    *,
    out_dir: str | Path = 'outputs/domain_rule_command_plan',
) -> dict[str, Any]:
    decision_package = load_decision_package(decision_package_json)
    plan = build_command_plan(decision_package, source=str(decision_package_json))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    plan_json = out / 'DOMAIN_RULE_COMMAND_PLAN.json'
    report_md = out / 'DOMAIN_RULE_COMMAND_PLAN.md'
    review_table_json = out / 'DOMAIN_RULE_REVIEW_TABLE.json'
    queue_json = out / 'DOMAIN_RULE_EXECUTION_QUEUE_CANDIDATE.json'

    export_json(plan.to_dict(), plan_json)
    export_json(plan.review_table, review_table_json)
    export_json(plan.execution_queue_candidate.to_dict(), queue_json)
    report_md.write_text(render_command_plan_markdown(plan), encoding='utf-8')

    return {
        'decision_package_json': str(decision_package_json),
        'out_dir': str(out),
        'plan_json': str(plan_json),
        'report': str(report_md),
        'review_table': str(review_table_json),
        'execution_queue_candidate': str(queue_json),
        'status': plan.status,
        'dry_run_step_count': len(plan.dry_run_steps),
        'queue_step_count': len(plan.execution_queue_candidate.steps),
    }
