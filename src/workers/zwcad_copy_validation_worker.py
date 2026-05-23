from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from src.execution.dwg_copy_manager import prepare_working_copy
from src.execution.execution_audit import build_execution_audit_log
from src.execution.scan_snapshot import build_scan_snapshot
from src.execution.zwcad_copy_validation import build_before_after_delta, save_as_copy_result
from src.reports.json_exporter import export_json


AdapterFactory = Callable[[], Any]


def run_copy_scan_validation_worker(
    *,
    original_dwg: str,
    working_copy_dwg: str,
    out_dir: str | Path = "outputs/zwcad_copy_validation",
    adapter_factory: AdapterFactory,
    overwrite_copy: bool = False,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest = prepare_working_copy(
        original_dwg,
        working_copy_dwg=working_copy_dwg,
        overwrite_copy=overwrite_copy,
    )

    adapter = adapter_factory()
    before = build_scan_snapshot(adapter, manifest.working_copy_dwg)
    audit = build_execution_audit_log(
        package={
            "status": "scan_only",
            "mode": "copy_validation",
            "original_dwg": manifest.original_dwg,
            "working_copy_dwg": manifest.working_copy_dwg,
            "save_as_target": manifest.save_as_target,
            "operator_approved": False,
        },
        before_scan=before.to_dict(),
    )

    manifest_path = out / "COPY_MANIFEST.json"
    before_path = out / "BEFORE_SCAN.json"
    audit_path = out / "EXECUTION_AUDIT_LOG.json"

    export_json(manifest.to_dict(), manifest_path)
    export_json(before.to_dict(), before_path)
    export_json(audit, audit_path)

    return {
        "out_dir": str(out),
        "copy_manifest": str(manifest_path),
        "before_scan": str(before_path),
        "audit_log": str(audit_path),
        "object_count": before.object_count,
        "status": "scan_only_complete",
    }


def run_copy_saveas_validation_worker(
    *,
    original_dwg: str,
    working_copy_dwg: str,
    save_as_target: str,
    out_dir: str | Path = "outputs/zwcad_copy_saveas_validation",
    adapter_factory: AdapterFactory,
    overwrite_copy: bool = False,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest = prepare_working_copy(
        original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        overwrite_copy=overwrite_copy,
    )

    adapter = adapter_factory()
    before = build_scan_snapshot(adapter, manifest.working_copy_dwg)
    save_as_copy_result(adapter, manifest.save_as_target)
    after = build_scan_snapshot(adapter, manifest.save_as_target)

    delta = build_before_after_delta(before, after)
    audit = build_execution_audit_log(
        package={
            "status": "saveas_validation",
            "mode": "copy_validation",
            "original_dwg": manifest.original_dwg,
            "working_copy_dwg": manifest.working_copy_dwg,
            "save_as_target": manifest.save_as_target,
            "operator_approved": False,
        },
        before_scan=before.to_dict(),
        after_scan=after.to_dict(),
        delta_report=delta,
    )

    manifest_path = out / "COPY_MANIFEST.json"
    before_path = out / "BEFORE_SCAN.json"
    after_path = out / "AFTER_SCAN.json"
    delta_path = out / "DELTA_REPORT.json"
    audit_path = out / "EXECUTION_AUDIT_LOG.json"

    export_json(manifest.to_dict(), manifest_path)
    export_json(before.to_dict(), before_path)
    export_json(after.to_dict(), after_path)
    export_json(delta, delta_path)
    export_json(audit, audit_path)

    return {
        "out_dir": str(out),
        "copy_manifest": str(manifest_path),
        "before_scan": str(before_path),
        "after_scan": str(after_path),
        "delta_report": str(delta_path),
        "audit_log": str(audit_path),
        "before_object_count": before.object_count,
        "after_object_count": after.object_count,
        "status": "saveas_validation_complete",
    }
