from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.main_readiness_local_validation_planner import write_main_readiness_plan_outputs


def run(
    repo_root: str | Path = ".",
    final_review_workspace: str | Path = "outputs/final_review_pipeline_verify",
    *,
    out_dir: str | Path = "outputs/main_readiness_local_validation",
    **_: Any,
) -> dict[str, Any]:
    """Generate main-readiness and local-only validation planning artifacts."""

    return write_main_readiness_plan_outputs(
        repo_root=repo_root,
        final_review_workspace=final_review_workspace,
        out_dir=out_dir,
    )


def run_worker(
    repo_root: str | Path = ".",
    final_review_workspace: str | Path = "outputs/final_review_pipeline_verify",
    *,
    out_dir: str | Path = "outputs/main_readiness_local_validation",
    **kwargs: Any,
) -> dict[str, Any]:
    return run(repo_root=repo_root, final_review_workspace=final_review_workspace, out_dir=out_dir, **kwargs)
