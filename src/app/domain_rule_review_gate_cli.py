from __future__ import annotations

import typer

from src.app.cli import app
from src.app.logger import console
from src.workers.domain_rule_review_gate_worker import run_domain_rule_review_gate_worker


@app.command('domain-rule-review-gate')
def domain_rule_review_gate(
    command_plan_json: str = typer.Option(..., help='DOMAIN_RULE_COMMAND_PLAN.json path'),
    out_dir: str = typer.Option('outputs/domain_rule_review_gate', help='Output directory'),
):
    result = run_domain_rule_review_gate_worker(command_plan_json, out_dir=out_dir)
    console.print(result)
