from __future__ import annotations

from pydantic import BaseModel, Field


class RawLine(BaseModel):
    id: str
    p1: list[float]
    p2: list[float]
    angle: float
    length: float
    confidence: float = Field(ge=0.0, le=1.0)
    source: str


class RawLineResult(BaseModel):
    lines: list[RawLine] = Field(default_factory=list)

