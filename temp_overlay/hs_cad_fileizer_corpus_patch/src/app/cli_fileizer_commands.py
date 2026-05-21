from __future__ import annotations

from pathlib import Path

import typer
from rich import print

from src.drawing_fileizers.fileizer_registry import FileizerRegistry
from src.drawing_fileizers.fileized_record_writer import FileizedRecordWriter


fileizer_app = typer.Typer(help="Drawing fileizer commands")


@fileizer_app.command("fileizer-check")
def fileizer_check() -> None:
    registry = FileizerRegistry()
    for row in registry.availability_report():
        status = "OK" if row["available"] else "unavailable"
        print(f"[bold]{row['name']}[/bold]: {status} ({row['version']})")


@fileizer_app.command("fileize")
def fileize(input: Path = typer.Option(..., "--input"), out: Path = typer.Option(Path("outputs/fileized"), "--out")) -> None:
    registry = FileizerRegistry()
    fileizer = registry.best_for(input)
    if not fileizer:
        raise typer.BadParameter(f"No fileizer supports {input}")
    record = fileizer.fileize(input, out)
    writer = FileizedRecordWriter(out)
    written = writer.write(record)
    print(f"[green]fileized[/green] {input} -> {written} status={record.status}")


@fileizer_app.command("fileize-folder")
def fileize_folder(
    root: Path = typer.Option(..., "--root"),
    out: Path = typer.Option(Path("outputs/fileized"), "--out"),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    registry = FileizerRegistry()
    writer = FileizedRecordWriter(out)
    supported = {".dwg", ".dxf", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".ifc", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".txt"}

    count = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in supported:
            continue
        fileizer = registry.best_for(path)
        if not fileizer:
            continue
        # Resume skip based on stable ID handled after fileize would compute ID; keep simple here.
        record = fileizer.fileize(path, out)
        json_path = out / "json" / f"{record.file_id}.json"
        if resume and json_path.exists() and not force:
            continue
        writer.write(record)
        count += 1
    print(f"[green]fileized {count} files[/green]")
