from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.local_evidence_finalization_safety_spec_approval import write_local_evidence_finalization_outputs


def run(
    repo_root: str | Path = ".",
    *,
    out_dir: str | Path = "outputs/local_evidence_finalization_safety_spec_approval",
    **_: Any,
) -> dict[str, Any]:
    """Finalize local evidence and prepare safety spec approval artifacts. Does not execute CAD."""

    return write_local_evidence_finalization_outputs(repo_root=repo_root, out_dir=out_dir)


def run_worker(**kwargs: Any) -> dict[str, Any]:
    return run(**kwargs)
