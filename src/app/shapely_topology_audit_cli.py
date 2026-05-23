from __future__ import annotations

import json
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.spatial.shapely_topology_audit import ShapelyTopologyAuditor


@app.command('hscad-shapely-topology-audit')
def hscad_shapely_topology_audit(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
    snap_tolerance: float = typer.Option(0.0, '--snap-tolerance'),
):
    json_dir = workspace / 'fileized' / 'json'
    result = ShapelyTopologyAuditor().audit_json_dir(json_dir, snap_tolerance=snap_tolerance)
    json_path = out_json or workspace / 'SHAPELY_TOPOLOGY_AUDIT.json'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    console.print({
        'json': str(json_path),
        'backend': result.get('backend'),
        'file_count': result.get('file_count'),
        'status_counts': result.get('status_counts'),
        'totals': result.get('totals'),
        'finding_count': result.get('finding_count'),
        'avg_quality_score': result.get('avg_quality_score'),
    })
    success('Shapely topology audit written')
