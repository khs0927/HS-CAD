from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.phase4_metrics_decision_bridge import write_phase4_bridge_outputs


def run(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    phase3_report_path: str | Path | None = None,
    out_dir: str | Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Create review-only Phase 4 metrics and decision bridge artifacts."""

    return write_phase4_bridge_outputs(
        workspace,
        phase3_report_path=phase3_report_path,
        out_dir=out_dir,
    )


def run_worker(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    phase3_report_path: str | Path | None = None,
    out_dir: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        workspace=workspace,
        phase3_report_path=phase3_report_path,
        out_dir=out_dir,
        **kwargs,
    )


def main(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    phase3_report_path: str | Path | None = None,
    out_dir: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        workspace=workspace,
        phase3_report_path=phase3_report_path,
        out_dir=out_dir,
        **kwargs,
    )
