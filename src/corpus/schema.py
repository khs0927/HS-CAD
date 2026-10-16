from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from src.corpus.text_extraction import text_rows_from_entities_v2

RecordStatus = Literal["ok", "failed", "unavailable"]


@dataclass
class FileizedDrawingRecord:
    """Stable, versioned corpus record produced by every HS-CAD fileizer."""

    file_id: str
    source_path: str
    relative_path: str
    extension: str
    status: RecordStatus
    engine: str
    schema_version: int = 2
    layers: list[dict[str, Any]] = field(default_factory=list)
    blocks: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    texts: list[dict[str, Any]] = field(default_factory=list)
    dimensions: list[dict[str, Any]] = field(default_factory=list)
    layouts: list[dict[str, Any]] = field(default_factory=list)
    xrefs: list[dict[str, Any]] = field(default_factory=list)
    extraction_report: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def failed(
        cls,
        *,
        file_id: str,
        source_path: str | Path,
        relative_path: str | Path,
        extension: str,
        engine: str,
        reason: str,
        error_type: str = "fileize_failed",
    ) -> "FileizedDrawingRecord":
        return cls(
            file_id=file_id,
            source_path=str(source_path),
            relative_path=str(relative_path),
            extension=extension.lower(),
            status="failed",
            engine=engine,
            extraction_report={
                "schema_version": 2,
                "complete": False,
                "failure_reason": reason,
            },
            errors=[{"type": error_type, "reason": reason}],
        )

    @classmethod
    def unavailable(
        cls,
        *,
        file_id: str,
        source_path: str | Path,
        relative_path: str | Path,
        extension: str,
        engine: str,
        reason: str,
    ) -> "FileizedDrawingRecord":
        return cls(
            file_id=file_id,
            source_path=str(source_path),
            relative_path=str(relative_path),
            extension=extension.lower(),
            status="unavailable",
            engine=engine,
            extraction_report={
                "schema_version": 2,
                "complete": False,
                "failure_reason": reason,
            },
            warnings=[{"type": "engine_unavailable", "reason": reason}],
        )


def normalize_entity_text(entity: dict[str, Any]) -> str | None:
    text = (
        entity.get("plain_text")
        or entity.get("text")
        or entity.get("TextString")
        or entity.get("contents")
    )
    if text is None:
        return None
    text = str(text).strip()
    return text or None


def layer_rows_from_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = {}
    for item in entities:
        layer = str(item.get("layer") or item.get("Layer") or "0")
        layout = str(item.get("layout") or "Model")
        key = (layout, layer)
        counts[key] = counts.get(key, 0) + 1
    return [
        {"layout": layout, "name": name, "entity_count": count}
        for (layout, name), count in sorted(counts.items())
    ]


def text_rows_from_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return text_rows_from_entities_v2(entities)


def block_rows_from_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = {}
    for item in entities:
        kind = str(item.get("entity_type") or item.get("type") or "").upper()
        if kind not in {"INSERT", "BLOCK", "INSERTREF"}:
            continue
        name = str(
            item.get("effective_name")
            or item.get("name")
            or item.get("block_name")
            or ""
        ).strip()
        if not name:
            continue
        layout = str(item.get("layout") or "Model")
        key = (layout, name)
        counts[key] = counts.get(key, 0) + 1
    return [
        {"layout": layout, "name": name, "count": count}
        for (layout, name), count in sorted(counts.items())
    ]


def dimension_rows_from_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in entities:
        kind = str(item.get("entity_type") or item.get("type") or "").upper()
        if "DIMENSION" not in kind:
            continue
        rows.append(
            {
                "handle": item.get("handle"),
                "layer": item.get("layer"),
                "layout": item.get("layout") or "Model",
                "measurement": item.get("measurement"),
                "text_override": item.get("text_override"),
                "display_text": item.get("display_text"),
                "text_position": item.get("text_position"),
                "block_path": item.get("block_path") or [],
            }
        )
    return rows
