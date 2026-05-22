from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.integrations.tool_catalog import find_catalog_tools
from src.reports.json_exporter import export_json


@app.command('hscad-open-tools')
def hscad_open_tools(
    query: str = typer.Option('', '--query', '-q'),
    out: Path | None = typer.Option(None, '--out'),
):
    payload = find_catalog_tools(query)
    table = Table('Priority', 'Name', 'Status', 'Role', 'Default Use')
    for tool in payload['tools']:
        table.add_row(
            str(tool.get('priority', '')),
            str(tool.get('name', '')),
            str(tool.get('status', '')),
            str(tool.get('role', '')),
            str(tool.get('default_use', '')),
        )
    console.print(table)
    if payload.get('warnings'):
        console.print({'warnings': payload['warnings']})
    if out:
        export_json(payload, out)
        success(f'HS-CAD open tool catalog written: {out}')
