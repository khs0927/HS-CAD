from __future__ import annotations

import json
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.spatial.containment import TextContainmentAnalyzer


@app.command('hscad-spatial-containment')
def hscad_spatial_containment(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
    out_md: Path | None = typer.Option(None, '--out-md'),
):
    json_dir = workspace / 'fileized' / 'json'
    result = TextContainmentAnalyzer().analyze_json_dir(json_dir)
    json_path = out_json or workspace / 'SPATIAL_CONTAINMENT.json'
    md_path = out_md or workspace / 'SPATIAL_CONTAINMENT.md'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text(_to_markdown(result), encoding='utf-8')
    console.print({'json': str(json_path), 'markdown': str(md_path), 'relation_count': result['relation_count']})
    success('Spatial containment analysis written')


def _to_markdown(result: dict) -> str:
    lines = [
        '# HS-CAD Spatial Containment Report',
        '',
        f'- JSON dir: `{result.get("json_dir")}`',
        f'- Files: {result.get("file_count")}',
        f'- Relations: {result.get("relation_count")}',
        '',
        '## Text in closed polyline relations',
    ]
    for relation in result.get('relations', [])[:200]:
        lines.append(
            f'- `{relation.get("text")}` text `{relation.get("text_handle")}` on `{relation.get("text_layer")}` '
            f'inside polygon `{relation.get("polygon_handle")}` on `{relation.get("polygon_layer")}`'
        )
    return '\n'.join(lines) + '\n'
