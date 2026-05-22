from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ScanStrategy:
    name: str
    allowed: bool
    warning: str | None
    steps: list[str]


def recommend_scan_strategy(
    total_objects: int | None,
    requested_detail: str = "minimal",
    available_tools: Iterable[str] = (),
) -> ScanStrategy:
    """Choose a large-drawing scan strategy from object count and intent."""

    detail = (requested_detail or "minimal").lower()
    tools = {t.lower() for t in available_tools}
    count = total_objects if total_objects is not None else -1

    if detail == "full" and count >= 100_000:
        return ScanStrategy(
            name="native_audit_or_dxf_required",
            allowed=False,
            warning="COM full scan is unsafe for drawings above 100,000 objects.",
            steps=["fast-scan", "audit-native", "index-dxf", "targeted execution"],
        )
    if detail == "full" and count >= 20_000:
        return ScanStrategy(
            name="heavy_full_scan",
            allowed=False,
            warning="Full COM scan requires explicit --confirm-heavy on drawings above 20,000 objects.",
            steps=["fast-scan", "audit-native", "index-dxf if available", "full scan only when unavoidable"],
        )
    if count <= 5_000 or count < 0:
        return ScanStrategy(
            name="com_minimal_or_index",
            allowed=True,
            warning=None,
            steps=["scan --mode minimal", "scan --mode index", "targeted execution"],
        )
    if count <= 20_000:
        return ScanStrategy(
            name="fast_scan_targeted_com",
            allowed=True,
            warning="Prefer fast scan and targeted COM access over repeated full scans.",
            steps=["fast-scan", "scan-layer/window/selection", "handle-based execution"],
        )
    if "ezdxf" in tools or "oda" in tools:
        return ScanStrategy(
            name="native_audit_dxf_index",
            allowed=True,
            warning="Use native audit and DXF index before any detailed COM access.",
            steps=["audit-native", "index-dxf", "query-index", "handle-based execution"],
        )
    return ScanStrategy(
        name="native_audit_required",
        allowed=True,
        warning="Use native audit first; install ODA/ezdxf for offline indexing if repeated queries are needed.",
        steps=["fast-scan", "audit-native", "scan-window or scan-layer", "handle-based execution"],
    )
