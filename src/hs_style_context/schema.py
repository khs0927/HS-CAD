from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class StyleSource:
    path: str
    source_type: str
    exists: bool
    loaded: bool
    warnings: list[str] = field(default_factory=list)


@dataclass
class LayerPreference:
    role: str
    preferred_layer: str | None
    fallback_layer: str | None = None
    confidence: float = 0.0
    source: str = "unknown"
    reason: str = ""


@dataclass
class LineStylePreference:
    role: str
    color: str | int | None = None
    linetype: str | None = None
    lineweight: str | int | None = None
    by_layer_ratio: float | None = None
    confidence: float = 0.0
    source: str = "unknown"


@dataclass
class TextStylePreference:
    role: str
    layer: str | None = None
    text_style: str | None = None
    height: float | None = None
    rotation: float | None = None
    confidence: float = 0.0
    source: str = "unknown"


@dataclass
class DimensionStylePreference:
    role: str
    layer: str | None = None
    dimstyle: str | None = None
    text_height: float | None = None
    arrow_size: float | None = None
    confidence: float = 0.0
    source: str = "unknown"


@dataclass
class BlockPreference:
    role: str
    block_name: str | None = None
    effective_name: str | None = None
    layer: str | None = None
    confidence: float = 0.0
    source: str = "unknown"


@dataclass
class SheetContext:
    sheet_block_name: str | None = None
    insert_layer: str | None = None
    insert_scale: float | None = None
    representative_usable_area: list[float] | None = None
    title_block_bbox: list[float] | None = None
    needs_visual_check: bool = True
    confidence: float = 0.0
    source: str = "unknown"


@dataclass
class StyleContext:
    version: str = "stage23-style-context-v1"
    generated_at: str = field(default_factory=now_iso)
    sources: list[StyleSource] = field(default_factory=list)
    layer_preferences: list[LayerPreference] = field(default_factory=list)
    line_style_preferences: list[LineStylePreference] = field(default_factory=list)
    text_style_preferences: list[TextStylePreference] = field(default_factory=list)
    dimension_style_preferences: list[DimensionStylePreference] = field(default_factory=list)
    block_preferences: list[BlockPreference] = field(default_factory=list)
    sheet_context: SheetContext | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StyleResolveRequest:
    element_type: str
    role: str | None = None
    nearby_handle: str | None = None
    user_layer: str | None = None
    user_style: dict[str, Any] | None = None
    confidence: float | None = None
    mode: str = "existing_dwg_preview"


@dataclass
class StyleResolveResult:
    element_type: str
    target_layer: str
    color: str | int | None = None
    linetype: str | None = None
    lineweight: str | int | None = None
    text_style: str | None = None
    text_height: float | None = None
    dimstyle: str | None = None
    block_name: str | None = None
    needs_review: bool = False
    confidence: float = 0.0
    reason: str = ""
    source: str = "fallback"


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {key: to_dict(value) for key, value in obj.items()}
    return obj
