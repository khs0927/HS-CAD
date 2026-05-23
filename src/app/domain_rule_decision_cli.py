from __future__ import annotations

import json
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.reports.json_exporter import export_json
from src.workers.domain_rule_decision_worker import run_domain_rule_decision_worker


@app.command('domain-rule-decision')
def domain_rule_decision(
    objects_json: str = typer.Option(..., help='Analyzed objects JSON path'),
    task: str = typer.Option('drawing modification decision', help='Decision task'),
    out_dir: str = typer.Option('outputs/domain_rule_decision', help='Output directory'),
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
    archioffice_root: str | None = typer.Option(None, help='Optional ArchiOffice root path'),
    hssteel_root: str | None = typer.Option(None, help='Optional HS-Steel root path'),
):
    result = run_domain_rule_decision_worker(
        objects_json,
        out_dir=out_dir,
        task=task,
        xicad_root=xicad_root,
        archioffice_root=archioffice_root,
        hssteel_root=hssteel_root,
    )
    console.print(result)


@app.command('domain-rule-decision-synthetic')
def domain_rule_decision_synthetic(
    out_dir: str = typer.Option('outputs/domain_rule_decision_synthetic', help='Output directory'),
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    objects_path = out / 'synthetic_objects.json'
    objects = [
        {'object_name': 'AcDbPolyline', 'entity_type': 'POLYLINE', 'closed': True, 'layer': 'WAL1'},
        {'object_name': 'AcDbBlockReference', 'entity_type': 'INSERT', 'layer': '0', 'name': 'H-300x150'},
        {'object_name': 'AcDbText', 'entity_type': 'TEXT', 'layer': 'ROOM-TEXT', 'text': 'ROOM 101'},
    ]
    export_json(objects, objects_path)
    result = run_domain_rule_decision_worker(
        objects_path,
        out_dir=out,
        task='synthetic domain-rule modification decision',
        xicad_root=xicad_root,
    )
    success(f'Domain rule decision synthetic output written: {out}')
    console.print(result)
