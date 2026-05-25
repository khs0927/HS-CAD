from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.main_merge_readiness_decision import write_main_merge_decision_outputs


def run(
    repo_root: str | Path = ".",
    post_pr53_workspace: str | Path = "outputs/post_pr53_main_merge_local_validation",
    *,
    out_dir: str | Path = "outputs/main_merge_readiness_decision",
    **_: Any,
) -> dict[str, Any]:
    """Generate main merge readiness decision artifacts."""

    return write_main_merge_decision_outputs(
        repo_root=repo_root,
        post_pr53_workspace=post_pr53_workspace,
        out_dir=out_dir,
    )


def run_worker(
    repo_root: str | Path = ".",
    post_pr53_workspace: str | Path = "outputs/post_pr53_main_merge_local_validation",
    *,
    out_dir: str | Path = "outputs/main_merge_readiness_decision",
    **kwargs: Any,
) -> dict[str, Any]:
    return run(repo_root=repo_root, post_pr53_workspace=post_pr53_workspace, out_dir=out_dir, **kwargs)
