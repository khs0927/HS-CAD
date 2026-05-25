from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.pr55_main_ready_review_only_validator import write_pr55_validation_outputs


def run(
    repo_root: str | Path = ".",
    *,
    out_dir: str | Path = "outputs/pr55_main_ready_review_only_validation",
    **_: Any,
) -> dict[str, Any]:
    """Generate PR55 main-ready review-only validation artifacts."""

    return write_pr55_validation_outputs(repo_root=repo_root, out_dir=out_dir)


def run_worker(
    repo_root: str | Path = ".",
    *,
    out_dir: str | Path = "outputs/pr55_main_ready_review_only_validation",
    **kwargs: Any,
) -> dict[str, Any]:
    return run(repo_root=repo_root, out_dir=out_dir, **kwargs)
