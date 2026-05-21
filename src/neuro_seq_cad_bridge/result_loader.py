from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_neuro_result(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "entities": [],
            "warnings": ["missing neuro result: no result path provided"],
            "metadata": {"missing": True, "path": None},
        }
    p = Path(path)
    if not p.exists():
        return {
            "entities": [],
            "warnings": [f"missing neuro result: {p}"],
            "metadata": {"missing": True, "path": str(p)},
        }
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"failed to load neuro result {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"neuro result must be a JSON object: {p}")
    return data


def iter_neuro_entities(result: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = result.get("entities")
    if candidates is None:
        candidates = result.get("evidence_graph", {}).get("entities")
    if candidates is None:
        candidates = result.get("objects")
    if candidates is None:
        return []
    return [item for item in candidates if isinstance(item, dict)]


def normalize_neuro_entity(entity: dict[str, Any]) -> dict[str, Any]:
    warnings = list(entity.get("warnings") or [])
    geometry = entity.get("geometry")
    if geometry is None:
        warnings.append("missing geometry")
    return {
        "id": str(entity.get("id") or entity.get("uid") or "entity"),
        "entity_type": str(entity.get("entity_type") or entity.get("type") or "unknown"),
        "geometry": geometry or {},
        "sources": list(entity.get("sources") or entity.get("source") or []),
        "confidence": float(entity.get("confidence", 0.5) if entity.get("confidence") is not None else 0.5),
        "provenance": dict(entity.get("provenance") or {}),
        "warnings": warnings,
    }
