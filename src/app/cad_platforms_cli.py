from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.integrations.cad_platforms import CADPlatformRegistry


@app.command('hscad-cad-platforms')
def hscad_cad_platforms(
    config: Path = typer.Option(Path('config/cad_platforms.json'), '--config'),
    out_json: Path | None = typer.Option(None, '--out-json'),
):
    registry = CADPlatformRegistry(config)
    summary = registry.summary()
    table = Table('CAD Platform', 'Available', 'Reason', 'Analysis role')
    for item in summary['platforms']:
        table.add_row(item['id'], str(item['available']), item['reason'], item['analysis_role'])
    console.print(table)
    console.print({'preferred_analysis_path': summary['preferred_analysis_path']})
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        console.print({'json': str(out_json)})
    success('CAD platform compatibility discovery complete')
