from __future__ import annotations

import typer

from src.analysis.post_merge_local_validation_execution_pack import write_post_merge_local_validation_execution_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-post-merge-local-validation-pack")
def hscad_post_merge_local_validation_pack(
    out_dir: str = typer.Option("outputs/post_merge_local_validation_execution_pack", help="Output directory."),
    result_template_dir: str = typer.Option("outputs/local_validation_results", help="Manual result template output directory."),
    original_dwg: str = typer.Option("C:/cad/test/original.dwg", help="Original DWG path. Must not be mutated."),
    working_copy_dwg: str = typer.Option("C:/cad/test_work/copy.dwg", help="Copied DWG path used for validation."),
    save_as_target: str = typer.Option("C:/cad/test_work/result.dwg", help="SaveAs target path."),
    xicad_root: str = typer.Option("C:/xicad", help="XiCAD root path."),
    phase12_workspace: str = typer.Option("outputs/phase10_11_domain_copy_verify", help="Phase 12 workspace."),
    alias: str = typer.Option("WAL", help="Alias candidate for phase12 guard validation."),
):
    """Generate post-merge local validation execution pack. Does not execute CAD."""

    result = write_post_merge_local_validation_execution_outputs(
        out_dir=out_dir,
        result_template_dir=result_template_dir,
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        xicad_root=xicad_root,
        phase12_workspace=phase12_workspace,
        alias=alias,
    )
    console.print(result)
