from __future__ import annotations

import json
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.spatial.shapely_topology import ShapelyTopologyAnalyzer


@app.command('hscad-shapely-topology')
def hscad_shapely_topology(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
):
    json_dir = workspace / 'fileized' / 'json'
    result = ShapelyTopologyAnalyzer().analyze_json_dir(json_dir)
    json_path = out_json or workspace / 'SHAPELY_TOPOLOGY.json'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    console.print({
        'json': str(json_path),
        'backend': result.get('backend'),
        'file_count': result.get('file_count'),
        'status_counts': result.get('status_counts'),
        'polygon_count': result.get('polygon_count'),
    })
    success('Shapely topology analysis written')
