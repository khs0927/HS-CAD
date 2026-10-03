from __future__ import annotations

import hashlib
import json
from typing import Any


SCHEMA = "cad-drawing-grammar/1"


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_drawing_grammar_contract(sample: dict[str, Any]) -> dict[str, Any]:
    """Normalize a local HS-CAD style sample into a portable read-only contract."""
    recommended = dict(sample.get("recommended_generation_style") or {})
    distributions = {
        "layers": sample.get("dominant_layers") or [],
        "entity_types": sample.get("dominant_entity_types") or [],
        "colors": sample.get("dominant_colors") or [],
        "linetypes": sample.get("dominant_linetypes") or [],
        "lineweights": sample.get("dominant_lineweights") or [],
        "text_heights": sample.get("text_height_families") or [],
        "text_styles": sample.get("text_styles") or [],
        "dimension_styles": sample.get("dimension_styles") or [],
        "block_effective_names": sample.get("block_effective_names") or [],
    }
    evidence = {
        "nearby_entity_count": int(sample.get("nearby_entity_count") or 0),
        "sample_digest": _digest(sample.get("nearby_sample") or []),
    }
    contract = {
        "schema": SCHEMA,
        "document": {
            "name": sample.get("doc_name"),
            "path": sample.get("full_name"),
        },
        "anchor": {
            "handle": sample.get("source_handle"),
            "radius": sample.get("radius"),
        },
        "recommended_generation_style": recommended,
        "distributions": distributions,
        "evidence": evidence,
        "execution_authorized": False,
        "may_execute_mutation": False,
    }
    contract["contract_digest"] = _digest(contract)
    return contract
