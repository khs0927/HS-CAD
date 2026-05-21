from __future__ import annotations

from pydantic import BaseModel, Field


class SymbolPrediction(BaseModel):
    id: str
    type: str
    bbox: list[float]
    confidence: float = Field(ge=0.0, le=1.0)
    source: str


class SymbolDetectionResult(BaseModel):
    symbols: list[SymbolPrediction] = Field(default_factory=list)

