from __future__ import annotations

from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.corpus_run.pipeline_runner import CorpusPipelineRunner

corpus_app = typer.Typer(help='HS-CAD corpus pipeline commands')
app.add_typer(corpus_app, name='corpus-run')


@corpus_app.command('prepare')
def corpus_prepare(
    root: Path = typer.Option(..., '--root'),
    workspace: Path = typer.Option(Path('outputs/corpus_workspace'), '--workspace'),
    sample: int = typer.Option(0, '--sample'),
):
    result = CorpusPipelineRunner(workspace).prepare(root, sample=sample)
    console.print(result)
    success('Corpus manifest prepared')


@corpus_app.command('fileize')
def corpus_fileize(
    workspace: Path = typer.Option(Path('outputs/corpus_workspace'), '--workspace'),
    limit: int = typer.Option(0, '--limit'),
):
    result = CorpusPipelineRunner(workspace).fileize(limit=limit)
    console.print(result)
    success('Corpus fileize stage complete')


@corpus_app.command('index')
def corpus_index(
    workspace: Path = typer.Option(Path('outputs/corpus_workspace'), '--workspace'),
):
    result = CorpusPipelineRunner(workspace).index()
    console.print(result)
    success('Corpus index stage complete')


@corpus_app.command('query')
def corpus_query(
    text: str = typer.Argument(...),
    workspace: Path = typer.Option(Path('outputs/corpus_workspace'), '--workspace'),
    limit: int = typer.Option(20, '--limit'),
):
    console.print(CorpusPipelineRunner(workspace).query(text, limit=limit))


@corpus_app.command('report')
def corpus_report(
    workspace: Path = typer.Option(Path('outputs/corpus_workspace'), '--workspace'),
    out: Path | None = typer.Option(None, '--out'),
):
    result = CorpusPipelineRunner(workspace).report(out)
    console.print(result)
    success('Corpus report written')
