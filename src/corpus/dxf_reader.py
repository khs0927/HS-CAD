"""DXF reader based on the ``ezdxf`` library.

Provides a thin wrapper that extracts the same high‑level pieces as ``dwg_reader``
so downstream code can treat both formats uniformly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

import ezdxf


def _collect_texts(msp) -> List[Dict[str, Any]]:
    texts: List[Dict[str, Any]] = []
    for e in msp:
        if e.dxftype() in {"TEXT", "MTEXT"}:
            texts.append({
                "handle": e.dxf.handle,
                "layer": e.dxf.layer,
                "text": e.text if e.dxftype() == "TEXT" else e.text,
                "insert": e.dxf.insert if hasattr(e.dxf, "insert") else None,
                "rotation": e.dxf.rotation if hasattr(e.dxf, "rotation") else None,
            })
    return texts


def read_dxf(dxf_path: Path) -> Dict[str, Any]:
    """Read a DXF file and return a simplified representation.

    Returns keys ``objects``, ``layer_summary``, ``block_summary``, ``texts``.
    ``objects`` is a list of raw DXF entities (as dictionaries) – for now we keep a
    minimal subset needed for knowledge extraction.
    """

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    # Gather raw entity information (very lightweight)
    objects: List[Dict[str, Any]] = []
    for e in msp:
        obj = {
            "handle": e.dxf.handle,
            "entity_type": e.dxftype(),
            "layer": e.dxf.layer,
        }
        # Add a few common attributes if present
        if hasattr(e.dxf, "text"):
            obj["text"] = e.dxf.text
        if hasattr(e.dxf, "insert"):
            obj["insert"] = list(e.dxf.insert)
        if hasattr(e.dxf, "rotation"):
            obj["rotation"] = e.dxf.rotation
        objects.append(obj)
    # Layer summary
    layer_counts: Dict[str, int] = {}
    for e in objects:
        layer = e.get("layer", "<NO_LAYER>")
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
    # Block summary – ezdxf stores block definitions separately; we count block
    # inserts in the modelspace.
    block_counts: Dict[str, int] = {}
    for e in objects:
        if e["entity_type"] in {"INSERT", "BLOCK_REFERENCE"}:
            name = e.get("name") or e.get("block_name")
            if name:
                block_counts[name] = block_counts.get(name, 0) + 1
    # Text extraction
    texts = _collect_texts(msp)
    return {
        "objects": objects,
        "layer_summary": layer_counts,
        "block_summary": block_counts,
        "texts": texts,
    }
