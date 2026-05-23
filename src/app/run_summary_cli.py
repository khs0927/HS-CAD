from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success, warn


@app.command('hscad-run-summary')
def hscad_run_summary(
    workspace: Path = typer.Option(Path('outputs/webhard_real_sample'), '--workspace'),
):
    """Generate a comprehensive summary of a corpus pipeline run."""
    if not workspace.exists():
        console.print(f'[red]Error: Workspace directory does not exist: {workspace}[/]')
        raise typer.Exit(code=1)

    # 1. Parse webhard_sample_run.json
    run_log_path = workspace / 'webhard_sample_run.json'
    run_log = {}
    if run_log_path.exists():
        try:
            run_log = json.loads(run_log_path.read_text(encoding='utf-8'))
        except Exception as e:
            warn(f'Failed to parse run log: {e}')

    # 2. Count ODA usage from fileized/json/*.json
    oda_used_count = 0
    fileized_dir = workspace / 'fileized' / 'json'
    if fileized_dir.exists():
        for p in fileized_dir.glob('*.json'):
            try:
                record = json.loads(p.read_text(encoding='utf-8'))
                if record.get('metadata', {}).get('external_converter_used') is True:
                    oda_used_count += 1
            except Exception:
                continue

    # 3. Connect to SQLite to retrieve actual stats
    sqlite_path = workspace / 'cad_knowledge.sqlite'
    db_stats = {}
    engine_stats = []
    top_layers = []
    top_blocks = []
    if sqlite_path.exists():
        try:
            with sqlite3.connect(str(sqlite_path)) as conn:
                conn.row_factory = sqlite3.Row
                for name in ('files', 'layers', 'entities', 'texts', 'blocks', 'dimensions', 'failures'):
                    db_stats[name] = conn.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                
                engine_stats = conn.execute(
                    'SELECT status, engine, extension, count(*) AS count FROM files GROUP BY status, engine, extension'
                ).fetchall()

                top_layers = conn.execute(
                    'SELECT name, sum(entity_count) AS count FROM layers GROUP BY name ORDER BY count DESC LIMIT 10'
                ).fetchall()

                top_blocks = conn.execute(
                    'SELECT name, sum(count) AS count FROM blocks GROUP BY name ORDER BY count DESC LIMIT 10'
                ).fetchall()
        except Exception as e:
            warn(f'Failed to query SQLite DB: {e}')

    # 4. Parse quality_audit.json
    quality_path = workspace / 'quality_audit.json'
    quality_data = {}
    if quality_path.exists():
        try:
            quality_data = json.loads(quality_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    # 5. Parse learning_summary.json
    learning_path = workspace / 'learning_summary.json'
    learning_data = {}
    if learning_path.exists():
        try:
            learning_data = json.loads(learning_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    # Build the gorgeous markdown report
    lines = [
        '# HS-CAD Run Summary Report',
        '',
        '## 1. Execution Overview',
        f'- **Workspace**: `{workspace}`',
    ]

    if run_log:
        lines.append(f'- **Source Root**: `{run_log.get("root")}`')
        lines.append(f'- **Sample Limit**: {run_log.get("sample")}')
        lines.append(f'- **Processing Limit**: {run_log.get("limit")}')
        
        stages = [f'{s["stage"]} ({s["status"]})' for s in run_log.get('stages', [])]
        lines.append(f'- **Pipeline Stages**: {", ".join(stages)}')

    lines.append(f'- **ODA File Converter Used**: **{oda_used_count}** DWG file(s) converted successfully.')
    lines.append('')

    lines.append('## 2. Database Index Statistics')
    if db_stats:
        lines.append(f'- **Total Files Indexed**: {db_stats.get("files", 0)}')
        lines.append(f'- **Total Layers Extracted**: {db_stats.get("layers", 0)}')
        lines.append(f'- **Total Entities Extracted**: {db_stats.get("entities", 0)}')
        lines.append(f'- **Text Elements**: {db_stats.get("texts", 0)}')
        lines.append(f'- **Block Instances**: {db_stats.get("blocks", 0)}')
        lines.append(f'- **Failures Logged**: {db_stats.get("failures", 0)}')
    else:
        lines.append('*No database metrics available.*')
    lines.append('')

    lines.append('## 3. Files by Status / Engine / Extension')
    if engine_stats:
        lines.append('| Status | Engine | Extension | Count |')
        lines.append('| :--- | :--- | :--- | :---: |')
        for row in engine_stats:
            lines.append(f'| {row["status"]} | {row["engine"]} | {row["extension"]} | {row["count"]} |')
    else:
        lines.append('*No file breakdown available.*')
    lines.append('')

    lines.append('## 4. Quality Audit Summary')
    if quality_data:
        lines.append('### Status counts')
        for k, v in quality_data.get('status_counts', {}).items():
            lines.append(f'- **{k}**: {v}')
        lines.append('')
        
        lines.append('### Warnings Encountered')
        warnings = quality_data.get('warning_counts', {})
        if warnings:
            for k, v in warnings.items():
                lines.append(f'- **{k}**: {v}')
        else:
            lines.append('- *None*')
    else:
        lines.append('*No quality metrics available.*')
    lines.append('')

    lines.append('## 5. Key Architecture & Block Learnings')
    if learning_data:
        lines.append('### Top Block Patterns')
        top_blks = learning_data.get('block_patterns', {})
        if top_blks:
            for k, v in list(top_blks.items())[:5]:
                lines.append(f'- **{k}**: {v} instances')
        else:
            lines.append('- *None*')
            
        lines.append('')
        lines.append('### Common Layers')
        common_layers = learning_data.get('common_layers', [])
        if common_layers:
            lines.append(f'- {", ".join(common_layers[:15])}')
        else:
            lines.append('- *None*')
    else:
        lines.append('*No learned patterns available.*')
    lines.append('')

    lines.append('---')
    lines.append('*Report auto-generated by `hscad-run-summary` CLI command.*')

    # Write the report
    out_path = workspace / 'RUN_SUMMARY.md'
    out_path.write_text('\n'.join(lines), encoding='utf-8')
    
    # Also print to terminal for feedback
    table = Table('Metric', 'Value')
    table.add_row('Workspace', str(workspace))
    table.add_row('ODA Converter Used', str(oda_used_count))
    if db_stats:
        table.add_row('Total Files', str(db_stats.get('files', 0)))
        table.add_row('Total Entities', str(db_stats.get('entities', 0)))
        table.add_row('Failures Logged', str(db_stats.get('failures', 0)))
    console.print(table)
    
    success(f'Run summary written: {out_path}')
