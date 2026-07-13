from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app as root_app
from src.app.logger import console, success
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
