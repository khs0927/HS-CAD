from __future__ import annotations

import json
import platform
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from src.reports.excel_exporter import export_excel
from src.reports.json_exporter import export_json
from src.semantics.layer_taxonomy import layer_rules_as_rows
from src.semantics.object_classifier import classify_objects, summarize_semantics

ARCH_LAYER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "wall": ("A-WALL", "WALL", "벽", "내벽", "외벽"),
    "column": ("A-COLUMN", "COLUMN", "COL", "기둥"),
    "beam": ("A-BEAM", "BEAM", "보"),
    "door": ("A-DOOR", "DOOR", "DR", "문"),
    "window": ("A-WINDOW", "WINDOW", "WIN", "창"),
    "room": ("A-ROOM", "ROOM", "실명", "실"),
    "text": ("A-TEXT", "TEXT", "문자"),
    "dimension": ("A-DIMS", "DIM", "치수"),
    "grid": ("A-GRID", "GRID", "축선", "그리드"),
    "boundary": ("A-BOUNDARY", "BOUNDARY", "경계"),
}

BLOCK_CANDIDATE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "door": ("D", "DOOR", "DR", "문"),
    "window": ("W", "WIN", "WINDOW", "창"),
    "column": ("C", "COL", "COLUMN", "기둥"),
    "parking": ("P", "PARK", "주차"),
    "equipment": ("EQ", "MEP", "위생", "설비"),
}

ROOM_TEXT_KEYWORDS = (
    "사무실", "창고", "화장실", "복도", "계단실", "기계실", "전기실", "홀", "ROOM", "실", "주차", "관리", "회의",
)
AREA_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(㎡|m2|M2|평|m²)")
BROKEN_TEXT_MARKERS = ("???", "□", "�")


# Clean semantic keywords. These assignments intentionally override any
# mojibake-prone package strings above so generated reports stay readable.
ARCH_LAYER_KEYWORDS = {
    "wall": ("A-WALL", "WALL", "WAL", "벽", "내벽", "외벽"),
    "column": ("A-COLUMN", "COLUMN", "COL", "기둥"),
    "beam": ("A-BEAM", "BEAM", "보"),
    "door": ("A-DOOR", "DOOR", "DR", "문"),
    "window": ("A-WINDOW", "WINDOW", "WIN", "창"),
    "room": ("A-ROOM", "ROOM", "실명", "실"),
    "text": ("A-TEXT", "TEXT", "문자"),
    "dimension": ("A-DIMS", "DIM", "치수"),
    "grid": ("A-GRID", "GRID", "축선", "그리드"),
    "boundary": ("A-BOUNDARY", "BOUNDARY", "BOUND", "경계"),
}

BLOCK_CANDIDATE_KEYWORDS = {
    "door": ("D", "DOOR", "DR", "문"),
    "window": ("W", "WIN", "WINDOW", "창"),
    "column": ("C", "COL", "COLUMN", "기둥"),
    "parking": ("P", "PARK", "주차"),
    "equipment": ("EQ", "MEP", "위생", "설비"),
}

ROOM_TEXT_KEYWORDS = (
    "사무실", "창고", "화장실", "복도", "계단실", "기계실", "전기실",
    "홀", "ROOM", "실", "주차", "관리", "회의",
)
AREA_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(㎡|m2|M2|평|m²)", re.IGNORECASE)
BROKEN_TEXT_MARKERS = ("???", "�", "占", "踰", "洹")


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _entity_type(obj: dict[str, Any]) -> str:
    return _upper(obj.get("entity_type") or obj.get("object_name") or "UNKNOWN")


def _block_name(obj: dict[str, Any]) -> str:
    return _norm(obj.get("effective_name") or obj.get("name"))


def _is_by_layer(value: Any) -> bool:
    if value is None:
        return True
    text = _upper(value)
    return text in {"BYLAYER", "256", "-1", "NONE", ""}


def _candidate_kind(text: str, rules: dict[str, tuple[str, ...]]) -> str | None:
    up = text.upper()
    for kind, keywords in rules.items():
        for keyword in keywords:
            key = keyword.upper()
            if up == key or up.startswith(key) or key in up:
                return kind
    return None


def layer_audit(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    candidates: dict[str, list[str]] = defaultdict(list)
    by_layer_violations = {"color": 0, "linetype": 0}
    for obj in objects:
        layer = _norm(obj.get("layer")) or "<none>"
        counts[layer] += 1
        kind = _candidate_kind(layer, ARCH_LAYER_KEYWORDS)
        if kind:
            candidates[kind].append(layer)
        if not _is_by_layer(obj.get("color")):
            by_layer_violations["color"] += 1
        if not _is_by_layer(obj.get("linetype")):
            by_layer_violations["linetype"] += 1
    rows = [{"layer": layer, "count": count, "candidate_kind": _candidate_kind(layer, ARCH_LAYER_KEYWORDS)} for layer, count in sorted(counts.items())]
    return {
        "counts": dict(counts),
        "rows": rows,
        "candidates": {k: sorted(set(v)) for k, v in candidates.items()},
        "by_layer_violations": by_layer_violations,
    }


def block_audit(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    inserts: dict[str, list[list[Any]]] = defaultdict(list)
    rotations: dict[str, Counter[str]] = defaultdict(Counter)
    scales: dict[str, Counter[str]] = defaultdict(Counter)
    candidates: dict[str, list[str]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    for obj in objects:
        if "INSERT" not in _entity_type(obj):
            continue
        name = _block_name(obj) or "<unnamed>"
        counts[name] += 1
        insert = obj.get("insert") or []
        inserts[name].append(insert)
        rotations[name][str(obj.get("rotation", 0))] += 1
        scale_key = f"{obj.get('x_scale', 1)}|{obj.get('y_scale', 1)}|{obj.get('z_scale', 1)}"
        scales[name][scale_key] += 1
        kind = _candidate_kind(name, BLOCK_CANDIDATE_KEYWORDS)
        if kind:
            candidates[kind].append(name)
        rows.append({
            "handle": obj.get("handle"),
            "layer": obj.get("layer"),
            "block": name,
            "candidate_kind": kind,
            "insert": insert,
            "rotation": obj.get("rotation"),
            "x_scale": obj.get("x_scale"),
            "y_scale": obj.get("y_scale"),
            "z_scale": obj.get("z_scale"),
        })
    summary_rows = []
    for name, count in sorted(counts.items()):
        summary_rows.append({
            "block": name,
            "count": count,
            "candidate_kind": _candidate_kind(name, BLOCK_CANDIDATE_KEYWORDS),
            "rotation_variants": len(rotations[name]),
            "scale_variants": len(scales[name]),
        })
    return {"counts": dict(counts), "rows": rows, "summary_rows": summary_rows, "candidates": {k: sorted(set(v)) for k, v in candidates.items()}}


def text_audit(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    room_candidates: list[dict[str, Any]] = []
    area_candidates: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for obj in objects:
        if _entity_type(obj) not in {"TEXT", "MTEXT"}:
            continue
        text = _norm(obj.get("text"))
        row = {"handle": obj.get("handle"), "layer": obj.get("layer"), "text": text, "insert": obj.get("insert"), "height": obj.get("height"), "rotation": obj.get("rotation")}
        rows.append(row)
        if any(keyword in text for keyword in ROOM_TEXT_KEYWORDS):
            room_candidates.append(row | {"reason": "room_keyword"})
        match = AREA_PATTERN.search(text)
        if match:
            area_candidates.append(row | {"area_value": match.group(1), "area_unit": match.group(2)})
        if not text:
            warnings.append(row | {"warning": "empty_text"})
        if len(text) > 120:
            warnings.append(row | {"warning": "very_long_text"})
        if any(marker in text for marker in BROKEN_TEXT_MARKERS):
            warnings.append(row | {"warning": "possible_broken_encoding"})
    return {"rows": rows, "room_candidates": room_candidates, "area_candidates": area_candidates, "warnings": warnings}


def polyline_audit(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for obj in objects:
        if "POLYLINE" not in _entity_type(obj):
            continue
        points = obj.get("points") or []
        area = obj.get("area")
        row = {"handle": obj.get("handle"), "layer": obj.get("layer"), "closed": bool(obj.get("closed")), "point_count": len(points), "area": area}
        rows.append(row)
        if row["closed"]:
            candidates.append(row | {"reason": "closed_polyline"})
    return {"rows": rows, "area_candidates": candidates, "closed_count": len(candidates), "open_count": len(rows) - len(candidates)}


def generate_drawing_audit(objects: list[dict[str, Any]]) -> dict[str, Any]:
    layer = layer_audit(objects)
    block = block_audit(objects)
    text = text_audit(objects)
    poly = polyline_audit(objects)
    entity_counts = Counter(_entity_type(o) for o in objects)
    xrefs = [o for o in objects if o.get("is_xref") or "XREF" in _upper(o.get("object_name"))]
    warnings = []
    warnings.extend(text["warnings"])
    if layer["by_layer_violations"]["color"]:
        warnings.append({"warning": "color_not_bylayer", "count": layer["by_layer_violations"]["color"]})
    if layer["by_layer_violations"]["linetype"]:
        warnings.append({"warning": "linetype_not_bylayer", "count": layer["by_layer_violations"]["linetype"]})
    return {
        "object_count": len(objects),
        "entity_counts": dict(entity_counts),
        "layers": layer,
        "blocks": block,
        "texts": text,
        "polylines": poly,
        "xrefs": [{"handle": o.get("handle"), "layer": o.get("layer"), "name": _block_name(o)} for o in xrefs],
        "warnings": warnings,
    }


def _write_md_report(audit: dict[str, Any], path: Path) -> None:
    lines = ["# Architecture Drawing Audit", "", f"- Object count: {audit['object_count']}", ""]
    lines.append("## Entity counts")
    for key, value in sorted(audit["entity_counts"].items()):
        lines.append(f"- {key}: {value}")
    lines.append("\n## Layer candidates")
    for kind, layers in audit["layers"]["candidates"].items():
        lines.append(f"- {kind}: {', '.join(layers) if layers else '-'}")
    lines.append("\n## Block candidates")
    for kind, blocks in audit["blocks"]["candidates"].items():
        lines.append(f"- {kind}: {', '.join(blocks) if blocks else '-'}")
    lines.append("\n## Text candidates")
    lines.append(f"- Room candidates: {len(audit['texts']['room_candidates'])}")
    lines.append(f"- Area text candidates: {len(audit['texts']['area_candidates'])}")
    lines.append("\n## Polyline quality")
    lines.append(f"- Closed polylines: {audit['polylines']['closed_count']}")
    lines.append(f"- Open polylines: {audit['polylines']['open_count']}")
    lines.append("\n## Warnings")
    if audit["warnings"]:
        for item in audit["warnings"][:200]:
            lines.append(f"- {item}")
    else:
        lines.append("- No warnings generated by static audit.")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_architecture_report(objects: list[dict[str, Any]], out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    audit = generate_drawing_audit(objects)
    object_semantics = classify_objects(objects)
    semantic_summary = summarize_semantics(object_semantics)
    paths: dict[str, Path] = {}
    paths["objects"] = export_json(objects, out / "objects.json")
    paths["summary_json"] = export_json(audit, out / "architecture_summary.json")
    paths["object_semantics_json"] = export_json(object_semantics, out / "object_semantics.json")
    paths["semantic_summary_json"] = export_json(semantic_summary, out / "semantic_summary.json")
    _write_md_report(audit, out / "architecture_summary.md")
    _write_md_report(audit, out / "drawing_audit.md")
    paths["summary_md"] = out / "architecture_summary.md"
    paths["drawing_audit_md"] = out / "drawing_audit.md"
    sheets = {
        "layers": audit["layers"]["rows"],
        "layer_candidates": [{"kind": k, "layers": ", ".join(v)} for k, v in audit["layers"]["candidates"].items()],
        "blocks": audit["blocks"]["summary_rows"],
        "block_instances": audit["blocks"]["rows"],
        "texts": audit["texts"]["rows"],
        "room_candidates": audit["texts"]["room_candidates"],
        "area_candidates": audit["texts"]["area_candidates"],
        "polylines": audit["polylines"]["rows"],
        "warnings": audit["warnings"],
        "object_semantics": object_semantics,
        "semantic_summary": [{"key": k, "value": v} for k, v in semantic_summary.items() if k not in {"low_confidence_samples", "color_mismatch_samples", "by_layer_category"}],
        "layer_taxonomy": layer_rules_as_rows(),
    }
    paths["audit_xlsx"] = export_excel(sheets, out / "architecture_audit.xlsx")
    paths["layer_audit_xlsx"] = export_excel({"layers": audit["layers"]["rows"]}, out / "layer_audit.xlsx")
    paths["block_audit_xlsx"] = export_excel({"blocks": audit["blocks"]["summary_rows"], "instances": audit["blocks"]["rows"]}, out / "block_audit.xlsx")
    paths["text_audit_xlsx"] = export_excel({"texts": audit["texts"]["rows"]}, out / "text_audit.xlsx")
    paths["room_candidates_xlsx"] = export_excel({"room_candidates": audit["texts"]["room_candidates"]}, out / "room_candidates.xlsx")
    paths["area_candidates_xlsx"] = export_excel({"area_candidates": audit["texts"]["area_candidates"], "polylines": audit["polylines"]["area_candidates"]}, out / "area_candidates.xlsx")
    paths["opening_candidates_xlsx"] = export_excel({"door_blocks": [{"block": b} for b in audit["blocks"]["candidates"].get("door", [])], "window_blocks": [{"block": b} for b in audit["blocks"]["candidates"].get("window", [])]}, out / "opening_candidates.xlsx")
    paths["column_candidates_xlsx"] = export_excel({"column_blocks": [{"block": b} for b in audit["blocks"]["candidates"].get("column", [])]}, out / "column_candidates.xlsx")
    paths["quantity_xlsx"] = export_excel({"block_quantity": audit["blocks"]["summary_rows"], "layer_quantity": audit["layers"]["rows"], "semantic_quantity": [{"category": k, "count": v} for k, v in semantic_summary["by_category"].items()]}, out / "quantity.xlsx")
    paths["object_semantics_xlsx"] = export_excel({"object_semantics": object_semantics, "summary": [{"category": k, "count": v} for k, v in semantic_summary["by_category"].items()], "layer_taxonomy": layer_rules_as_rows()}, out / "object_semantics.xlsx")
    paths["layer_semantics_xlsx"] = export_excel({"layer_taxonomy": layer_rules_as_rows(), "by_layer_category": [{"layer": layer, "categories": str(cats)} for layer, cats in semantic_summary["by_layer_category"].items()]}, out / "layer_semantics.xlsx")

    semantic_lines = ["# Drawing Semantic Summary", "", "## Category counts"]
    for key, value in sorted(semantic_summary["by_category"].items()):
        semantic_lines.append(f"- {key}: {value}")
    semantic_lines.append("\n## Low confidence samples")
    for item in semantic_summary["low_confidence_samples"][:50]:
        semantic_lines.append(f"- {item.get('handle')} | {item.get('layer')} | {item.get('category')} | {item.get('reason')}")
    (out / "drawing_semantic_summary.md").write_text("\n".join(semantic_lines), encoding="utf-8")
    paths["semantic_summary_md"] = out / "drawing_semantic_summary.md"
    warning_lines = ["# Warnings", ""] + [f"- {item}" for item in audit["warnings"]]
    (out / "warnings.md").write_text("\n".join(warning_lines), encoding="utf-8")
    paths["warnings_md"] = out / "warnings.md"
    return paths


def build_environment_snapshot() -> dict[str, Any]:
    optional_modules = {}
    for name in ("comtypes", "win32com", "ezdxf", "cad_pyrx", "pyrx", "pandas", "openpyxl"):
        try:
            __import__(name)
            optional_modules[name] = True
        except Exception as exc:
            optional_modules[name] = False
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "optional_modules": optional_modules,
    }
