from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class XicadRisk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class XicadCategory(str, Enum):
    wall = "wall"
    column = "column"
    beam = "beam"
    steel = "steel"
    door = "door"
    window = "window"
    stair = "stair"
    elevator = "elevator"
    parking = "parking"
    insulation = "insulation"
    annotation = "annotation"
    utility = "utility"
    unknown = "unknown"


class XicadAlias(BaseModel):
    """A single XiCAD command alias that is safe to expose to AI."""

    alias: str = Field(..., min_length=1)
    name: str = ""
    category: XicadCategory = XicadCategory.unknown
    description: str = ""
    interactive_required: bool = True
    risk: XicadRisk = XicadRisk.medium
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, value: str) -> str:
        return value.strip().upper()


class XicadSafety(BaseModel):
    backup_required: bool = True
    preview_required: bool = True
    allow_interactive: bool = False
    allow_high_risk: bool = False


class XicadSafeCommand(BaseModel):
    """Validated command emitted by an AI planner for XiCAD integration."""

    command: Literal["xicad_safe_plan", "xicad_safe_execute"]
    alias: str = Field(..., min_length=1)
    load_first: bool = True
    dry_run: bool = True
    params: dict[str, Any] = Field(default_factory=dict)
    safety: XicadSafety = Field(default_factory=XicadSafety)

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, value: str) -> str:
        return value.strip().upper()


class XicadExecutionPlan(BaseModel):
    alias: str
    alias_name: str = ""
    category: XicadCategory = XicadCategory.unknown
    risk: XicadRisk = XicadRisk.medium
    interactive_required: bool = True
    can_execute: bool = False
    dry_run: bool = True
    load_first: bool = True
    commands_to_send: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
