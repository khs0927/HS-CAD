from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.human_main_merge_review_gate import write_human_main_merge_review_outputs


def run(
    repo_root: str | Path = ".",
    *,
    post_main_safety_workspace: str | Path = "outputs/post_main_local_validation_live_runner_safety",
    out_dir: str | Path = "outputs/human_main_merge_review_gate",
    **_: Any,
) -> dict[str, Any]:
    """Generate human main merge review gate artifacts."""

    return write_human_main_merge_review_outputs(
        repo_root=repo_root,
        post_main_safety_workspace=post_main_safety_workspace,
        out_dir=out_dir,
    )


def run_worker(
    repo_root: str | Path = ".",
    *,
    post_main_safety_workspace: str | Path = "outputs/post_main_local_validation_live_runner_safety",
    out_dir: str | Path = "outputs/human_main_merge_review_gate",
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        repo_root=repo_root,
        post_main_safety_workspace=post_main_safety_workspace,
        out_dir=out_dir,
        **kwargs,
    )
