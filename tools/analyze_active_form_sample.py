from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pythoncom
import win32com.client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "outputs" / "active_form_analysis_current"


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
    if "ellipse" in low:
        return "ELLIPSE"
    return str(object_name) or "UNKNOWN"


def selection_set(doc: Any, name: str) -> Any:
    try:
        for existing in doc.SelectionSets:
            if existing.Name == name:
                existing.Delete()
                break
    except Exception:
        pass
    return doc.SelectionSets.Add(name)


def select_block_inserts(doc: Any, block_name: str) -> dict[str, Any]:
    ss = selection_set(doc, "HS_FORM_BLOCK_SAMPLE")
    filter_types = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [0, 2])
    filter_data = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, ["INSERT", block_name])
    try:
        ss.Select(5, None, None, filter_types, filter_data)
    except Exception as exc:
        return {"error": str(exc), "count": 0, "items": []}
    items = [_insert_row(obj) for obj in ss]
    try:
        ss.Delete()
    except Exception:
        pass
    return {"count": len(items), "items": items}


def select_layer_inserts(doc: Any, layer: str) -> dict[str, Any]:
    ss = selection_set(doc, "HS_FORM_LAYER_SAMPLE")
    filter_types = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [0, 8])
    filter_data = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, ["INSERT", layer])
    try:
        ss.Select(5, None, None, filter_types, filter_data)
    except Exception as exc:
        return {"error": str(exc), "count": 0, "items": []}
    items = [_insert_row(obj) for obj in ss]
    try:
        ss.Delete()
    except Exception:
        pass
    return {"count": len(items), "items": items}


def _insert_row(obj: Any) -> dict[str, Any]:
    return {
        "handle": safe_get(obj, "Handle"),
        "block": safe_get(obj, "EffectiveName") or safe_get(obj, "Name"),
        "layer": safe_get(obj, "Layer"),
        "insert": point(safe_get(obj, "InsertionPoint")),
        "x_scale": safe_get(obj, "XScaleFactor"),
        "y_scale": safe_get(obj, "YScaleFactor"),
        "rotation": safe_get(obj, "Rotation"),
    }


def analyze(sample_target: int, title_block: str, title_layer: str) -> dict[str, Any]:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    modelspace = doc.ModelSpace
    total = int(safe_get(modelspace, "Count", 0) or 0)
    step = max(1, total // max(1, sample_target))

    type_counts: Counter[str] = Counter()
    style_counts: Counter[tuple[str, str, str, str]] = Counter()
    color_counts: Counter[str] = Counter()
    linetype_counts: Counter[str] = Counter()
    lineweight_counts: Counter[str] = Counter()
    line_lengths: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    text_heights: Counter[float] = Counter()
    dim_styles: Counter[str] = Counter()
    leader_styles: Counter[str] = Counter()
    block_counts: Counter[str] = Counter()
    dim_samples: list[dict[str, Any]] = []
    block_samples: list[dict[str, Any]] = []
    batting_samples: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    start = time.time()
    sampled = 0
    for index in range(0, total, step):
        try:
            obj = modelspace.Item(index)
            sampled += 1
            kind = entity_type(safe_get(obj, "ObjectName", ""))
            color = str(safe_get(obj, "Color", ""))
            linetype = str(safe_get(obj, "Linetype", "") or "BYLAYER")
            lineweight = str(safe_get(obj, "Lineweight", ""))
            layer = str(safe_get(obj, "Layer", "") or "")
            key = (kind, color, linetype, lineweight)

            type_counts[kind] += 1
            style_counts[key] += 1
            color_counts[color] += 1
            linetype_counts[linetype] += 1
            lineweight_counts[lineweight] += 1

            if kind == "LINE":
                start_point = point(safe_get(obj, "StartPoint"))
                end_point = point(safe_get(obj, "EndPoint"))
                if start_point and end_point:
                    line_lengths[key].append(math.dist(start_point[:2], end_point[:2]))
            elif kind in {"TEXT", "MTEXT"}:
                try:
                    text_heights[round(float(safe_get(obj, "Height")), 3)] += 1
                except Exception:
                    pass
            elif kind == "DIMENSION":
                dim_styles[str(safe_get(obj, "StyleName", ""))] += 1
                if len(dim_samples) < 80:
                    dim_samples.append(
                        {
                            "handle": safe_get(obj, "Handle"),
                            "style": safe_get(obj, "StyleName"),
                            "scale": safe_get(obj, "ScaleFactor"),
                            "override": safe_get(obj, "TextOverride"),
                            "measurement": safe_get(obj, "Measurement"),
                        }
                    )
            elif kind == "LEADER":
                leader_styles[str(safe_get(obj, "StyleName", ""))] += 1
            elif kind == "INSERT":
                block = str(safe_get(obj, "EffectiveName", "") or safe_get(obj, "Name", "") or "")
                block_counts[block] += 1
                if len(block_samples) < 80:
                    block_samples.append(_insert_row(obj))

            if linetype.upper() == "BATTING" or "BATTING" in layer.upper():
                batting_samples.append(
                    {
                        "handle": safe_get(obj, "Handle"),
                        "kind": kind,
                        "layer": layer,
                        "linetype": linetype,
                        "ltscale": safe_get(obj, "LinetypeScale"),
                    }
                )
        except Exception as exc:
            errors.append({"index": index, "error": str(exc)})

    line_stats = []
    for key, lengths in line_lengths.items():
        if not lengths:
            continue
        sorted_lengths = sorted(lengths)
        line_stats.append(
            {
                "kind": key[0],
                "color": key[1],
                "linetype": key[2],
                "lineweight": key[3],
                "count": len(sorted_lengths),
                "min": round(sorted_lengths[0], 3),
                "median": round(sorted_lengths[len(sorted_lengths) // 2], 3),
                "max": round(sorted_lengths[-1], 3),
            }
        )
    line_stats.sort(key=lambda item: item["count"], reverse=True)

    return {
        "doc_name": safe_get(doc, "Name"),
        "full_name": safe_get(doc, "FullName"),
        "modelspace_count": total,
        "sample_target": sample_target,
        "sample_step": step,
        "sampled": sampled,
        "elapsed_seconds": round(time.time() - start, 2),
        "sample_entity_counts": type_counts.most_common(),
        "sample_style_counts_top": [
            {"kind": key[0], "color": key[1], "linetype": key[2], "lineweight": key[3], "sample_count": count}
            for key, count in style_counts.most_common(80)
        ],
        "sample_color_counts": color_counts.most_common(40),
        "sample_linetype_counts": linetype_counts.most_common(40),
        "sample_lineweight_counts": lineweight_counts.most_common(40),
        "sample_line_length_stats_top": line_stats[:80],
        "sample_text_heights_top": text_heights.most_common(50),
        "sample_dim_styles": dim_styles.most_common(30),
        "sample_dimensions": dim_samples,
        "sample_leader_styles": leader_styles.most_common(30),
        "sample_block_counts": block_counts.most_common(30),
        "sample_blocks": block_samples,
        "sample_batting": batting_samples[:50],
        "title_block_inserts": select_block_inserts(doc, title_block),
        "title_layer_inserts": select_layer_inserts(doc, title_layer),
        "errors": errors[:30],
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Analyze active ZWCAD sheet form and line expression by sampling.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--sample-target", type=int, default=3000)
    parser.add_argument("--title-block", default="ZIUM_sheet_architect")
    parser.add_argument("--title-layer", default="A-FORM")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = analyze(args.sample_target, args.title_block, args.title_layer)
    path = out_dir / "sample_form_analysis.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(path),
                "doc": result["doc_name"],
                "modelspace_count": result["modelspace_count"],
                "sampled": result["sampled"],
                "title_block_count": result["title_block_inserts"]["count"],
                "elapsed_seconds": result["elapsed_seconds"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
