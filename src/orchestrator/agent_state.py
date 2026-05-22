from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TaskContext:
    """Normalized user task context."""

    task: str
    has_image: bool = False
    has_pdf: bool = False
    has_dwg: bool = False
    has_active_drawing: bool = False
    wants_write: bool = False
    wants_xicad: bool = False
    wants_steel: bool = False
    image_path: str | None = None
    dwg_path: str | None = None
    out_dir: str = "outputs/agent_route"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionTrace:
    stage: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentRunState:
    context: TaskContext
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    traces: list[DecisionTrace] = field(default_factory=list)

    def add_trace(self, stage: str, message: str, **data: Any) -> None:
        self.traces.append(DecisionTrace(stage=stage, message=message, data=data))

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "context": self.context.to_dict(),
            "traces": [trace.to_dict() for trace in self.traces],
        }


def normalize_context(
    task: str,
    *,
    has_image: bool = False,
    has_pdf: bool = False,
    has_dwg: bool = False,
    has_active_drawing: bool = False,
    wants_write: bool = False,
    image_path: str | Path | None = None,
    dwg_path: str | Path | None = None,
    out_dir: str | Path = "outputs/agent_route",
) -> TaskContext:
    text = task.lower()
    inferred_image = has_image or has_pdf or image_path is not None or any(
        token in text for token in ("image", "pdf", "scan", "scanned", "floorplan", "이미지", "스캔")
    )
    inferred_dwg = has_dwg or has_active_drawing or dwg_path is not None or any(token in text for token in ("dwg", "zwcad"))
    inferred_write = wants_write or any(
        token in text for token in ("execute", "write", "save", "modify", "change", "insert", "delete", "purge", "explode", "수정", "변경", "삽입", "저장", "삭제")
    )
    wants_xicad = any(
        token in text for token in ("xicad", "layer", "area", "quantity", "dimension", "text", "벽체", "문", "창", "계단", "레이어", "면적", "수량", "문자", "치수")
    )
    wants_steel = any(token in text for token in ("hssteel", "beam", "steel", "column", "h-beam", "철골", "보", "기둥"))

    return TaskContext(
        task=task,
        has_image=inferred_image,
        has_pdf=has_pdf or "pdf" in text,
        has_dwg=inferred_dwg,
        has_active_drawing=has_active_drawing,
        wants_write=inferred_write,
        wants_xicad=wants_xicad,
        wants_steel=wants_steel,
        image_path=str(image_path) if image_path else None,
        dwg_path=str(dwg_path) if dwg_path else None,
        out_dir=str(out_dir),
    )
