"""Schema-aware helpers for legacy HS-CAD JSON artifacts.

The evidence bridge must accept outputs from several older analyzer/exporter
generations. Those outputs often contain the same semantic records under
different wrapper keys, for example ``{"data": {"layers": ...}}`` or
``{"result": {"inferences": ...}}``.

This module keeps that normalization review-only. It reads JSON-like Python
objects and returns summary metadata plus normalized record dictionaries. It
does not execute CAD commands, does not call COM, and does not mutate source
files.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from typing import Any, Iterable

Json = dict[str, Any]

COMMON_CONTAINER_KEYS: tuple[str, ...] = (
    "data",
    "result",
    "results",
    "payload",
    "items",
    "records",
    "artifacts",
    "analysis",
    "graph",
)

COMMON_RECORD_KEYS: tuple[str, ...] = (
    "entities",
    "layers",
    "layer_semantics",
    "texts",
    "text_roles",
    "inferences",
    "areas",
    "area_elements",
    "rooms",
    "issues",
    "warnings",
    "conflicts",
    "gaps",
    "recommendations",
    "rules",
    "domain_rules",
    "results",
)

ID_KEYS: tuple[str, ...] = (
    "id",
    "entity_id",
    "object_id",
    "uuid",
    "guid",
    "handle",
    "name",
    "layer",
    "layer_name",
    "rule_id",
)

TEXT_KEYS: tuple[str, ...] = (
    "text",
    "value",
    "label",
    "message",
    "name",
    "room_name",
)

GEOMETRY_KEYS: tuple[str, ...] = (
    "geometry",
    "bbox",
    "bounds",
    "points",
    "polygon",
    "polyline",
    "center",
)


@dataclass(frozen=True)
class ArtifactSchemaSummary:
    """Compact schema summary for one artifact payload."""

    kind: str
    payload_shape: str
    record_path: str
    record_count: int
    top_level_keys: list[str]
    record_keys: list[str]
    id_keys_present: list[str]
    text_keys_present: list[str]
    geometry_keys_present: list[str]

    def to_record(self) -> Json:
        return asdict(self)


def summarize_artifact_schema(payload: Any, kind: str = "unknown") -> ArtifactSchemaSummary:
    """Return a compact schema summary for review reports and evidence data."""

    records, record_path = _extract_records_with_path(payload, preferred_keys=(), max_depth=4)
    record_keys = sorted({key for record in records if isinstance(record, dict) for key in record.keys()})
    top_level_keys = sorted(str(k) for k in payload.keys()) if isinstance(payload, dict) else []
    return ArtifactSchemaSummary(
        kind=kind,
        payload_shape=type(payload).__name__,
        record_path=record_path,
        record_count=len(records),
        top_level_keys=top_level_keys[:50],
        record_keys=record_keys[:80],
        id_keys_present=[key for key in ID_KEYS if key in record_keys],
        text_keys_present=[key for key in TEXT_KEYS if key in record_keys],
        geometry_keys_present=[key for key in GEOMETRY_KEYS if key in record_keys],
    )


def extract_artifact_records(
    payload: Any,
    kind: str = "unknown",
    preferred_keys: Iterable[str] = (),
    *,
    max_depth: int = 4,
) -> list[Json]:
    """Extract normalized record dictionaries from a legacy artifact payload.

    The function is intentionally forgiving: it supports top-level lists,
    top-level mappings, nested ``data``/``result``/``payload`` wrappers and
    mapping-of-id-to-record shapes.
    """

    records, _path = _extract_records_with_path(payload, preferred_keys=tuple(preferred_keys), max_depth=max_depth)
    normalized: list[Json] = []
    for index, record in enumerate(records):
        normalized.append(_coerce_record(record, index=index, kind=kind))
    return normalized


def stable_record_id(record: Any, fallback: str) -> str:
    """Return a stable human-readable record id from common id/name fields."""

    if isinstance(record, dict):
        for key in ID_KEYS:
            value = record.get(key)
            if value not in (None, ""):
                return sanitize_identifier(str(value))
    return sanitize_identifier(fallback)


def sanitize_identifier(value: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in value.strip())
    return out or "unknown"


def _extract_records_with_path(
    payload: Any,
    *,
    preferred_keys: Iterable[str],
    max_depth: int,
) -> tuple[list[Any], str]:
    if isinstance(payload, list):
        return payload, "$"

    if not isinstance(payload, dict):
        return [], "$"

    direct = _extract_from_mapping(payload, preferred_keys=preferred_keys)
    if direct:
        return direct[0], direct[1]

    queue: deque[tuple[Any, str, int]] = deque((payload.get(key), f"$.{key}", 1) for key in COMMON_CONTAINER_KEYS if key in payload)
    seen: set[int] = set()
    while queue:
        node, path, depth = queue.popleft()
        if id(node) in seen:
            continue
        seen.add(id(node))

        if depth > max_depth:
            continue

        if isinstance(node, list):
            return node, path

        if isinstance(node, dict):
            nested = _extract_from_mapping(node, preferred_keys=preferred_keys)
            if nested:
                return nested[0], f"{path}.{nested[1][2:]}" if nested[1].startswith("$.") else f"{path}.{nested[1]}"

            for key in (*COMMON_CONTAINER_KEYS, *COMMON_RECORD_KEYS):
                if key in node:
                    queue.append((node[key], f"{path}.{key}", depth + 1))

    if _looks_like_mapping_of_records(payload):
        return _mapping_to_records(payload), "$"

    return [], "$"


def _extract_from_mapping(payload: Json, *, preferred_keys: Iterable[str]) -> tuple[list[Any], str] | None:
    for key in (*tuple(preferred_keys), *COMMON_RECORD_KEYS):
        value = payload.get(key)
        if isinstance(value, list):
            return value, f"$.{key}"
        if isinstance(value, dict):
            return _mapping_to_records(value), f"$.{key}"
    if _looks_like_mapping_of_records(payload):
        return _mapping_to_records(payload), "$"
    return None


def _looks_like_mapping_of_records(value: Any) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    if any(key in COMMON_CONTAINER_KEYS for key in value):
        return False
    return all(isinstance(item, (dict, str, int, float, bool, type(None))) for item in value.values())


def _mapping_to_records(mapping: Json) -> list[Json]:
    records: list[Json] = []
    for key, value in mapping.items():
        if isinstance(value, dict):
            if "name" in value:
                record = dict(value)
                record.setdefault("_mapping_key", str(key))
            else:
                record = {"name": str(key), **value}
        else:
            record = {"name": str(key), "value": value}
        records.append(record)
    return records


def _coerce_record(record: Any, *, index: int, kind: str) -> Json:
    if isinstance(record, dict):
        out = dict(record)
    else:
        out = {"value": record}
    out.setdefault("_record_index", index)
    out.setdefault("_artifact_kind", kind)
    out.setdefault("_stable_id", stable_record_id(out, f"{kind}.{index}"))
    return out
