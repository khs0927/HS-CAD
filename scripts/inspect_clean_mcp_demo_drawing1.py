from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from typing import Any

DEFAULT_DOCUMENT = "Drawing1.dwg"
DEFAULT_DEMO_LAYER = "HSCAD_MCP_ANNO"
EXPECTED_TEXTS = {"1000,1000,1000", "3000"}
MTEXT_NAMES = {"acdbmtext"}
LEADER_NAMES = {"acdb2dleader", "acdbleader"}


def _point(value: Any) -> tuple[float, float, float]:
    values = tuple(float(item) for item in value)
    if len(values) < 2:
        raise ValueError("point must contain at least x and y")
    return values[0], values[1], values[2] if len(values) > 2 else 0.0


def _overall_bbox(objects: list[dict[str, Any]]) -> dict[str, list[float]] | None:
    boxes = [item["bbox"] for item in objects if item.get("bbox") is not None]
    if not boxes:
        return None
    minimum = [min(box["min"][axis] for box in boxes) for axis in range(3)]
    maximum = [max(box["max"][axis] for box in boxes) for axis in range(3)]
    return {
        "min": minimum,
        "max": maximum,
        "size": [maximum[axis] - minimum[axis] for axis in range(3)],
    }


def validate_demo_snapshot(
    *,
    document: str,
    layer: str,
    cmdactive: int,
    objects: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate normalized read-only evidence without requiring COM."""
    type_counts = Counter(str(item["object_name"]) for item in objects)
    mtexts = [item for item in objects if str(item["object_name"]).casefold() in MTEXT_NAMES]
    leaders = [item for item in objects if str(item["object_name"]).casefold() in LEADER_NAMES]
    errors: list[str] = []

    if cmdactive != 0:
        errors.append(f"CMDACTIVE must be 0, got {cmdactive}")
    if len(mtexts) != 2:
        errors.append(f"expected exactly 2 MText objects, got {len(mtexts)}")
    if len(leaders) != 2:
        errors.append(f"expected exactly 2 Leader objects, got {len(leaders)}")
    if len(objects) != len(mtexts) + len(leaders):
        errors.append("demo layer contains object types other than MText and Leader")

    texts = {str(item.get("text", "")).strip() for item in mtexts}
    if texts != EXPECTED_TEXTS:
        errors.append(f"MText contents must be {sorted(EXPECTED_TEXTS)!r}, got {sorted(texts)!r}")
    for item in mtexts:
        height = item.get("text_height")
        if height is None or float(height) < 250:
            errors.append(f"MText {item['handle']} height must be >= 250")

    insertion_distance = None
    if len(mtexts) == 2 and all(item.get("insertion_point") is not None for item in mtexts):
        first, second = mtexts[0]["insertion_point"], mtexts[1]["insertion_point"]
        insertion_distance = math.dist(first, second)
        if insertion_distance < 2500:
            errors.append(f"MText insertion-point distance must be >= 2500, got {insertion_distance}")
    elif len(mtexts) == 2:
        errors.append("both MText objects must expose insertion points")

    mtext_handles = {str(item["handle"]).casefold() for item in mtexts}
    annotation_handles = [
        str(item["annotation_handle"]).casefold() if item.get("annotation_handle") else None for item in leaders
    ]
    for item, annotation_handle in zip(leaders, annotation_handles, strict=True):
        if annotation_handle is None:
            errors.append(f"Leader {item['handle']} has no annotation connection")
        elif annotation_handle not in mtext_handles:
            errors.append(f"Leader {item['handle']} annotation is outside the demo MText set")
    if len(leaders) == 2 and set(annotation_handles) != mtext_handles:
        errors.append("the two Leaders must connect one-to-one to the two demo MText objects")

    bbox = _overall_bbox(objects)
    if bbox is None:
        errors.append("overall demo bounding box is unavailable")

    return {
        "ok": not errors,
        "document": document,
        "demo_layer": layer,
        "cmdactive": cmdactive,
        "object_count": len(objects),
        "type_counts": dict(sorted(type_counts.items())),
        "mtexts": [
            {
                "handle": item["handle"],
                "text": item.get("text"),
                "text_height": item.get("text_height"),
                "insertion_point": item.get("insertion_point"),
            }
            for item in mtexts
        ],
        "mtext_insertion_distance": insertion_distance,
        "leaders": [
            {"handle": item["handle"], "annotation_handle": item.get("annotation_handle")} for item in leaders
        ],
        "overall_bbox": bbox,
        "errors": errors,
    }


def _entity_bbox(entity: Any) -> dict[str, list[float]] | None:
    try:
        minimum, maximum = entity.GetBoundingBox()
        return {"min": list(_point(minimum)), "max": list(_point(maximum))}
    except Exception:
        return None


def _annotation_handle(entity: Any) -> str | None:
    try:
        annotation = entity.Annotation
        if annotation is None:
            return None
        return str(annotation.Handle)
    except Exception:
        return None


def _text_height(entity: Any) -> float | None:
    for property_name in ("TextHeight", "Height"):
        try:
            return float(getattr(entity, property_name))
        except Exception:
            continue
    return None


def inspect_open_drawing(document_name: str, layer_name: str) -> dict[str, Any]:
    """Collect read-only COM evidence from one uniquely open ZWCAD document."""
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    documents = [doc for doc in app.Documents if str(doc.Name).casefold() == document_name.casefold()]
    if len(documents) != 1:
        raise RuntimeError(f"expected exactly one open {document_name!r}, found {len(documents)}")
    doc = documents[0]
    objects: list[dict[str, Any]] = []
    for entity in doc.ModelSpace:
        if str(entity.Layer).casefold() != layer_name.casefold():
            continue
        object_name = str(entity.ObjectName)
        row: dict[str, Any] = {
            "handle": str(entity.Handle),
            "object_name": object_name,
            "bbox": _entity_bbox(entity),
        }
        if object_name.casefold() in MTEXT_NAMES:
            row.update(
                text=str(entity.TextString),
                text_height=_text_height(entity),
                insertion_point=list(_point(entity.InsertionPoint)),
            )
        elif object_name.casefold() in LEADER_NAMES:
            row["annotation_handle"] = _annotation_handle(entity)
        objects.append(row)
    return validate_demo_snapshot(
        document=str(doc.Name),
        layer=layer_name,
        cmdactive=int(doc.GetVariable("CMDACTIVE")),
        objects=objects,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only validation of the clean HS-CAD MCP demo in Drawing1.dwg")
    parser.add_argument("--document", default=DEFAULT_DOCUMENT)
    parser.add_argument("--layer", default=DEFAULT_DEMO_LAYER)
    args = parser.parse_args()
    try:
        report = inspect_open_drawing(args.document, args.layer)
    except Exception as exc:
        report = {
            "ok": False,
            "document": args.document,
            "demo_layer": args.layer,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
