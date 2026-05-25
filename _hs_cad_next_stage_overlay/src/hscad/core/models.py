"""Shared data models for fileized drawing content."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hscad.core.evidence import Evidence


@dataclass
class DrawingEntity:
    entity_id: str
    entity_type: str
    layer: str = "0"
    geometry: dict[str, Any] = field(default_factory=dict)
    text: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "layer": self.layer,
            "geometry": self.geometry,
            "text": self.text,
            "raw": self.raw,
        }


@dataclass
class FileizedDrawing:
    input_path: str
    input_type: str
    normalized_path: str | None = None
    entities: list[DrawingEntity] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_evidence(self, evidence: Evidence) -> None:
        self.evidence.append(evidence)

    @property
    def path(self) -> Path:
        return Path(self.normalized_path or self.input_path)

    def to_record(self) -> dict[str, Any]:
        return {
            "input_path": self.input_path,
            "input_type": self.input_type,
            "normalized_path": self.normalized_path,
            "metadata": self.metadata,
            "entities": [entity.to_record() for entity in self.entities],
            "evidence": [item.to_record() for item in self.evidence],
        }
