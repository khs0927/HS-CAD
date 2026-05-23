from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.integrations.fusion_matrix import OpenSourceFusionMatrix


@app.command('hscad-fusion-matrix')
def hscad_fusion_matrix(
    config: Path = typer.Option(Path('config/open_source_fusion_matrix.json'), '--config'),
    out_json: Path | None = typer.Option(None, '--out-json'),
):
    matrix = OpenSourceFusionMatrix(config)
    summary = matrix.summary()
    table = Table('Target', 'Implemented weight', 'Planned weight', 'Deferred weight')
    for target in summary.get('targets') or []:
        table.add_row(
            str(target.get('target_type')),
            str(target.get('implemented_weight')),
            str(target.get('planned_weight')),
            str(target.get('deferred_weight')),
        )
    console.print(table)
    console.print({'signal_count': summary.get('signal_count'), 'backend_counts': summary.get('backend_counts')})
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        console.print({'json': str(out_json)})
    success('Open source fusion matrix summary written')
