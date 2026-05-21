"""Dynamic block report utilities.

The report groups block insert references by ``EffectiveName`` (when present)
or by the raw ``Name`` otherwise. It produces JSON and Markdown summaries
that include count, sample handles and insertion points.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.integrations.zwcad_live.active_document_probe import connect_active_zwcad


def collect_dynamic_blocks() -> Dict[str, Any]:
    """Collect block insert statistics from the active drawing.

    Returns a mapping keyed by the chosen block identifier (EffectiveName if
    available, otherwise Name). Each value is a dictionary containing:
    - ``raw_name``
    - ``effective_name``
    - ``layer_counts`` – dict of layer → count
    - ``count`` – total occurrences
    - ``handles`` – list of sample handles (up to 5)
    - ``insertion_points`` – list of sample insertion points (up to 5)
    """
    adapter = connect_active_zwcad()
    doc = adapter.get_active_document()
    blocks: Dict[str, Dict[str, Any]] = {}
    for obj in doc.ModelSpace:
        try:
            entity_type = adapter._entity_type(str(adapter._safe_get(obj, "ObjectName", "")))
            if entity_type != "INSERT":
                continue
            name = str(adapter._safe_get(obj, "Name", ""))
            effective = str(adapter._safe_get(obj, "EffectiveName", ""))
            key = effective or name
            if not key:
                continue
            entry = blocks.setdefault(key, {
                "raw_name": name,
                "effective_name": effective,
                "layer_counts": {},
                "count": 0,
                "handles": [],
                "insertion_points": [],
            })
            entry["count"] += 1
            layer = str(adapter._safe_get(obj, "Layer", ""))
            if layer:
                entry["layer_counts"][layer] = entry["layer_counts"].get(layer, 0) + 1
            handle = str(adapter._safe_get(obj, "Handle", ""))
            if handle and len(entry["handles"]) < 5 and handle not in entry["handles"]:
                entry["handles"].append(handle)
            ins = adapter._safe_get(obj, "InsertionPoint")
            if ins and len(entry["insertion_points"]) < 5:
                entry["insertion_points"].append(ins)
        except Exception:
            continue
    return blocks


def write_dynamic_block_report_json(out_path: str) -> str:
    """Write the dynamic block report to *out_path* as JSON.
    """
    report = collect_dynamic_blocks()
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_file)


def write_dynamic_block_report_md(out_path: str) -> str:
    """Write a Markdown summary of the dynamic block report.
    """
    blocks = collect_dynamic_blocks()
    lines = ["# Dynamic Block Report", ""]
    for key, data in sorted(blocks.items()):
        lines.append(f"## Block: {key}")
        lines.append(f"- Raw Name: {data.get('raw_name')}")
        lines.append(f"- Effective Name: {data.get('effective_name')}")
        lines.append(f"- Total Count: {data.get('count')}")
        lines.append(f"- Layers: {', '.join(f'{ly}:{cnt}' for ly, cnt in data.get('layer_counts', {}).items())}")
        lines.append(f"- Sample Handles: {', '.join(data.get('handles', []))}")
        lines.append(f"- Sample Insertion Points: {', '.join(str(p) for p in data.get('insertion_points', []))}")
        lines.append("")
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")
    return str(out_file)
