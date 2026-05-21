from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class MergeGroup:
    group: str
    action: str
    target_layer: str | None
    confidence: float
    count: int


@dataclass
class MergeCandidatePlan:
    mode: str = "plan_only"
    generated_at: str = field(default_factory=now_iso)
    can_merge: bool = False
    requires_user_approval: bool = True
    source_preview_session: str | None = None
    merge_groups: list[MergeGroup] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=lambda: ["save", "purge", "explode_block_definition"])
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
