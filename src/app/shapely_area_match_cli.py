from __future__ import annotations

import json
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.spatial.shapely_area_matching import write_shapely_area_matches


@app.command('hscad-shapely-area-match')
def hscad_shapely_area_match(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
    min_score: float = typer.Option(0.25, '--min-score'),
):
    result = write_shapely_area_matches(workspace, out_json=out_json, min_score=min_score)
    json_path = out_json or workspace / 'SHAPELY_AREA_MATCHES.json'
    console.print({
        'json': str(json_path),
        'status': result.get('status'),
        'area_count': result.get('area_count'),
        'shapely_polygon_count': result.get('shapely_polygon_count'),
        'match_count': result.get('match_count'),
    })
    success('Shapely area matches written')
