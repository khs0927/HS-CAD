from __future__ import annotations

import typer

from src.app.cli import app
from src.app.logger import console
from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.workers.zwcad_copy_validation_worker import (
    run_copy_scan_validation_worker,
    run_copy_saveas_validation_worker,
)


def _adapter_factory():
    return ZWCADCOMAdapter(visible=True)


@app.command("zwcad-copy-scan-validate")
def zwcad_copy_scan_validate(
    original_dwg: str = typer.Option(..., help="Original DWG path. It will not be modified."),
    working_copy_dwg: str = typer.Option(..., help="Working copy DWG path."),
    out_dir: str = typer.Option("outputs/zwcad_copy_validation", help="Output directory"),
    overwrite_copy: bool = typer.Option(False, help="Allow overwriting existing working copy."),
):
    result = run_copy_scan_validation_worker(
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        out_dir=out_dir,
        adapter_factory=_adapter_factory,
        overwrite_copy=overwrite_copy,
    )
    console.print(result)


@app.command("zwcad-copy-saveas-validate")
def zwcad_copy_saveas_validate(
    original_dwg: str = typer.Option(..., help="Original DWG path. It will not be modified."),
    working_copy_dwg: str = typer.Option(..., help="Working copy DWG path."),
    save_as_target: str = typer.Option(..., help="SaveAs target path. Must not equal original DWG."),
    out_dir: str = typer.Option("outputs/zwcad_copy_saveas_validation", help="Output directory"),
    overwrite_copy: bool = typer.Option(False, help="Allow overwriting existing working copy."),
):
    result = run_copy_saveas_validation_worker(
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        out_dir=out_dir,
        adapter_factory=_adapter_factory,
        overwrite_copy=overwrite_copy,
    )
    console.print(result)
