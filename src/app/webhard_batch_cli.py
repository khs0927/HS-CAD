from __future__ import annotations

from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.corpus_run.batch_runner import CorpusBatchRunner
from src.corpus_run.pipeline_runner import CorpusPipelineRunner


@app.command('hscad-webhard-batch')
def hscad_webhard_batch(
    drive: str = typer.Option('Z:/', '--drive'),
    workspace: Path = typer.Option(Path('outputs/webhard_batch'), '--workspace'),
    sample: int = typer.Option(100, '--sample'),
    batch_size: int = typer.Option(50, '--batch-size'),
    max_batches: int = typer.Option(1, '--max-batches'),
    start_offset: int = typer.Option(0, '--start-offset'),
    skip_existing: bool = typer.Option(True, '--skip-existing/--no-skip-existing'),
    prepare: bool = typer.Option(True, '--prepare/--no-prepare'),
    finalize: bool = typer.Option(True, '--finalize/--no-finalize'),
):
    root = Path(drive) / '내 드라이브' / '#웹하드'
    if not root.exists():
        console.print({'error': f'Webhard root not found: {root}'})
        raise typer.Exit(code=2)
    if prepare or not (workspace / 'run_manifest.json').exists():
        prepared = CorpusPipelineRunner(workspace).prepare(root, sample=sample)
        console.print({'prepare': prepared})
    result = CorpusBatchRunner(workspace).run_batches(
        batch_size=batch_size,
        max_batches=max_batches,
        start_offset=start_offset,
        skip_existing=skip_existing,
        finalize=finalize,
    )
    console.print(result)
    success(f'Webhard batch complete. Next offset: {result["next_offset"]}')
