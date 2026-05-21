from __future__ import annotations

from pydantic import BaseModel, Field


CONFLICT_RULES = {
    "geometry_precision": ["Raster2Seq polygon", "OpenCV", "MLSD", "PlanParser bbox", "VLM"],
    "semantic_priority": ["VLM", "PlanParser", "Raster2Seq raw label", "OpenCV"],
    "dimension_priority": ["OCR dimension", "titleblock scale", "door heuristic", "VLM guess"],
    "wall_topology": ["Raster2Seq polygon", "double-line detector", "single Hough line"],
}


class EvidenceEntity(BaseModel):
    id: str
    entity_type: str
    geometry: dict
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class EvidenceGraph(BaseModel):
    entities: list[EvidenceEntity] = Field(default_factory=list)
    scale: float = 1.0
    scale_source: str = "identity"
    warnings: list[str] = Field(default_factory=list)

