from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.post_merge_local_validation_execution_pack import write_post_merge_local_validation_execution_outputs


def run(
    *,
    out_dir: str | Path = "outputs/post_merge_local_validation_execution_pack",
    result_template_dir: str | Path = "outputs/local_validation_results",
    original_dwg: str = "C:/cad/test/original.dwg",
    working_copy_dwg: str = "C:/cad/test_work/copy.dwg",
    save_as_target: str = "C:/cad/test_work/result.dwg",
    xicad_root: str = "C:/xicad",
    phase12_workspace: str = "outputs/phase10_11_domain_copy_verify",
    alias: str = "WAL",
    **_: Any,
) -> dict[str, Any]:
    """Generate manual post-merge local validation execution pack. Does not run CAD."""

    return write_post_merge_local_validation_execution_outputs(
        out_dir=out_dir,
        result_template_dir=result_template_dir,
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        xicad_root=xicad_root,
        phase12_workspace=phase12_workspace,
        alias=alias,
    )


def run_worker(**kwargs: Any) -> dict[str, Any]:
    return run(**kwargs)
