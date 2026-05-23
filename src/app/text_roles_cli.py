from __future__ import annotations

import json
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.spatial.text_roles import TextRoleInferer


@app.command('hscad-text-roles')
def hscad_text_roles(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
    out_md: Path | None = typer.Option(None, '--out-md'),
):
    json_dir = workspace / 'fileized' / 'json'
    result = TextRoleInferer().infer_json_dir(json_dir)
    json_path = out_json or workspace / 'TEXT_ROLE_INFERENCE.json'
    md_path = out_md or workspace / 'TEXT_ROLE_INFERENCE.md'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text(_to_markdown(result), encoding='utf-8')
    console.print({'json': str(json_path), 'markdown': str(md_path), 'role_counts': result.get('role_counts')})
    success('CAD text role inference written')


def _to_markdown(result: dict) -> str:
    lines = [
        '# HS-CAD Text Role Inference Report',
        '',
        f'- JSON dir: `{result.get("json_dir")}`',
        f'- Files: {result.get("file_count")}',
        f'- Text count: {result.get("text_count")}',
        f'- Role counts: `{json.dumps(result.get("role_counts", {}), ensure_ascii=False)}`',
        '',
        '## Sample roles',
    ]
    for role in result.get('roles', [])[:300]:
        evidence = '; '.join(role.get('evidence') or [])
        lines.append(
            f'- `{role.get("text")}` → **{role.get("role")}** '
            f'({role.get("confidence")}) layer=`{role.get("layer")}` evidence={evidence}'
        )
    return '\n'.join(lines) + '\n'
