from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.final_todo_integration_readiness import write_final_todo_readiness_outputs


def run(
    repo_root: str | Path = ".",
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    out_dir: str | Path = "outputs/final_todo_integration_readiness",
    **_: Any,
) -> dict[str, Any]:
    """Create final TODO and integration readiness reports."""

    return write_final_todo_readiness_outputs(
        repo_root=repo_root,
        workspace=workspace,
        out_dir=out_dir,
    )


def run_worker(
    repo_root: str | Path = ".",
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    out_dir: str | Path = "outputs/final_todo_integration_readiness",
    **kwargs: Any,
) -> dict[str, Any]:
    return run(repo_root=repo_root, workspace=workspace, out_dir=out_dir, **kwargs)
