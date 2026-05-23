from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console
from src.converters.oda_file_converter import ODAFileConverter


@app.command('hscad-converters')
def hscad_converters(
    probe: bool = typer.Option(False, '--probe'),
    executable: Path | None = typer.Option(None, '--oda-exe'),
):
    """Inspect external CAD converters available to HS-CAD."""
    converter = ODAFileConverter(executable=executable)
    ok, reason = converter.is_available()
    table = Table('Converter', 'Available', 'Path / Reason')
    table.add_row('ODA File Converter', str(ok), reason)
    console.print(table)
    if probe and ok:
        console.print({'oda_file_converter': str(converter.executable), 'command_shape': converter._build_command(Path('<input_dir>'), Path('<output_dir>'))})
