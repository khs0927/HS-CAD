from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.post_pr53_main_merge_local_validation import write_post_pr53_outputs


def run(
    repo_root: str | Path = ".",
    main_readiness_workspace: str | Path = "outputs/main_readiness_local_validation",
    *,
    out_dir: str | Path = "outputs/post_pr53_main_merge_local_validation",
    **_: Any,
) -> dict[str, Any]:
    """Generate Post-PR53 main merge and local-only validation planning artifacts."""

    return write_post_pr53_outputs(
        repo_root=repo_root,
        main_readiness_workspace=main_readiness_workspace,
        out_dir=out_dir,
    )


def run_worker(
    repo_root: str | Path = ".",
    main_readiness_workspace: str | Path = "outputs/main_readiness_local_validation",
    *,
    out_dir: str | Path = "outputs/post_pr53_main_merge_local_validation",
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        repo_root=repo_root,
        main_readiness_workspace=main_readiness_workspace,
        out_dir=out_dir,
        **kwargs,
    )
