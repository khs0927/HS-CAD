from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class DxfEntityInfo:
    handle: str | None
    dxftype: str
    layer: str | None
    color: int | None = None
    linetype: str | None = None


@dataclass
class DxfRewriteAction:
    handle: str | None
    dxftype: str
    old_layer: str | None
    new_layer: str | None
    reason: str
    applied: bool = False


@dataclass
class DxfRewriteReport:
    source_dxf: str
    output_dxf: str | None
    generated_at: str = field(default_factory=now_iso)
    ezdxf_available: bool = False
    source_exists: bool = False
    copied_without_rewrite: bool = False
    inspected_count: int = 0
    actions: list[DxfRewriteAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
