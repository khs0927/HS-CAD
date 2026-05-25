from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.post_main_local_validation_live_runner_safety import write_post_main_bundle_outputs


def run(
    repo_root: str | Path = ".",
    *,
    operator_review_workspace: str | Path = "outputs/main_merge_operator_review",
    out_dir: str | Path = "outputs/post_main_local_validation_live_runner_safety",
    **_: Any,
) -> dict[str, Any]:
    """Generate post-main local validation and final live runner safety planning artifacts."""

    return write_post_main_bundle_outputs(
        repo_root=repo_root,
        operator_review_workspace=operator_review_workspace,
        out_dir=out_dir,
    )


def run_worker(
    repo_root: str | Path = ".",
    *,
    operator_review_workspace: str | Path = "outputs/main_merge_operator_review",
    out_dir: str | Path = "outputs/post_main_local_validation_live_runner_safety",
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        repo_root=repo_root,
        operator_review_workspace=operator_review_workspace,
        out_dir=out_dir,
        **kwargs,
    )
