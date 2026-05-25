from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.phase7_domain_decision_package_bridge import write_phase7_outputs
from src.analysis.phase8_review_gate_chain_bridge import write_phase8_outputs
from src.analysis.phase9_pipeline_readiness_summary import write_phase9_outputs


def run(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    out_dir: str | Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Run Phase 7~9 review-only pipeline bundle."""

    workspace_path = Path(workspace)
    target = Path(out_dir) if out_dir else workspace_path
    target.mkdir(parents=True, exist_ok=True)

    phase7 = write_phase7_outputs(workspace_path, out_dir=target)
    phase8 = write_phase8_outputs(workspace_path, phase7_package_path=target / "PHASE7_DOMAIN_DECISION_PACKAGE.json", out_dir=target)
    phase9 = write_phase9_outputs(target, out_dir=target)

    return {
        "status": phase9["status"],
        "workspace": str(workspace_path),
        "out_dir": str(target),
        "phase7": phase7,
        "phase8": phase8,
        "phase9": phase9,
        "safety": phase9["safety"],
    }


def run_worker(
    workspace: str | Path = "outputs/webhard_batch_100",
    *,
    out_dir: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return run(workspace=workspace, out_dir=out_dir, **kwargs)
