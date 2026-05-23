from __future__ import annotations

import json
from pathlib import Path

import typer

from src.analysis.layer_semantics import LayerSemanticInferer
from src.app.cli import app
from src.app.logger import console, success


@app.command('hscad-layer-semantics')
def hscad_layer_semantics(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
):
    json_dir = workspace / 'fileized' / 'json'
    result = LayerSemanticInferer().infer_json_dir(json_dir)
    json_path = out_json or workspace / 'LAYER_SEMANTICS.json'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    console.print({'json': str(json_path), 'layer_count': result.get('layer_count'), 'semantic_counts': result.get('semantic_counts')})
    success('Layer semantics inference written')
