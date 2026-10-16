from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app as root_app
from src.app.logger import console, success
from src.semantic_index.evaluation import evaluate_group_csv
from src.semantic_index.service import SemanticIndexService

semantic_app = typer.Typer(help='Offline text-independent CAD similarity index')
root_app.add_typer(semantic_app, name='semantic-index')


@semantic_app.command('build')
def build_index(
    records_dir: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True, help='Folder containing FileizedDrawingRecord JSON files'),
    db: Path = typer.Option(Path('outputs/semantic_index/semantic.sqlite3'), help='Local SQLite index path'),
    clear: bool = typer.Option(False, help='Replace the current geometry-v1 index'),
) -> None:
    result = SemanticIndexService(db).build_from_json_dir(records_dir, clear=clear)
    console.print(result)
    success(f"Indexed {result['indexed']} drawings; total={result['total_in_index']}")


@semantic_app.command('query')
def query_index(
    record: Path = typer.Option(..., exists=True, dir_okay=False, help='FileizedDrawingRecord JSON used as the query'),
    db: Path = typer.Option(Path('outputs/semantic_index/semantic.sqlite3'), help='Local SQLite index path'),
    top_k: int = typer.Option(10, min=1, max=100, help='Maximum result count'),
    include_self: bool = typer.Option(False, help='Include the query drawing itself'),
) -> None:
    hits = SemanticIndexService(db).search_record(record, limit=top_k, include_self=include_self)
    table = Table('Rank', 'Score', 'Drawing', 'Entities', 'Feature')
    for index, hit in enumerate(hits, start=1):
        table.add_row(
            str(index),
            f'{hit.score:.4f}',
            hit.relative_path,
            str(hit.metadata.get('entity_count', '')),
            hit.feature_version,
        )
    console.print(table)


@semantic_app.command('evaluate')
def evaluate_index(
    labels: Path = typer.Option(..., exists=True, dir_okay=False, help='CSV with record,group columns'),
    db: Path = typer.Option(Path('outputs/semantic_index/semantic.sqlite3'), help='Local SQLite index path'),
    top_k: int = typer.Option(5, min=1, max=100, help='Precision/recall cutoff'),
    out: Path | None = typer.Option(None, help='Optional JSON report path'),
) -> None:
    report = evaluate_group_csv(SemanticIndexService(db), labels, top_k=top_k)
    precision_key = f'precision_at_{top_k}'
    recall_key = f'recall_at_{top_k}'
    hit_key = f'hit_at_{top_k}'
    table = Table('Queries', f'P@{top_k}', f'R@{top_k}', f'Hit@{top_k}')
    table.add_row(
        str(report['evaluated_queries']),
        f"{report[precision_key]:.4f}",
        f"{report[recall_key]:.4f}",
        f"{report[hit_key]:.4f}",
    )
    console.print(table)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        success(f'Evaluation report written: {out}')


@semantic_app.command('status')
def index_status(
    db: Path = typer.Option(Path('outputs/semantic_index/semantic.sqlite3'), help='Local SQLite index path'),
) -> None:
    console.print(SemanticIndexService(db).inspect())


@semantic_app.command('gui')
def launch_gui(
    db: Path = typer.Option(Path('outputs/semantic_index/semantic.sqlite3'), help='Local SQLite index path'),
) -> None:
    from src.local_app.semantic_index_app import run_app

    run_app(db)
