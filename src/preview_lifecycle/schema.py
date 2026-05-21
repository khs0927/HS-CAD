from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_session_id() -> str:
    return "preview_" + datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid4().hex[:8]


@dataclass
class PreviewSession:
    session_id: str = field(default_factory=new_session_id)
    created_at: str = field(default_factory=now_iso)
    active_dwg: str | None = None
    source_dxf: str | None = None
    inserted_handle: str | None = None
    insert_layer: str = "QA-REVIEW"
    base_point: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale: float = 1.0
    rotation: float = 0.0
    undo_mark_created: bool = False
    saved: bool = False
    status: str = "planned"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreviewOperationResult:
    operation: str
    session_id: str | None
    allow_execute: bool = False
    executed: bool = False
    saved: bool = False
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
