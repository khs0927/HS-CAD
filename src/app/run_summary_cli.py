from __future__ import annotations

from pathlib import Path
import json
import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.corpus_run.result_summarizer import CorpusRunResultSummarizer


@app.command('hscad-run-summary')
def hscad_run_summary(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
    out_md: Path | None = typer.Option(None, '--out-md'),
):
    """Generate a comprehensive checklist-based summary of a corpus pipeline run."""
    if not workspace.exists():
        console.print(f'[red]Error: Workspace directory does not exist: {workspace}[/]')
        raise typer.Exit(code=1)

    summarizer = CorpusRunResultSummarizer(workspace)
    json_path = summarizer.write_json(out_json)
    md_path = summarizer.write_markdown(out_md)

    # Print a beautiful Rich table overview
    summary = summarizer.summarize()
    checklist = summary.get('checklist', {})
    
    table = Table('Validation Item', 'Status / Count')
    table.add_row('webhard_sample_run.json Exists', '✅ Yes' if checklist.get('webhard_sample_run_json_exists') else '❌ No')
    table.add_row('QUALITY_AUDIT.md Exists', '✅ Yes' if checklist.get('quality_audit_md_exists') else '❌ No')
    table.add_row('FINAL_REPORT.md Exists', '✅ Yes' if checklist.get('final_report_md_exists') else '❌ No')
    table.add_row('Staged DWGs under tmp/dxf', str(checklist.get('staged_dwg_count', 0)))
    table.add_row('Converted DXFs under tmp/dxf', str(checklist.get('dxf_count', 0)))
    table.add_row('DWG record engine is correct', '✅ Yes' if checklist.get('dwg_engine_is_zwcad_saveas_dxf_ezdxf') else '❌ No')
    table.add_row('ODA Converter Success Count', str(checklist.get('external_converter_success_count', 0)))
    table.add_row('ODA Converter Warning Count', str(checklist.get('external_converter_warning_count', 0)))
    table.add_row('ZWCAD Fallback Observed', '✅ Yes' if checklist.get('zwcad_fallback_attempted_when_oda_unavailable_or_failed') else '❌ No')
    table.add_row('All Pipeline Stages Completed', '✅ Yes' if checklist.get('all_pipeline_stages_completed_without_abort') else '❌ No')

    console.print(table)
    console.print({'json': json_path, 'markdown': md_path})
    success('HS-CAD corpus run summary written successfully')
