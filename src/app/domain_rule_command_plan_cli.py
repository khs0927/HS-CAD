from __future__ import annotations

from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.workers.domain_rule_command_plan_worker import run_domain_rule_command_plan_worker
from src.workers.domain_rule_decision_worker import run_domain_rule_decision_worker


@app.command('domain-rule-command-plan')
def domain_rule_command_plan(
    decision_package_json: str = typer.Option(..., help='DOMAIN_RULE_DECISION_PACKAGE.json path'),
    out_dir: str = typer.Option('outputs/domain_rule_command_plan', help='Output directory'),
):
    result = run_domain_rule_command_plan_worker(decision_package_json, out_dir=out_dir)
    console.print(result)


@app.command('domain-rule-command-plan-synthetic')
def domain_rule_command_plan_synthetic(
    out_dir: str = typer.Option('outputs/domain_rule_command_plan_synthetic', help='Output directory'),
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    decision_dir = out / 'decision'
    plan_dir = out / 'command_plan'
    decision_result = run_domain_rule_decision_worker(
        out / 'synthetic_objects.json',
        out_dir=decision_dir,
        task='synthetic command planning decision',
        xicad_root=xicad_root,
    ) if (out / 'synthetic_objects.json').exists() else _make_synthetic_decision(out, decision_dir, xicad_root)
    plan_result = run_domain_rule_command_plan_worker(decision_result['json'], out_dir=plan_dir)
    success(f'Domain rule command plan synthetic output written: {out}')
    console.print({'decision': decision_result, 'command_plan': plan_result})


def _make_synthetic_decision(out: Path, decision_dir: Path, xicad_root: str):
    from src.reports.json_exporter import export_json

    objects_path = out / 'synthetic_objects.json'
    objects = [
        {'object_name': 'AcDbPolyline', 'entity_type': 'POLYLINE', 'closed': True, 'layer': 'WAL1'},
        {'object_name': 'AcDbBlockReference', 'entity_type': 'INSERT', 'layer': '0', 'name': 'H-300x150'},
        {'object_name': 'AcDbText', 'entity_type': 'TEXT', 'layer': 'ROOM-TEXT', 'text': 'ROOM 101'},
    ]
    export_json(objects, objects_path)
    return run_domain_rule_decision_worker(
        objects_path,
        out_dir=decision_dir,
        task='synthetic command planning decision',
        xicad_root=xicad_root,
    )
