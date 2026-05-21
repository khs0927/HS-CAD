from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "outputs" / "style_sample_current"


def safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def point(value: Any) -> list[float] | None:
    try:
        vals = list(value)
        return [float(vals[0]), float(vals[1]), float(vals[2]) if len(vals) > 2 else 0.0]
    except Exception:
        return None


def entity_type(object_name: Any) -> str:
    low = str(object_name).lower()
    if "leader" in low:
        return "LEADER"
    if "dim" in low:
        return "DIMENSION"
    if "mtext" in low:
        return "MTEXT"
    if "text" in low:
        return "TEXT"
    if "insert" in low or "block" in low:
        return "INSERT"
    if "lwpolyline" in low or "polyline" in low:
        return "POLYLINE"
    if "line" in low and "poly" not in low:
        return "LINE"
    if "circle" in low:
        return "CIRCLE"
    if "arc" in low:
        return "ARC"
    if "hatch" in low:
        return "HATCH"
    return str(object_name) or "UNKNOWN"


def distance_xy(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b:
        return None
    return math.dist(a[:2], b[:2])


def entity_anchor(obj: Any) -> list[float] | None:
    for attr in ("InsertionPoint", "StartPoint", "Center", "TextAlignmentPoint"):
        p = point(safe_get(obj, attr))
        if p:
            return p
    coords = safe_get(obj, "Coordinates")
    try:
        vals = list(coords)
        if len(vals) >= 2:
            return [float(vals[0]), float(vals[1]), 0.0]
    except Exception:
        pass
    return None


def connect_active_document() -> tuple[Any, Any]:
    import win32com.client  # type: ignore

    app = win32com.client.GetActiveObject("ZWCAD.Application")
    return app, app.ActiveDocument


def find_by_handle(doc: Any, handle: str) -> Any | None:
    try:
        return doc.HandleToObject(handle)
    except Exception:
        pass
    for obj in doc.ModelSpace:
        if str(safe_get(obj, "Handle", "") or "").upper() == handle.upper():
            return obj
    return None


def selected_entity(doc: Any) -> Any | None:
    try:
        ss = doc.ActiveSelectionSet
        if int(safe_get(ss, "Count", 0) or 0) > 0:
            return ss.Item(0)
    except Exception:
        return None
    return None


def top(counter: Counter[Any], limit: int = 20) -> list[list[Any]]:
    return [[k, v] for k, v in counter.most_common(limit)]


def style_row(obj: Any, source_point: list[float] | None = None) -> dict[str, Any]:
    kind = entity_type(safe_get(obj, "ObjectName", ""))
    anchor = entity_anchor(obj)
    return {
        "handle": safe_get(obj, "Handle"),
        "type": kind,
        "layer": safe_get(obj, "Layer"),
        "color": safe_get(obj, "Color"),
        "linetype": safe_get(obj, "Linetype"),
        "lineweight": safe_get(obj, "Lineweight"),
        "style": safe_get(obj, "StyleName"),
        "height": safe_get(obj, "Height"),
        "dimstyle": safe_get(obj, "StyleName") if kind == "DIMENSION" else None,
        "block_name": safe_get(obj, "Name") if kind == "INSERT" else None,
        "effective_name": safe_get(obj, "EffectiveName") if kind == "INSERT" else None,
        "anchor": anchor,
        "distance": distance_xy(source_point, anchor),
    }


def recommended_style(rows: list[dict[str, Any]]) -> dict[str, Any]:
    layers = Counter(row.get("layer") for row in rows if row.get("layer"))
    colors = Counter(str(row.get("color")) for row in rows if row.get("color") is not None)
    linetypes = Counter(row.get("linetype") for row in rows if row.get("linetype"))
    lineweights = Counter(str(row.get("lineweight")) for row in rows if row.get("lineweight") is not None)
    text_heights = Counter(round(float(row["height"]), 3) for row in rows if row.get("height") not in (None, ""))
    dimstyles = Counter(row.get("dimstyle") for row in rows if row.get("dimstyle"))
    return {
        "line_layer": layers.most_common(1)[0][0] if layers else None,
        "line_color": colors.most_common(1)[0][0] if colors else None,
        "line_linetype": linetypes.most_common(1)[0][0] if linetypes else None,
        "lineweight": lineweights.most_common(1)[0][0] if lineweights else None,
        "text_height": text_heights.most_common(1)[0][0] if text_heights else None,
        "dimension_style": dimstyles.most_common(1)[0][0] if dimstyles else None,
        "leader_style": "qleader_l_route",
    }


def sample_style_near_handle(handle: str | None, active_selection: bool, radius: float, out_dir: Path) -> dict[str, Any]:
    _, doc = connect_active_document()
    source = selected_entity(doc) if active_selection else find_by_handle(doc, handle or "")
    if source is None:
        raise SystemExit("No source entity found. Provide --handle or use --active-selection with a selected object.")
    source_point = entity_anchor(source)
    source_row = style_row(source, source_point)
    nearby: list[dict[str, Any]] = []
    for obj in doc.ModelSpace:
        row = style_row(obj, source_point)
        d = row.get("distance")
        if d is None or d > radius:
            continue
        nearby.append(row)

    layers = Counter(row.get("layer") for row in nearby if row.get("layer"))
    entity_types = Counter(row.get("type") for row in nearby if row.get("type"))
    colors = Counter(str(row.get("color")) for row in nearby if row.get("color") is not None)
    linetypes = Counter(row.get("linetype") for row in nearby if row.get("linetype"))
    lineweights = Counter(str(row.get("lineweight")) for row in nearby if row.get("lineweight") is not None)
    text_heights = Counter(round(float(row["height"]), 3) for row in nearby if row.get("height") not in (None, ""))
    text_styles = Counter(row.get("style") for row in nearby if row.get("style"))
    dimstyles = Counter(row.get("dimstyle") for row in nearby if row.get("dimstyle"))
    effective_names = Counter((row.get("effective_name") or row.get("block_name")) for row in nearby if row.get("effective_name") or row.get("block_name"))

    return {
        "doc_name": safe_get(doc, "Name"),
        "full_name": safe_get(doc, "FullName"),
        "source_handle": safe_get(source, "Handle"),
        "source": source_row,
        "radius": radius,
        "nearby_entity_count": len(nearby),
        "dominant_layers": top(layers),
        "dominant_entity_types": top(entity_types),
        "dominant_colors": top(colors),
        "dominant_linetypes": top(linetypes),
        "dominant_lineweights": top(lineweights),
        "text_height_families": top(text_heights),
        "text_styles": top(text_styles),
        "dimension_styles": top(dimstyles),
        "block_effective_names": top(effective_names),
        "nearby_sample": nearby[:120],
        "recommended_generation_style": recommended_style(nearby),
    }


def write_markdown(path: Path, data: dict[str, Any]) -> None:
    lines = [
        "# Local Style Sample",
        "",
        f"- Document: {data.get('doc_name')}",
        f"- Source handle: {data.get('source_handle')}",
        f"- Radius: {data.get('radius')}",
        f"- Nearby entity count: {data.get('nearby_entity_count')}",
        "",
        "## Recommended Generation Style",
    ]
    for key, value in data.get("recommended_generation_style", {}).items():
        lines.append(f"- {key}: {value}")
    for title, key in [
        ("Dominant Layers", "dominant_layers"),
        ("Dominant Entity Types", "dominant_entity_types"),
        ("Dominant Linetypes", "dominant_linetypes"),
        ("Text Height Families", "text_height_families"),
        ("Dimension Styles", "dimension_styles"),
        ("Block Effective Names", "block_effective_names"),
    ]:
        lines += ["", f"## {title}"]
        for item, count in data.get(key, []):
            lines.append(f"- {item}: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Sample local drawing grammar near a handle or active selection.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--handle")
    group.add_argument("--active-selection", action="store_true")
    parser.add_argument("--radius", type=float, default=3000.0)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = sample_style_near_handle(args.handle, args.active_selection, args.radius, out_dir)
    json_path = out_dir / "local_style_sample.json"
    md_path = out_dir / "local_style_sample.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_markdown(md_path, result)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "nearby": result["nearby_entity_count"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
