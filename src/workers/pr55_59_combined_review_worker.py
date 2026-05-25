from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.pr55_59_combined_review import write_outputs


def run(
    repo_root: str | Path = ".",
    *,
    out_dir: str | Path = "outputs/pr55_59_combined_review",
    **_: Any,
) -> dict[str, Any]:
    """Generate PR #55~#59 combined review package. Does not merge main."""

    return write_outputs(repo_root=repo_root, out_dir=out_dir)


def run_worker(**kwargs: Any) -> dict[str, Any]:
    return run(**kwargs)
