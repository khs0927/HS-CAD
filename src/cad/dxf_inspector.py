from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import ezdxf


def inspect_dxf(path: str | Path) -> dict[str, Any]:
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    entity_counts: Counter[str] = Counter()
    layer_counts: Counter[str] = Counter()
    text_rows: list[dict[str, str]] = []
    block_names: Counter[str] = Counter()

    for entity in msp:
        dxftype = entity.dxftype()
        entity_counts[dxftype] += 1
        layer_counts[getattr(entity.dxf, "layer", "0")] += 1

        if dxftype in {"TEXT", "MTEXT"}:
            text_rows.append(
                {
                    "type": dxftype,
                    "layer": getattr(entity.dxf, "layer", "0"),
                    "text": entity.plain_text() if dxftype == "MTEXT" else entity.dxf.text,
                    "handle": entity.dxf.handle,
                }
            )
        if dxftype == "INSERT":
            block_names[entity.dxf.name] += 1

    return {
        "entity_counts": dict(entity_counts),
        "layer_counts": dict(layer_counts),
        "texts": text_rows,
        "block_names": dict(block_names),
    }
