"""Runtime factory for synthetic legacy HS-CAD artifacts.

No DXF/DWG fixture is committed here. The tests create JSON artifacts only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_legacy_artifact_set(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "FILEIZED_DRAWING.json", {
        "input_path": "synthetic_legacy.dxf",
        "source_format": "dxf",
        "entities": [
            {"entity_id": "E1", "entity_type": "LINE", "layer": "WAL1", "geometry": {"start": [0, 0], "end": [10, 0]}},
            {"entity_id": "E2", "entity_type": "TEXT", "layer": "TEXT", "text": "ROOM 101", "geometry": {"insert": [2, 2]}},
            {"entity_id": "E3", "entity_type": "LWPOLYLINE", "layer": "AREA", "geometry": {"points": [[0,0],[10,0],[10,5],[0,5]], "closed": True}},
        ],
        "metadata": {"factory": "legacy_artifact_factory"},
        "warnings": [],
    })
    write_json(root / "LAYER_SEMANTICS.json", {
        "layers": [
            {"layer": "WAL1", "role": "lightweight_wall", "confidence": 0.82},
            {"layer": "TEXT", "role": "annotation", "confidence": 0.78},
        ]
    })
    write_json(root / "TEXT_ROLE_INFERENCE.json", {
        "text_roles": [{"text": "ROOM 101", "role": "room_name", "confidence": 0.8, "entity_id": "E2"}]
    })
    write_json(root / "AREA_ELEMENTS.json", {
        "areas": [{"entity_id": "E3", "area": 50.0, "layer": "AREA", "confidence": 0.83}]
    })
    write_json(root / "SHAPELY_TOPOLOGY.json", {
        "issues": [{"severity": "warning", "message": "synthetic topology review marker", "entity_id": "E3"}]
    })
    write_json(root / "CROSS_VALIDATION.json", {
        "conflicts": [{"type": "low_confidence", "message": "synthetic conflict for review"}],
        "recommendations": [{"priority": "P1", "action": "manual_review_required", "details": "synthetic"}],
    })
    write_json(root / "DOMAIN_RULE_RESULTS.json", [
        {"rule_id": "SYNTHETIC_REVIEW_ONLY", "status": "warning", "message": "Synthetic review-only rule", "confidence": 0.55}
    ])
    return root
