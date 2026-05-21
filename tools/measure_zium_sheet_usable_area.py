from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "outputs" / "zium_sheet_area_current"
DEFAULT_BLOCK = "ZIUM_sheet_architect"
DEFAULT_LAYER = "A-FORM"


def get_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return default


def as_point(value: Any) -> list[float] | None:
    try:
        items = list(value)
        return [float(items[0]), float(items[1]), float(items[2]) if len(items) > 2 else 0.0]
    except Exception:
        return None


def bbox(points: list[list[float]]) -> list[float] | None:
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def transform_bbox(box: list[float] | None, origin: list[float] | None, sx: float, sy: float) -> list[float] | None:
    if not box or not origin:
        return None
    return [origin[0] + box[0] * sx, origin[1] + box[1] * sy, origin[0] + box[2] * sx, origin[1] + box[3] * sy]


def entity_points(obj: Any) -> list[list[float]]:
    pts: list[list[float]] = []
    for name in ("StartPoint", "EndPoint", "Center", "InsertionPoint"):
        p = as_point(get_attr(obj, name))
        if p:
            pts.append(p)
    try:
        values = list(get_attr(obj, "Coordinates"))
        for i in range(0, len(values) - 1, 2):
            pts.append([float(values[i]), float(values[i + 1]), 0.0])
    except Exception:
        pass
    return pts


def connect_active_document() -> tuple[Any, Any]:
    import win32com.client  # type: ignore
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    return app, app.ActiveDocument


def analyze_block_definition(doc: Any, block_name: str) -> dict[str, Any]:
    try:
        block = doc.Blocks.Item(block_name)
    except Exception as exc:
        return {"exists": False, "error": str(exc), "entity_count": 0, "extents": None, "title_block_bbox": None, "usable_drawing_area_bbox": None}
    pts: list[list[float]] = []
    count = 0
    for obj in block:
        count += 1
        pts.extend(entity_points(obj))
    ext = bbox(pts)
    title = None
    usable = None
    if ext:
        minx, miny, maxx, maxy = ext
        w = maxx - minx
        h = maxy - miny
        title_pts = [p for p in pts if p[0] > minx + w * 0.55 and p[1] < miny + h * 0.35]
        title = bbox(title_pts) or [maxx - w * 0.38, miny, maxx, miny + h * 0.22]
        margin_x = w * 0.035
        margin_y = h * 0.04
        usable = [minx + margin_x, max(title[3] + margin_y * 0.5, miny + margin_y), maxx - margin_x, maxy - margin_y]
    return {"exists": True, "entity_count": count, "extents": ext, "title_block_bbox": title, "usable_drawing_area_bbox": usable, "needs_visual_check": ext is None}


def insert_row(obj: Any, definition: dict[str, Any]) -> dict[str, Any]:
    origin = as_point(get_attr(obj, "InsertionPoint"))
    sx = float(get_attr(obj, "XScaleFactor", 1.0) or 1.0)
    sy = float(get_attr(obj, "YScaleFactor", 1.0) or 1.0)
    return {
        "handle": get_attr(obj, "Handle"),
        "block": get_attr(obj, "EffectiveName") or get_attr(obj, "Name"),
        "layer": get_attr(obj, "Layer"),
        "insert": origin,
        "x_scale": sx,
        "y_scale": sy,
        "rotation": get_attr(obj, "Rotation"),
        "modelspace_extents": transform_bbox(definition.get("extents"), origin, sx, sy),
        "modelspace_title_block_bbox": transform_bbox(definition.get("title_block_bbox"), origin, sx, sy),
        "modelspace_usable_drawing_area_bbox": transform_bbox(definition.get("usable_drawing_area_bbox"), origin, sx, sy),
    }


def measure(block_name: str, layer_name: str) -> dict[str, Any]:
    _, doc = connect_active_document()
    definition = analyze_block_definition(doc, block_name)
    inserts: list[dict[str, Any]] = []
    scales: Counter[str] = Counter()
    layers: Counter[str] = Counter()
    for obj in doc.ModelSpace:
        obj_name = str(get_attr(obj, "ObjectName", "") or "").lower()
        if "insert" not in obj_name and "block" not in obj_name:
            continue
        name = str(get_attr(obj, "EffectiveName", "") or get_attr(obj, "Name", "") or "")
        if name != block_name:
            continue
        row = insert_row(obj, definition)
        inserts.append(row)
        scales[f"{row['x_scale']:.6g}/{row['y_scale']:.6g}"] += 1
        layers[str(row.get("layer"))] += 1
    return {
        "doc_name": get_attr(doc, "Name"),
        "full_name": get_attr(doc, "FullName"),
        "block_name": block_name,
        "expected_insert_layer": layer_name,
        "block_definition": definition,
        "insert_count": len(inserts),
        "insert_layers": layers.most_common(),
        "scale_distribution": scales.most_common(),
        "inserts_sample": inserts[:120],
        "representative_usable_area": inserts[0].get("modelspace_usable_drawing_area_bbox") if inserts else None,
        "needs_visual_check": bool(definition.get("needs_visual_check")) or not inserts,
    }


def write_md(path: Path, data: dict[str, Any]) -> None:
    definition = data.get("block_definition", {})
    lines = [
        "# ZIUM Sheet Usable Area",
        "",
        f"- Document: {data.get('doc_name')}",
        f"- Block: {data.get('block_name')}",
        f"- Definition exists: {definition.get('exists')}",
        f"- Insert count: {data.get('insert_count')}",
        f"- Needs visual check: {data.get('needs_visual_check')}",
        "",
        "## Definition BBoxes",
        f"- Extents: {definition.get('extents')}",
        f"- Title block bbox: {definition.get('title_block_bbox')}",
        f"- Usable drawing area bbox: {definition.get('usable_drawing_area_bbox')}",
        "",
        "## Scale Distribution",
    ]
    for scale, count in data.get("scale_distribution", []):
        lines.append(f"- {scale}: {count}")
    lines += ["", "## Representative Usable Area", str(data.get("representative_usable_area"))]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Measure usable drawing area for ZIUM sheet inserts.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--block-name", default=DEFAULT_BLOCK)
    parser.add_argument("--layer-name", default=DEFAULT_LAYER)
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = measure(args.block_name, args.layer_name)
    json_path = out_dir / "zium_sheet_usable_area.json"
    md_path = out_dir / "zium_sheet_usable_area.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_md(md_path, result)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "insert_count": result["insert_count"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
