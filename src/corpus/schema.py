from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

RecordStatus = Literal['ok', 'failed', 'unavailable']


@dataclass
class FileizedDrawingRecord:
    """Stable JSON shape produced by every HS-CAD fileizer.

    The first corpus milestone is schema stability, not perfect extraction.
    Every engine should return this shape so indexing, query, and reports can
    operate without knowing whether the source was DWG, DXF, PDF, or image.
    """

    file_id: str
    source_path: str
    relative_path: str
    extension: str
    status: RecordStatus
    engine: str
    layers: list[dict[str, Any]] = field(default_factory=list)
    blocks: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    texts: list[dict[str, Any]] = field(default_factory=list)
    dimensions: list[dict[str, Any]] = field(default_factory=list)
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
        error_type: str = 'fileize_failed',
    ) -> 'FileizedDrawingRecord':
        return cls(
            file_id=file_id,
            source_path=str(source_path),
            relative_path=str(relative_path),
            extension=extension.lower(),
            status='failed',
            engine=engine,
            errors=[{'type': error_type, 'reason': reason}],
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
    ) -> 'FileizedDrawingRecord':
        return cls(
            file_id=file_id,
            source_path=str(source_path),
            relative_path=str(relative_path),
            extension=extension.lower(),
            status='unavailable',
            engine=engine,
            warnings=[{'type': 'engine_unavailable', 'reason': reason}],
        )


def normalize_entity_text(entity: dict[str, Any]) -> str | None:
    text = entity.get('text') or entity.get('TextString') or entity.get('contents')
    if text is None:
        return None
    text = str(text).strip()
    return text or None


def layer_rows_from_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in entities:
        layer = str(item.get('layer') or item.get('Layer') or '0')
        counts[layer] = counts.get(layer, 0) + 1
    return [{'name': name, 'entity_count': count} for name, count in sorted(counts.items())]


def text_rows_from_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in entities:
        text = normalize_entity_text(item)
        if not text:
            continue
        rows.append(
            {
                'handle': item.get('handle'),
                'layer': item.get('layer') or item.get('Layer'),
                'entity_type': item.get('entity_type') or item.get('type'),
                'text': text,
                'insert': item.get('insert') or item.get('point'),
            }
        )
    return rows


def block_rows_from_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in entities:
        kind = str(item.get('entity_type') or item.get('type') or '').upper()
        if kind not in {'INSERT', 'BLOCK', 'INSERTREF'}:
            continue
        name = str(item.get('effective_name') or item.get('name') or item.get('block_name') or '').strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
    return [{'name': name, 'count': count} for name, count in sorted(counts.items())]


def dimension_rows_from_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in entities:
        kind = str(item.get('entity_type') or item.get('type') or '').upper()
        if kind != 'DIMENSION':
            continue
        rows.append(
            {
                'handle': item.get('handle'),
                'layer': item.get('layer'),
                'measurement': item.get('measurement'),
                'text_override': item.get('text_override'),
                'text_position': item.get('text_position'),
            }
        )
    return rows
