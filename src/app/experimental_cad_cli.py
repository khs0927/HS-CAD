from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from src.adapters.backend_registry import build_default_backend_registry
from src.app.cli import app
from src.app.logger import console, success
from src.reports.evidence_report import render_evidence_markdown
from src.reports.json_exporter import export_json
from src.scanners.object_scanner import build_evidence_package
from src.workflows.scan_strategy import plan_scan_strategy


@app.command('experimental-cad-backends')
def experimental_cad_backends(
    query: str = typer.Option('', help='Filter backend registry rows'),
    json_out: str | None = typer.Option(None, help='Optional JSON output path'),
):
    registry = build_default_backend_registry()
    rows = registry.find(query)
    if json_out:
        export_json([row.to_dict() for row in rows], json_out)
        success(f'Experimental backend registry written: {json_out}')
        return

    table = Table('Backend', 'Status', 'Default', 'Requires CAD', 'Purpose')
    for row in rows:
        table.add_row(row.name, row.status, str(row.default), str(row.requires_active_cad), row.purpose)
    console.print(table)


@app.command('experimental-cad-scan-strategy')
def experimental_cad_scan_strategy(
    task: str = typer.Argument('drawing analysis'),
    has_dxf: bool = typer.Option(False, help='Whether a DXF export/fileized source is available'),
    object_count_hint: int | None = typer.Option(None, help='Approximate object count if known'),
    json_out: str | None = typer.Option(None, help='Optional JSON output path'),
):
    strategy = plan_scan_strategy(task, has_dxf=has_dxf, object_count_hint=object_count_hint)
    payload = strategy.to_dict()
    if json_out:
        export_json(payload, json_out)
        success(f'Experimental scan strategy written: {json_out}')
        return

    table = Table('#', 'Step', 'Backend', 'Default', 'Mutates', 'Purpose')
    for step in payload['steps']:
        table.add_row(
            str(step['order']),
            step['name'],
            step['backend'],
            str(step['default_enabled']),
            str(step['mutates_drawing']),
            step['purpose'],
        )
    console.print(table)
    if payload.get('warnings'):
        console.print({'warnings': payload['warnings']})


@app.command('experimental-cad-evidence-synthetic')
def experimental_cad_evidence_synthetic(
    out_dir: str = typer.Option('outputs/experimental_cad_synthetic', help='Output directory'),
):
    objects = [
        {'object_name': 'AcDbPolyline', 'entity_type': 'POLYLINE', 'closed': True, 'points': [[0, 0], [10, 0], [10, 5], [0, 5]], 'layer': 'WAL1'},
        {'object_name': 'AcDbAlignedDimension', 'entity_type': 'DIMENSION', 'layer': 'DIM', 'measurement': 3000, 'text_override': '3000'},
        {'object_name': 'AcDbText', 'entity_type': 'TEXT', 'layer': 'ROOM-TEXT', 'text': 'ROOM 101'},
    ]
    package = build_evidence_package(objects, source='synthetic')
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / 'EXPERIMENTAL_CAD_EVIDENCE_SYNTHETIC.json'
    report_path = out / 'EXPERIMENTAL_CAD_EVIDENCE_SYNTHETIC.md'
    export_json(package, json_path)
    report_path.write_text(render_evidence_markdown(package), encoding='utf-8')
    success(f'Synthetic evidence written: {json_path}')
    success(f'Synthetic report written: {report_path}')
