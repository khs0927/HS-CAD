from __future__ import annotations

import json
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.corpus_run.pipeline_runner import CorpusPipelineRunner


@app.command('hscad-webhard-sample')
def hscad_webhard_sample(
    drive: str = typer.Option('Z:/', '--drive'),
    workspace: Path = typer.Option(Path('outputs/webhard_real_sample'), '--workspace'),
    sample: int = typer.Option(5, '--sample'),
    limit: int = typer.Option(5, '--limit'),
    stop_on_error: bool = typer.Option(False, '--stop-on-error'),
):
    """Run a safe sample corpus flow for the local Google Drive Webhard folder.

    The Korean path is assembled inside Python to avoid shell encoding issues:
    Z:/내 드라이브/#웹하드
    """
    root = Path(drive) / '내 드라이브' / '#웹하드'
    result = {
        'root': str(root),
        'workspace': str(workspace),
        'sample': sample,
        'limit': limit,
        'stages': [],
    }
    if not root.exists():
        result['error'] = f'Webhard root not found: {root}'
        console.print(result)
        raise typer.Exit(code=2)

    runner = CorpusPipelineRunner(workspace)
    stages = [
        ('prepare', lambda: runner.prepare(root, sample=sample)),
        ('fileize', lambda: runner.fileize(limit=limit)),
        ('validate', lambda: _validate(workspace)),
        ('index', runner.index),
        ('learn', runner.learn),
        ('quality', lambda: _quality(workspace)),
        ('report', runner.report),
    ]
    for name, fn in stages:
        try:
            payload = fn()
            result['stages'].append({'stage': name, 'status': 'ok', 'result': payload})
            console.print({'stage': name, 'status': 'ok', 'result': payload})
        except Exception as exc:
            item = {'stage': name, 'status': 'failed', 'error': str(exc)}
            result['stages'].append(item)
            console.print(item)
            if stop_on_error:
                break

    workspace.mkdir(parents=True, exist_ok=True)
    log_path = workspace / 'webhard_sample_run.json'
    log_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    success(f'Webhard sample run log written: {log_path}')


def _validate(workspace: Path) -> dict:
    from src.corpus.validator import FileizedRecordValidator

    result = FileizedRecordValidator().validate_json_dir(workspace / 'fileized' / 'json')
    if result.get('invalid_count'):
        raise RuntimeError(f'Fileized JSON validation failed: {result}')
    return result


def _quality(workspace: Path) -> dict:
    from src.corpus.quality import CorpusQualityAuditor

    auditor = CorpusQualityAuditor(workspace)
    return {'json': auditor.write_json(), 'markdown': auditor.write_markdown()}
