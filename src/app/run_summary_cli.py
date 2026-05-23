from __future__ import annotations

from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.corpus_run.result_summarizer import CorpusRunResultSummarizer


@app.command('hscad-run-summary')
def hscad_run_summary(
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    out_json: Path | None = typer.Option(None, '--out-json'),
    out_md: Path | None = typer.Option(None, '--out-md'),
):
    summarizer = CorpusRunResultSummarizer(workspace)
    json_path = summarizer.write_json(out_json)
    md_path = summarizer.write_markdown(out_md)
    console.print({'json': json_path, 'markdown': md_path})
    success('HS-CAD corpus run summary written')
