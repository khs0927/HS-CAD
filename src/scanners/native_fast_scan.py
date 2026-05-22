from __future__ import annotations

from pathlib import Path
from typing import Any

from src.scanners.scan_strategy import recommend_scan_strategy


def fast_scan_active(adapter: Any) -> dict[str, Any]:
    """Read drawing metadata without walking every ModelSpace object."""

    doc = adapter.get_active_document()
    layers = []
    for i in range(doc.Layers.Count):
        layer = doc.Layers.Item(i)
        layers.append({
            "name": adapter._safe_get(layer, "Name"),
            "color": adapter._safe_get(layer, "Color"),
            "linetype": adapter._safe_get(layer, "Linetype"),
            "lineweight": adapter._safe_get(layer, "Lineweight"),
            "freeze": adapter._safe_get(layer, "Freeze"),
            "on": adapter._safe_get(layer, "LayerOn"),
        })

    blocks = []
    title_candidates = []
    for i in range(doc.Blocks.Count):
        block = doc.Blocks.Item(i)
        name = str(adapter._safe_get(block, "Name", "") or "")
        if not name or name.startswith("*"):
            continue
        blocks.append(name)
        low = name.lower()
        if any(k in low for k in ("zium", "sheet", "title", "도곽")):
            title_candidates.append(name)

    total_objects = adapter._modelspace_count()
    strategy = recommend_scan_strategy(total_objects, "index", available_tools=())
    return {
        "drawing_name": adapter._safe_get(doc, "Name"),
        "drawing_path": adapter._safe_get(doc, "FullName") or str(Path(adapter._safe_get(doc, "Path", "")) / str(adapter._safe_get(doc, "Name", ""))),
        "total_objects": total_objects,
        "layers_observed": layers,
        "user_blocks_observed": blocks,
        "title_block_candidates": title_candidates,
        "zium_title_block_present": any("zium" in b.lower() for b in title_candidates),
        "entity_frequency": {},
        "scan_strategy_recommendation": {
            "name": strategy.name,
            "allowed": strategy.allowed,
            "warning": strategy.warning,
            "steps": strategy.steps,
        },
    }
