from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.local_validation_recorder_final_runner_safety import write_local_validation_recorder_outputs


def run(
    repo_root: str | Path = ".",
    *,
    result_dir: str | Path = "outputs/local_validation_results",
    out_dir: str | Path = "outputs/local_validation_recorder",
    create_templates: bool = True,
    **_: Any,
) -> dict[str, Any]:
    """Record manual local validation results. Does not execute CAD."""

    return write_local_validation_recorder_outputs(
        repo_root=repo_root,
        result_dir=result_dir,
        out_dir=out_dir,
        create_templates=create_templates,
    )


def run_worker(
    repo_root: str | Path = ".",
    *,
    result_dir: str | Path = "outputs/local_validation_results",
    out_dir: str | Path = "outputs/local_validation_recorder",
    create_templates: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        repo_root=repo_root,
        result_dir=result_dir,
        out_dir=out_dir,
        create_templates=create_templates,
        **kwargs,
    )
