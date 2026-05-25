from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.final_live_runner_safety_spec_gate import write_final_live_runner_safety_spec_gate_outputs


def run(
    repo_root: str | Path = ".",
    *,
    local_validation_summary_json: str | Path = "outputs/local_validation_recorder/LOCAL_VALIDATION_RESULT_SUMMARY.json",
    out_dir: str | Path = "outputs/final_live_runner_safety_spec_gate",
    **_: Any,
) -> dict[str, Any]:
    """Generate final live runner safety spec gate artifacts. Does not implement runner."""

    return write_final_live_runner_safety_spec_gate_outputs(
        repo_root=repo_root,
        local_validation_summary_json=local_validation_summary_json,
        out_dir=out_dir,
    )


def run_worker(
    repo_root: str | Path = ".",
    *,
    local_validation_summary_json: str | Path = "outputs/local_validation_recorder/LOCAL_VALIDATION_RESULT_SUMMARY.json",
    out_dir: str | Path = "outputs/final_live_runner_safety_spec_gate",
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        repo_root=repo_root,
        local_validation_summary_json=local_validation_summary_json,
        out_dir=out_dir,
        **kwargs,
    )
