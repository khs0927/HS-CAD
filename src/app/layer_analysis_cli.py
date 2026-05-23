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
    out_md: Path | None = typer.Option(None, '--out-md'),
):
    json_dir = workspace / 'fileized' / 'json'
    result = LayerSemanticInferer().infer_json_dir(json_dir)
    json_path = out_json or workspace / 'LAYER_SEMANTICS.json'
    md_path = out_md or workspace / 'LAYER_SEMANTICS.md'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text(_to_markdown(result), encoding='utf-8')
    console.print({
        'json': str(json_path),
        'markdown': str(md_path),
        'layer_count': result.get('layer_count'),
        'semantic_counts': result.get('semantic_counts'),
    })
    success('Layer semantics inference written')


def _to_markdown(result: dict) -> str:
    lines = [
        '# HS-CAD Layer Semantics Report',
        '',
        f'- JSON dir: `{result.get("json_dir")}`',
        f'- Files: {result.get("file_count")}',
        f'- Layers: {result.get("layer_count")}',
        f'- Semantic counts: `{json.dumps(result.get("semantic_counts", {}), ensure_ascii=False)}`',
        '',
        '## Layer guesses',
        '',
        '| Layer | Semantic | Confidence | Evidence | Entity Types |',
        '|---|---:|---:|---|---|',
    ]
    for layer in sorted(result.get('layers') or [], key=lambda item: (item.get('predicted_semantic') or '', item.get('layer') or '')):
        counts = layer.get('counts') or {}
        entity_types = counts.get('entity_types') or {}
        evidence = '; '.join(layer.get('evidence') or [])
        lines.append(
            f"| `{_escape(layer.get('layer'))}` | `{_escape(layer.get('predicted_semantic'))}` | {layer.get('confidence')} | {_escape(evidence)} | `{json.dumps(entity_types, ensure_ascii=False)}` |"
        )
    lines += [
        '',
        '## Notes',
        '',
        '- This is a vendor-neutral layer inference report.',
        '- Company-specific layer mapping is intentionally deferred until real Webhard corpus review.',
        '- Confidence is heuristic and should be calibrated after manual review.',
    ]
    return '\n'.join(lines) + '\n'


def _escape(value: object) -> str:
    return str(value or '').replace('|', '\\|').replace('\n', ' ')
