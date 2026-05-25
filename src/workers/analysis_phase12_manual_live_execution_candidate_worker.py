from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.phase12_manual_live_execution_candidate import write_phase12_outputs


def run(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    phase11_plan_path: str | Path | None = None,
    allowlist_plan_path: str | Path | None = None,
    alias: str = "WAL",
    manual_live_flag: bool = False,
    operator_approved: bool = False,
    out_dir: str | Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Create Phase 12 manual-only live execution candidate artifacts.

    This worker does not execute CAD. It only verifies preconditions and writes guard artifacts.
    """

    return write_phase12_outputs(
        workspace,
        phase11_plan_path=phase11_plan_path,
        allowlist_plan_path=allowlist_plan_path,
        alias=alias,
        manual_live_flag=manual_live_flag,
        operator_approved=operator_approved,
        out_dir=out_dir,
    )


def run_worker(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    phase11_plan_path: str | Path | None = None,
    allowlist_plan_path: str | Path | None = None,
    alias: str = "WAL",
    manual_live_flag: bool = False,
    operator_approved: bool = False,
    out_dir: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        workspace=workspace,
        phase11_plan_path=phase11_plan_path,
        allowlist_plan_path=allowlist_plan_path,
        alias=alias,
        manual_live_flag=manual_live_flag,
        operator_approved=operator_approved,
        out_dir=out_dir,
        **kwargs,
    )
