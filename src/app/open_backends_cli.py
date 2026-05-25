from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.integrations.open_source_backends import OpenSourceBackendRegistry


@app.command('hscad-open-backends')
def hscad_open_backends(
    config: Path = typer.Option(Path('config/open_source_backends.json'), '--config'),
    out_json: Path | None = typer.Option(None, '--out-json'),
):
    registry = OpenSourceBackendRegistry(config)
    summary = registry.summary()
    table = Table('Backend', 'Capability', 'Import', 'Available', 'Planned')
    for item in summary['backends']:
        table.add_row(item['id'], item['capability'], item['python_import'], str(item['available']), item['planned_pr'])
    console.print(table)
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        console.print({'json': str(out_json)})
    success('Open source backend discovery complete')
