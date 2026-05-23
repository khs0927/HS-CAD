from __future__ import annotations

import json
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.spatial.graph_exporter import SpatialGraphExporter


@app.command('hscad-spatial-graph')
def hscad_spatial_graph(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
    area_backend: str = typer.Option('auto', '--area-backend'),
):
    json_dir = workspace / 'fileized' / 'json'
    result = SpatialGraphExporter(area_backend=area_backend).export_json_dir(json_dir)
    json_path = out_json or workspace / 'SPATIAL_GRAPH.json'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    console.print({
        'json': str(json_path),
        'nodes': result.get('node_count'),
        'edges': result.get('edge_count'),
        'node_kind_counts': result.get('node_kind_counts'),
        'edge_relation_counts': result.get('edge_relation_counts'),
    })
    success('Spatial relationship graph exported')
