from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.phase6_domain_rule_workflow_adapter import write_phase6_adapter_outputs


def run(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    phase5_package_path: str | Path | None = None,
    out_dir: str | Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Create review-only Phase 6 Domain Rule Workflow adapter artifacts."""

    return write_phase6_adapter_outputs(
        workspace,
        phase5_package_path=phase5_package_path,
        out_dir=out_dir,
    )


def run_worker(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    phase5_package_path: str | Path | None = None,
    out_dir: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        workspace=workspace,
        phase5_package_path=phase5_package_path,
        out_dir=out_dir,
        **kwargs,
    )


def main(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    phase5_package_path: str | Path | None = None,
    out_dir: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        workspace=workspace,
        phase5_package_path=phase5_package_path,
        out_dir=out_dir,
        **kwargs,
    )
