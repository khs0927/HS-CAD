from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any


@dataclass(frozen=True)
class XiCADSignatureMatch:
    alias: str
    status: str
    confidence: float
    entity_handles: list[str]
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def match_signatures_in_objects(
    objects: list[dict[str, Any]],
    signatures: list[dict[str, Any]],
) -> dict[str, Any]:
    matches: list[XiCADSignatureMatch] = []
    warnings: list[str] = []

    verified = [sig for sig in signatures if sig.get("status") == "verified"]
    if not verified:
        warnings.append("No verified signatures were provided; matching was skipped.")

    for signature in verified:
        alias = str(signature.get("alias") or "").upper()
        if alias == "WAL":
            matches.extend(_match_wal(objects, signature))
        else:
            warnings.append(f"No matcher is implemented for alias '{alias}'.")

    return {
        "status": "review_required",
        "object_count": len(objects),
        "signature_count": len(verified),
        "match_count": len(matches),
        "matches": [match.to_dict() for match in matches],
        "warnings": warnings,
        "safety": {
            "cad_mutation": False,
            "send_command": False,
            "requires_human_review": True,
        },
    }


def _match_wal(objects: list[dict[str, Any]], signature: dict[str, Any]) -> list[XiCADSignatureMatch]:
    expected_layers = _expected_layers(signature)
    expected_types = _expected_types(signature) or {"LINE", "LWPOLYLINE"}
    lines = [
        line
        for line in (_line_tuple(obj) for obj in objects)
        if line is not None
        and line["entity_type"] in expected_types
        and (not expected_layers or line["layer"] in expected_layers)
    ]

    matches: list[XiCADSignatureMatch] = []
    for idx, first in enumerate(lines):
        for second in lines[idx + 1 :]:
            if not _are_parallel(first, second):
                continue
            distance = round(_line_distance(first, second), 6)
            if distance <= 0:
                continue
            matches.append(
                XiCADSignatureMatch(
                    alias="WAL",
                    status="candidate_match",
                    confidence=0.55,
                    entity_handles=[first["handle"], second["handle"]],
                    evidence={
                        "pattern": "parallel_line_pair",
                        "layers": sorted({first["layer"], second["layer"]}),
                        "distance": distance,
                    },
                )
            )
    return matches


def _expected_layers(signature: dict[str, Any]) -> set[str]:
    hint = signature.get("signature_hint") or {}
    evidence = signature.get("evidence") or {}
    return {
        str(item)
        for item in (
            hint.get("expected_layer_names")
            or evidence.get("matched_layers")
            or []
        )
        if str(item)
    }


def _expected_types(signature: dict[str, Any]) -> set[str]:
    hint = signature.get("signature_hint") or {}
    evidence = signature.get("evidence") or {}
    return {
        str(item).upper()
        for item in (
            hint.get("expected_added_types")
            or evidence.get("matched_types")
            or []
        )
        if str(item)
    }


def _line_tuple(entity: dict[str, Any]) -> dict[str, Any] | None:
    entity_type = _entity_type(entity)
    if "LINE" not in entity_type:
        return None
    start = _point(entity.get("start") or entity.get("StartPoint"))
    end = _point(entity.get("end") or entity.get("EndPoint"))
    if start is None or end is None:
        return None
    return {
        "handle": str(entity.get("handle") or ""),
        "entity_type": entity_type,
        "layer": str(entity.get("layer") or "0"),
        "start": start,
        "end": end,
    }


def _point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except Exception:
        return None


def _are_parallel(first: dict[str, Any], second: dict[str, Any], *, tolerance: float = 1e-6) -> bool:
    ax, ay = _vector(first)
    bx, by = _vector(second)
    if math.hypot(ax, ay) <= tolerance or math.hypot(bx, by) <= tolerance:
        return False
    cross = abs(ax * by - ay * bx)
    return cross / (math.hypot(ax, ay) * math.hypot(bx, by)) <= tolerance


def _line_distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    x1, y1 = first["start"]
    x2, y2 = first["end"]
    x0, y0 = second["start"]
    numerator = abs((x2 - x1) * (y1 - y0) - (x1 - x0) * (y2 - y1))
    denominator = math.hypot(x2 - x1, y2 - y1)
    return numerator / denominator if denominator else 0.0


def _vector(line: dict[str, Any]) -> tuple[float, float]:
    sx, sy = line["start"]
    ex, ey = line["end"]
    length = math.hypot(ex - sx, ey - sy)
    if not length:
        return (0.0, 0.0)
    return ((ex - sx) / length, (ey - sy) / length)


def _entity_type(entity: dict[str, Any]) -> str:
    return str(
        entity.get("entity_type")
        or entity.get("dxftype")
        or entity.get("object_name")
        or "UNKNOWN"
    ).upper()
