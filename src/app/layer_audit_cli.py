from __future__ import annotations

from pathlib import Path

import typer

from src.analysis.layer_audit import write_layer_audit
from src.app.cli import app
from src.app.logger import console, success


@app.command('hscad-layer-audit')
def hscad_layer_audit(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
    out_md: Path | None = typer.Option(None, '--out-md'),
):
    result = write_layer_audit(workspace, out_json=out_json, out_md=out_md)
    console.print({
        'workspace': str(workspace),
        'findings': result.get('finding_count'),
        'severity_counts': result.get('severity_counts'),
        'finding_type_counts': result.get('finding_type_counts'),
    })
    success('Layer semantics audit written')
