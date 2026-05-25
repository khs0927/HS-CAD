from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


FileizedStatus = Literal["ok", "failed", "unavailable"]


@dataclass(frozen=True)
class FileizedEntity:
    entity_type: str
    layer: str = "0"
    handle: str | None = None
    geometry: dict[str, Any] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FileizedDrawing:
    source_path: str
    source_type: str
    status: FileizedStatus
    engine: str
    normalized_entities: list[FileizedEntity] = field(default_factory=list)
    layers: list[dict[str, Any]] = field(default_factory=list)
    texts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    safety: dict[str, bool] = field(
        default_factory=lambda: {
            "cad_execution": False,
            "zwcad_com": False,
            "sendcommand": False,
            "source_mutation": False,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["normalized_entities"] = [entity.to_dict() for entity in self.normalized_entities]
        return payload

    @classmethod
    def unavailable(cls, path: str | Path, *, source_type: str, engine: str, reason: str) -> "FileizedDrawing":
        return cls(
            source_path=str(path),
            source_type=source_type,
            status="unavailable",
            engine=engine,
            warnings=[{"type": "engine_unavailable", "reason": reason}],
        )

    @classmethod
    def failed(cls, path: str | Path, *, source_type: str, engine: str, reason: str) -> "FileizedDrawing":
        return cls(
            source_path=str(path),
            source_type=source_type,
            status="failed",
            engine=engine,
            errors=[{"type": "fileize_failed", "reason": reason}],
        )


def layer_counts(entities: list[FileizedEntity]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for entity in entities:
        counts[entity.layer] = counts.get(entity.layer, 0) + 1
    return [{"name": name, "entity_count": count} for name, count in sorted(counts.items())]

