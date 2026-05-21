"""Active ZWCAD document probing utilities.

These helpers are thin wrappers around the existing ``image_to_cad`` analysis
functions. They expose a more granular API required by the orchestrator
workflow and write JSON/Markdown reports to the *generated* directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from image_to_cad.auto.active_analyzer import analyze_active_drawing, ActiveDrawingAnalysis


def connect_active_zwcad() -> ZWCADCOMAdapter:
    """Create and connect a ``ZWCADCOMAdapter`` for the current active document.
    """
    adapter = ZWCADCOMAdapter(visible=True, start_if_needed=False)
    adapter.connect()
    return adapter


def get_active_document_info() -> Dict[str, str]:
    """Return the name and full path of the active DWG document.
    """
    adapter = connect_active_zwcad()
    doc = adapter.get_active_document()
    full = str(getattr(doc, "FullName", "") or getattr(doc, "Name", ""))
    name = Path(full).name
    return {"document_name": name, "document_path": full}


def _analysis() -> ActiveDrawingAnalysis:
    """Run the full active‑drawing analysis and return the model.
    """
    return analyze_active_drawing()


def collect_active_layers() -> Dict[str, int]:
    return _analysis().layer_counts


def collect_modelspace_summary() -> int:
    """Return the total number of objects in ModelSpace.
    """
    return _analysis().object_count


def collect_entity_type_counts() -> Dict[str, int]:
    return _analysis().entity_counts


def collect_block_references() -> Dict[str, int]:
    return _analysis().block_counts


def collect_dynamic_block_references() -> int:
    """Count block inserts where the *Name* starts with ``*U`` (anonymous) and
    an ``EffectiveName`` is present. These are the typical dynamic blocks.
    """
    adapter = connect_active_zwcad()
    doc = adapter.get_active_document()
    count = 0
    for obj in doc.ModelSpace:
        try:
            name = str(adapter._safe_get(obj, "Name", ""))
            effective = str(adapter._safe_get(obj, "EffectiveName", ""))
            if name.startswith("*U") and effective:
                count += 1
        except Exception:
            continue
    return count


def collect_text_samples() -> list[Dict[str, Any]]:
    return _analysis().text_samples


def collect_dimstyle_summary() -> Dict[str, Any]:
    adapter = connect_active_zwcad()
    doc = adapter.get_active_document()
    dimstyles = []
    try:
        for style in doc.DimStyles:
            dimstyles.append(str(adapter._safe_get(style, "Name", "")))
    except Exception:
        pass
    return {"count": len(dimstyles), "list": dimstyles}


def write_active_probe_json(out_path: str) -> str:
    """Write the probe data as JSON and return the absolute path.
    """
    analysis = _analysis()
    # Additional information that is not part of ``ActiveDrawingAnalysis``
    dynamic_refs = collect_dynamic_block_references()
    dimstyle_summary = collect_dimstyle_summary()
    probe = {
        "document_name": analysis.active_doc,
        "document_path": analysis.active_doc,
        "modelspace_object_count": analysis.object_count,
        "layer_count": len(analysis.layer_counts),
        "entity_type_counts": analysis.entity_counts,
        "block_reference_count": sum(analysis.block_counts.values()),
        "dynamic_block_reference_count": dynamic_refs,
        "text_count": len(analysis.text_samples),
        "dimension_count": analysis.dimension_count,
        "linetype_count": len(dimstyle_summary.get("list", [])),  # placeholder, real linetype count not collected here
        "dimstyle_count": dimstyle_summary.get("count", 0),
        "read_errors": analysis.warnings,
    }
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(probe, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_file)


def write_active_probe_md(out_path: str) -> str:
    """Write a human‑readable Markdown summary of the active probe.
    """
    analysis = _analysis()
    lines = [
        "# Active Document Probe",
        "",
        f"**Document**: {analysis.active_doc}",
        f"**Objects**: {analysis.object_count}",
        f"**Layers**: {len(analysis.layer_counts)}",
        f"**Entities**: {', '.join(f'{k}: {v}' for k, v in analysis.entity_counts.items())}",
        f"**Blocks**: {sum(analysis.block_counts.values())} (dynamic: {collect_dynamic_block_references()})",
        f"**Dimensions**: {analysis.dimension_count}",
        f"**Texts**: {len(analysis.text_samples)}",
        "",
        "## Warnings",
    ]
    if analysis.warnings:
        for w in analysis.warnings:
            lines.append(f"- {w.get('error', w)}")
    else:
        lines.append("- None")
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")
    return str(out_file)
