from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_execution_audit_log(
    *,
    package: dict[str, Any],
    dry_run_result: dict[str, Any] | None = None,
    execution_result: dict[str, Any] | None = None,
    before_scan: dict[str, Any] | None = None,
    after_scan: dict[str, Any] | None = None,
    delta_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "created_at": utc_now_iso(),
        "package_status": package.get("status"),
        "package_mode": package.get("mode"),
        "original_dwg": package.get("original_dwg"),
        "working_copy_dwg": package.get("working_copy_dwg"),
        "save_as_target": package.get("save_as_target"),
        "operator_approved": package.get("operator_approved"),
        "dry_run_result": dry_run_result,
        "execution_result": execution_result,
        "before_scan": before_scan,
        "after_scan": after_scan,
        "delta_report": delta_report,
        "safety": {
            "original_dwg_mutation_allowed": False,
            "save_as_required": True,
            "human_approval_required": True,
        },
    }
