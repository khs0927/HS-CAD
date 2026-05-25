from __future__ import annotations

import typer

from src.analysis.local_validation_operator_handoff import write_operator_handoff_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-local-validation-operator-handoff")
def hscad_local_validation_operator_handoff(
    out_dir: str = typer.Option("outputs/local_validation_operator_handoff", help="Output directory."),
    original_dwg: str = typer.Option("C:/cad/test/original.dwg", help="Original DWG path. Must not be mutated."),
    working_copy_dwg: str = typer.Option("C:/cad/test_work/copy.dwg", help="Copied DWG path."),
    save_as_target: str = typer.Option("C:/cad/test_work/result.dwg", help="SaveAs target path."),
    xicad_root: str = typer.Option("C:/xicad", help="XiCAD root path."),
):
    """Generate manual local validation operator handoff. Does not execute CAD."""

    result = write_operator_handoff_outputs(
        out_dir=out_dir,
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        xicad_root=xicad_root,
    )
    console.print(result)
