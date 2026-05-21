from __future__ import annotations

from pathlib import Path

import typer
from rich import print

from src.drawing_fileizers.fileizer_registry import FileizerRegistry
from src.drawing_fileizers.fileized_record_writer import FileizedRecordWriter


fileizer_app = typer.Typer(help="Drawing fileizer commands")


@fileizer_app.command("fileizer-check")
def fileizer_check() -> None:
    """Print detailed availability information for each registered fileizer.
\n    The output includes the fileizer name, availability status, version (if any),\n    and a human‑readable reason when unavailable. This aids debugging\n    DWG handling where COM or external CLI tools may be missing.
    """
    registry = FileizerRegistry()
    for row in registry.availability_report():
        name = row["name"]
        available = row["available"]
        version = row.get("version", "unknown")
        status = "OK" if available else "unavailable"
        # Attempt to fetch a detailed reason if the fileizer implements it.
        reason = ""
        try:
            # ``registry.fileizers`` holds instantiated objects in the same order.
            f_obj = next((f for f in registry.fileizers if f.get_name() == name), None)
            if f_obj and not available and hasattr(f_obj, "get_unavailable_reason"):
                reason = f_obj.get_unavailable_reason()
        except Exception:
            reason = ""
        if reason:
            print(f"[bold]{name}[/bold]: {status} (v{version}) - {reason}")
        else:
            print(f"[bold]{name}[/bold]: {status} (v{version})")


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
