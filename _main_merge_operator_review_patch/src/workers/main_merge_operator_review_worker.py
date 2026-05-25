from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.main_merge_operator_review import write_main_merge_operator_review_outputs


def run(
    repo_root: str | Path = ".",
    *,
    pr56_workspace: str | Path = "outputs/pr55_main_ready_review_only_validation",
    out_dir: str | Path = "outputs/main_merge_operator_review",
    **_: Any,
) -> dict[str, Any]:
    """Generate main merge operator review artifacts."""

    return write_main_merge_operator_review_outputs(
        repo_root=repo_root,
        pr56_workspace=pr56_workspace,
        out_dir=out_dir,
    )


def run_worker(
    repo_root: str | Path = ".",
    *,
    pr56_workspace: str | Path = "outputs/pr55_main_ready_review_only_validation",
    out_dir: str | Path = "outputs/main_merge_operator_review",
    **kwargs: Any,
) -> dict[str, Any]:
    return run(repo_root=repo_root, pr56_workspace=pr56_workspace, out_dir=out_dir, **kwargs)
