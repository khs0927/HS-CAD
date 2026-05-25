from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.phase10_domain_decision_connector import write_phase10_outputs
from src.analysis.phase11_copied_dwg_validation_bridge import write_phase11_outputs


def run(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    original_dwg: str | Path | None = None,
    working_copy_dwg: str | Path | None = None,
    save_as_target: str | Path | None = None,
    out_dir: str | Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Run Phase 10~11 review-only domain/copy validation bridge."""

    workspace_path = Path(workspace)
    target = Path(out_dir) if out_dir else workspace_path
    target.mkdir(parents=True, exist_ok=True)

    phase10 = write_phase10_outputs(workspace_path, out_dir=target)
    phase11 = write_phase11_outputs(
        workspace_path,
        phase10_connector_path=target / "PHASE10_DOMAIN_DECISION_CONNECTOR.json",
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        out_dir=target,
    )

    return {
        "status": phase11["status"],
        "workspace": str(workspace_path),
        "out_dir": str(target),
        "phase10": phase10,
        "phase11": phase11,
        "safety": phase11["safety"],
    }


def run_worker(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    original_dwg: str | Path | None = None,
    working_copy_dwg: str | Path | None = None,
    save_as_target: str | Path | None = None,
    out_dir: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return run(
        workspace=workspace,
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        out_dir=out_dir,
        **kwargs,
    )
