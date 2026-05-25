from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any


GEOMETRY_KEYS = (
    "start",
    "end",
    "coords",
    "coordinates",
    "insert",
    "center",
    "radius",
    "text",
    "effective_name",
    "name",
    "rotation",
    "x_scale",
    "y_scale",
    "z_scale",
    "closed",
    "bbox",
)


@dataclass(frozen=True)
class EntityDeltaItem:
    key: str
    entity: dict[str, Any]
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    changed_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityDeltaReport:
    added: list[EntityDeltaItem]
    removed: list[EntityDeltaItem]
    changed: list[EntityDeltaItem]
    unchanged_count: int
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "added": [item.to_dict() for item in self.added],
            "removed": [item.to_dict() for item in self.removed],
            "changed": [item.to_dict() for item in self.changed],
            "unchanged_count": self.unchanged_count,
            "summary": self.summary,
        }


def build_entity_delta(
    before_objects: list[dict[str, Any]],
    after_objects: list[dict[str, Any]],
) -> EntityDeltaReport:
    before = _index_entities(before_objects)
    after = _index_entities(after_objects)

    before_keys = set(before)
    after_keys = set(after)

    added = [
        EntityDeltaItem(key=key, entity=after[key], after=after[key])
        for key in sorted(after_keys - before_keys)
    ]
    removed = [
        EntityDeltaItem(key=key, entity=before[key], before=before[key])
        for key in sorted(before_keys - after_keys)
    ]

    changed: list[EntityDeltaItem] = []
    unchanged_count = 0
    for key in sorted(before_keys & after_keys):
        changed_fields = _changed_fields(before[key], after[key])
        if changed_fields:
            changed.append(
                EntityDeltaItem(
                    key=key,
                    entity=after[key],
                    before=before[key],
                    after=after[key],
                    changed_fields=changed_fields,
                )
            )
        else:
            unchanged_count += 1

    summary = {
        "before_count": len(before_objects),
        "after_count": len(after_objects),
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "unchanged_count": unchanged_count,
        "added_layer_counts": _counts([item.entity for item in added], "layer"),
        "added_type_counts": _type_counts([item.entity for item in added]),
        "removed_layer_counts": _counts([item.entity for item in removed], "layer"),
        "removed_type_counts": _type_counts([item.entity for item in removed]),
    }

    return EntityDeltaReport(
        added=added,
        removed=removed,
        changed=changed,
        unchanged_count=unchanged_count,
        summary=summary,
    )


def entity_identity(entity: dict[str, Any]) -> str:
    handle = str(entity.get("handle") or entity.get("Handle") or "").strip()
    if handle:
        return f"handle:{handle}"
    payload = {
        "entity_type": _entity_type(entity),
        "layer": str(entity.get("layer") or entity.get("Layer") or "0"),
        "geometry": _geometry_payload(entity),
    }
    data = json.dumps(_normalize(payload), sort_keys=True, ensure_ascii=False)
    return f"fingerprint:{hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]}"


def entity_fingerprint(entity: dict[str, Any]) -> str:
    data = json.dumps(_normalize(entity), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _index_entities(objects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    seen: Counter[str] = Counter()
    for entity in objects:
        base = entity_identity(entity)
        seen[base] += 1
        key = base if seen[base] == 1 else f"{base}#{seen[base]}"
        indexed[key] = entity
    return indexed


def _changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    fields = sorted(set(before) | set(after))
    changed: list[str] = []
    for field in fields:
        if _normalize(before.get(field)) != _normalize(after.get(field)):
            changed.append(field)
    return changed


def _entity_type(entity: dict[str, Any]) -> str:
    return str(
        entity.get("entity_type")
        or entity.get("dxftype")
        or entity.get("object_name")
        or entity.get("ObjectName")
        or "UNKNOWN"
    ).upper()


def _geometry_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {key: entity.get(key) for key in GEOMETRY_KEYS if key in entity}


def _counts(objects: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts = Counter(str(item.get(key) or "0") for item in objects)
    return dict(sorted(counts.items()))


def _type_counts(objects: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(_entity_type(item) for item in objects)
    return dict(sorted(counts.items()))


def _normalize(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value)}
    return value
