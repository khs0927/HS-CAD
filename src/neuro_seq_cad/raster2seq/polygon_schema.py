from __future__ import annotations

from pydantic import BaseModel, Field


class PolygonPrediction(BaseModel):
    id: str
    type: str
    label: str
    points: list[list[float]]
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = "raster2seq"


class Raster2SeqResult(BaseModel):
    polygons: list[PolygonPrediction] = Field(default_factory=list)

