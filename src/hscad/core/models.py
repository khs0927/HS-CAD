"""Core serializable models for HS-CAD main-code pipeline.

The models are deliberately dependency-light so they can be used by fileizers,
analyzers, fusion, rule engines, reports and tests without importing CAD apps.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


JsonDict = dict[str, Any]
Point2D = tuple[float, float]


@dataclass(frozen=True)
class DrawingEntity:
    """Normalized drawing entity extracted from DXF/image/PDF inputs."""

    entity_id: str
    entity_type: str
    layer: str = "0"
    geometry: JsonDict = field(default_factory=dict)
    text: str | None = None
    raw: JsonDict = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "unknown"

    def to_record(self) -> JsonDict:
        return asdict(self)

    @property
    def points(self) -> list[Point2D]:
        pts = self.geometry.get("points")
        if isinstance(pts, list):
            out: list[Point2D] = []
            for pt in pts:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    out.append((float(pt[0]), float(pt[1])))
            return out
        start = self.geometry.get("start")
        end = self.geometry.get("end")
        if isinstance(start, (list, tuple)) and isinstance(end, (list, tuple)):
            return [(float(start[0]), float(start[1])), (float(end[0]), float(end[1]))]
        return []


@dataclass(frozen=True)
class FileizedDrawing:
    """Common output of all fileizers."""

    input_path: str
    source_format: str
    entities: list[DrawingEntity] = field(default_factory=list)
    metadata: JsonDict = field(default_factory=dict)
    evidence: list[Any] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    converted_path: str | None = None

    def to_record(self) -> JsonDict:
        return {
            "input_path": self.input_path,
            "source_format": self.source_format,
            "converted_path": self.converted_path,
            "metadata": self.metadata,
            "warnings": self.warnings,
            "entities": [e.to_record() for e in self.entities],
            "evidence": [e.to_record() if hasattr(e, "to_record") else e for e in self.evidence],
        }

    @property
    def input_name(self) -> str:
        return Path(self.input_path).name
