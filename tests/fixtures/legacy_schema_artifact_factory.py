"""Factories for schema-variant legacy artifacts used by v6 tests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def write_schema_variant_legacy_artifacts(root: str | Path) -> Path:
    """Write realistic legacy artifact shapes that use nested wrappers.

    The files are JSON only and are generated at test/runtime. No runtime CAD
    files are committed.
    """

    output = Path(root)
    output.mkdir(parents=True, exist_ok=True)

    _write_json(
        output / "LAYER_SEMANTICS.json",
        {
            "schema_version": "legacy-layer-v2",
            "data": {
                "layers": {
                    "WAL1": {"semantic_role": "lightweight_wall", "confidence": 0.91},
                    "DOOR": {"category": "door", "confidence": 0.88},
                    "WIN": {"role": "window", "confidence": 0.86},
                }
            },
        },
    )
    _write_json(
        output / "TEXT_ROLE_INFERENCE.json",
        {
            "result": {
                "inferences": [
                    {"text": "ROOM 101", "text_role": "room_name", "confidence": 0.9},
                    {"text": "A=32.5m2", "role": "area_label", "confidence": 0.84},
                ]
            }
        },
    )
    _write_json(
        output / "AREA_ELEMENTS.json",
        {
            "payload": {
                "area_elements": [
                    {"entity_id": "ROOM-001", "computed_area": 32.5, "confidence": 0.82},
                    {"entity_id": "ROOM-002", "area": 18.25, "confidence": 0.77},
                ]
            }
        },
    )
    _write_json(
        output / "CROSS_VALIDATION.json",
        {
            "data": {
                "conflicts": [
                    {
                        "message": "Text area differs from computed area",
                        "severity": "warning",
                        "entity_id": "ROOM-001",
                    }
                ],
                "recommendations": [
                    {"message": "Manual review required for ROOM-001"},
                ],
            }
        },
    )
    _write_json(
        output / "DOMAIN_RULE_RESULTS.json",
        {
            "data": {
                "rules": [
                    {
                        "rule_id": "ROOM_AREA_REVIEW",
                        "status": "warning",
                        "message": "Room area should be reviewed",
                        "confidence": 0.65,
                    },
                    {
                        "rule_id": "CAD_LIVE_EXECUTION_DISABLED",
                        "status": "pass",
                        "message": "Review-only safety policy is active",
                        "confidence": 0.98,
                    },
                ]
            }
        },
    )
    return output


def _write_json(path: Path, payload: Json) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
