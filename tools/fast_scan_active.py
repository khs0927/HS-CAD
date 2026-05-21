from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "outputs" / "active_scan_current"


def safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def entity_type(object_name: str) -> str:
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
    return str(object_name) or "UNKNOWN"


def connect_active_document() -> tuple[Any, Any]:
    import win32com.client  # type: ignore

    app = win32com.client.GetActiveObject("ZWCAD.Application")
    return app, app.ActiveDocument


def scan_active_document(out_dir: Path, max_items: int = 50000, progress_every: int = 250) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    progress_path = out_dir / "progress.json"

    _, doc = connect_active_document()
    modelspace = doc.ModelSpace

    layer_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    layer_entity_counts: dict[str, Counter[str]] = defaultdict(Counter)
    block_counts: Counter[str] = Counter()
    text_samples: list[dict[str, Any]] = []
    broken_text: list[dict[str, Any]] = []
    dimensions: list[dict[str, Any]] = []
    leaders: list[dict[str, Any]] = []
    batting: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    start = time.time()
    count = 0
    try:
        total = int(safe_get(modelspace, "Count", 0) or 0)
    except Exception:
        total = None

    for obj in modelspace:
        count += 1
        if progress_every and count % progress_every == 0:
            progress_path.write_text(
                json.dumps(
                    {"count": count, "total": total, "elapsed_seconds": round(time.time() - start, 1)},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if count > max_items:
            warnings.append({"stage": "scan", "warning": "max_items_reached", "max_items": max_items})
            break
        try:
            object_name = str(safe_get(obj, "ObjectName", "") or "")
            kind = entity_type(object_name)
            layer = str(safe_get(obj, "Layer", "<NO_LAYER>") or "<NO_LAYER>")
            handle = str(safe_get(obj, "Handle", "") or "")

            layer_counts[layer] += 1
            entity_counts[kind] += 1
            layer_entity_counts[layer][kind] += 1

            if kind == "INSERT":
                block_name = str(safe_get(obj, "EffectiveName", "") or safe_get(obj, "Name", "") or "")
                if block_name:
                    block_counts[block_name] += 1
            elif kind in {"TEXT", "MTEXT"}:
                value = str(safe_get(obj, "TextString", "") or "")
                row = {
                    "handle": handle,
                    "layer": layer,
                    "text": value,
                    "height": safe_get(obj, "Height"),
                    "style": safe_get(obj, "StyleName"),
                }
                if len(text_samples) < 80:
                    text_samples.append(row)
                if "?" in value or "\ufffd" in value:
                    broken_text.append(row)
            elif kind == "DIMENSION":
                dimensions.append(
                    {
                        "handle": handle,
                        "layer": layer,
                        "measurement": safe_get(obj, "Measurement"),
                        "override": safe_get(obj, "TextOverride"),
                        "scale": safe_get(obj, "ScaleFactor"),
                        "style": safe_get(obj, "StyleName"),
                    }
                )
            elif kind == "LEADER":
                leaders.append({"handle": handle, "layer": layer, "style": safe_get(obj, "StyleName")})

            linetype = str(safe_get(obj, "Linetype", "") or "")
            if linetype.upper() == "BATTING" or "BATTING" in layer.upper():
                batting.append(
                    {
                        "handle": handle,
                        "type": kind,
                        "layer": layer,
                        "linetype": linetype,
                        "ltscale": safe_get(obj, "LinetypeScale"),
                    }
                )
        except Exception as exc:
            warnings.append({"count": count, "error": str(exc)})

    dimension_overrides = [row for row in dimensions if str(row.get("override") or "")]
    return {
        "doc_name": safe_get(doc, "Name"),
        "full_name": safe_get(doc, "FullName"),
        "modelspace_count_reported": total,
        "modelspace_count_scanned": count,
        "elapsed_seconds": round(time.time() - start, 2),
        "layer_count": len(layer_counts),
        "top_layers": layer_counts.most_common(30),
        "entity_counts": dict(entity_counts),
        "layer_entity_counts_top": {layer: dict(counter) for layer, counter in list(layer_entity_counts.items())[:30]},
        "top_blocks": block_counts.most_common(20),
        "dimension_count": len(dimensions),
        "dimension_override_count": len(dimension_overrides),
        "dimension_overrides_sample": dimension_overrides[:20],
        "dimension_measurements_sample": [row.get("measurement") for row in dimensions[:50]],
        "leader_count": len(leaders),
        "batting_related_count": len(batting),
        "batting_sample": batting[:30],
        "text_sample": text_samples[:30],
        "broken_text_count": len(broken_text),
        "broken_text_sample": broken_text[:30],
        "warnings": warnings[:30],
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Fast baseline scan of the active ZWCAD ModelSpace.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--max-items", type=int, default=50000)
    parser.add_argument("--progress-every", type=int, default=250)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    result = scan_active_document(out_dir, max_items=args.max_items, progress_every=args.progress_every)
    result_path = out_dir / "fast_scan.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "result": str(result_path),
                "scanned": result["modelspace_count_scanned"],
                "reported": result["modelspace_count_reported"],
                "elapsed_seconds": result["elapsed_seconds"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
