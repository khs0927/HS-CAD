from __future__ import annotations

from pathlib import Path
from typing import Any

from src.execution.drawing_delta import build_delta_report
from src.execution.scan_snapshot import build_scan_snapshot, DrawingScanSnapshot


class ZWCADCopyValidationError(RuntimeError):
    pass


def scan_working_copy(adapter: Any, working_copy_dwg: str) -> DrawingScanSnapshot:
    if not working_copy_dwg:
        raise ZWCADCopyValidationError("working_copy_dwg is required.")
    return build_scan_snapshot(adapter, working_copy_dwg)


def save_as_copy_result(adapter: Any, save_as_target: str) -> None:
    if not save_as_target:
        raise ZWCADCopyValidationError("save_as_target is required.")
    Path(save_as_target).parent.mkdir(parents=True, exist_ok=True)
    adapter.save_as(save_as_target)


def build_before_after_delta(before_snapshot: DrawingScanSnapshot, after_snapshot: DrawingScanSnapshot) -> dict[str, Any]:
    return build_delta_report(before_snapshot.objects, after_snapshot.objects)
