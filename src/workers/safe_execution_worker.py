from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.execution.execution_audit import build_execution_audit_log
from src.execution.safe_execution_package_builder import build_safe_execution_package
from src.execution.zwcad_xicad_safe_executor import ZWCADXiCADSafeExecutor
from src.reports.json_exporter import export_json


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def run_safe_execution_dry_run_worker(
    *,
    command_plan_json: str | Path,
    review_gate_json: str | Path,
    signoff_manifest_json: str | Path,
    out_dir: str | Path = "outputs/safe_execution",
    original_dwg: str = "",
    working_copy_dwg: str = "",
    save_as_target: str = "",
) -> dict[str, Any]:
    command_plan = _load_json(command_plan_json)
    review_gate = _load_json(review_gate_json)
    signoff_manifest = _load_json(signoff_manifest_json)

    package = build_safe_execution_package(
        command_plan,
        review_gate,
        signoff_manifest,
        source_command_plan=str(command_plan_json),
        source_review_gate=str(review_gate_json),
        mode="dry_run",
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
    )

    executor = ZWCADXiCADSafeExecutor()
    dry_run = executor.dry_run(package)
    audit = build_execution_audit_log(package=package.to_dict(), dry_run_result=dry_run)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    package_json = out / "SAFE_EXECUTION_PACKAGE.json"
    dry_run_json = out / "SAFE_EXECUTION_DRY_RUN_RESULT.json"
    audit_json = out / "EXECUTION_AUDIT_LOG.json"

    export_json(package.to_dict(), package_json)
    export_json(dry_run, dry_run_json)
    export_json(audit, audit_json)

    return {
        "out_dir": str(out),
        "package_json": str(package_json),
        "dry_run_json": str(dry_run_json),
        "audit_json": str(audit_json),
        "status": package.status,
        "mode": package.mode,
        "step_count": len(package.steps),
        "blocked_count": len(package.blocked_reasons),
    }
