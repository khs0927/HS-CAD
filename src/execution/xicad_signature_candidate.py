from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any

from src.execution.entity_delta import EntityDeltaReport


@dataclass(frozen=True)
class GeometryPattern:
    kind: str
    count: int
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class XiCADSignatureCandidate:
    alias: str
    status: str
    source: str
    requires_human_review: bool
    confidence: float
    observed_delta: dict[str, Any]
    geometry_patterns: list[GeometryPattern]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "status": self.status,
            "source": self.source,
            "requires_human_review": self.requires_human_review,
            "confidence": self.confidence,
            "observed_delta": self.observed_delta,
            "geometry_patterns": [item.to_dict() for item in self.geometry_patterns],
            "warnings": self.warnings,
            "safety": {
                "original_dwg_mutation": False,
                "execution_scope": "fixture_or_approved_copy_only",
                "auto_promote_to_config": False,
            },
        }


def build_signature_candidate(
    alias: str,
    delta: EntityDeltaReport | dict[str, Any],
    *,
    source: str = "entity_delta",
) -> XiCADSignatureCandidate:
    payload = delta.to_dict() if isinstance(delta, EntityDeltaReport) else delta
    added = [item.get("entity", {}) for item in payload.get("added", [])]
    patterns = detect_geometry_patterns(added)
    confidence = _initial_confidence(patterns, added)

    warnings = [
        "Generated signature candidate only; human review is required before config promotion."
    ]
    if not added:
        warnings.append("No added entities were observed.")

    return XiCADSignatureCandidate(
        alias=alias.upper(),
        status="candidate",
        source=source,
        requires_human_review=True,
        confidence=confidence,
        observed_delta={
            "summary": payload.get("summary", {}),
            "added_layer_counts": payload.get("summary", {}).get("added_layer_counts", {}),
            "added_type_counts": payload.get("summary", {}).get("added_type_counts", {}),
        },
        geometry_patterns=patterns,
        warnings=warnings,
    )


def detect_geometry_patterns(entities: list[dict[str, Any]]) -> list[GeometryPattern]:
    patterns: list[GeometryPattern] = []
    lines = [_line_tuple(entity) for entity in entities]
    lines = [line for line in lines if line is not None]

    parallel_pairs: list[dict[str, Any]] = []
    for idx, first in enumerate(lines):
        for second in lines[idx + 1 :]:
            if _are_parallel(first, second):
                parallel_pairs.append(
                    {
                        "first_layer": first["layer"],
                        "second_layer": second["layer"],
                        "distance": round(_line_distance(first, second), 6),
                    }
                )

    if parallel_pairs:
        patterns.append(
            GeometryPattern(
                kind="parallel_line_pair",
                count=len(parallel_pairs),
                evidence=parallel_pairs,
            )
        )

    block_inserts = [
        entity
        for entity in entities
        if "INSERT" in _entity_type(entity) or "BLOCK" in _entity_type(entity)
    ]
    if block_inserts:
        patterns.append(
            GeometryPattern(
                kind="block_insert",
                count=len(block_inserts),
                evidence=[
                    {
                        "layer": str(item.get("layer") or "0"),
                        "name": str(item.get("effective_name") or item.get("name") or ""),
                    }
                    for item in block_inserts[:20]
                ],
            )
        )

    return patterns


def _line_tuple(entity: dict[str, Any]) -> dict[str, Any] | None:
    if "LINE" not in _entity_type(entity):
        return None
    start = _point(entity.get("start") or entity.get("StartPoint"))
    end = _point(entity.get("end") or entity.get("EndPoint"))
    if start is None or end is None:
        return None
    return {
        "start": start,
        "end": end,
        "layer": str(entity.get("layer") or "0"),
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


def _initial_confidence(patterns: list[GeometryPattern], entities: list[dict[str, Any]]) -> float:
    if not entities:
        return 0.0
    if any(pattern.kind == "parallel_line_pair" for pattern in patterns):
        return 0.45
    if patterns:
        return 0.25
    return 0.1
