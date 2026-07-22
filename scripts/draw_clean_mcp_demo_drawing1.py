from __future__ import annotations

import json
import math
import sys
from typing import Any

import pythoncom
import win32com.client

DOCUMENT_NAME = "Drawing1.dwg"
MIN_TEXT_HEIGHT = 250.0
MIN_LEADER_SEPARATION = 2500.0

WALL_LAYER = "HSCAD_MCP_WALL"
DOOR_LAYER = "HSCAD_MCP_DOOR"
TEXT_LAYER = "HSCAD_MCP_TEXT"
ANNO_LAYER = "HSCAD_MCP_ANNO"
LEADER_TEXTS = ("1000,1000,1000", "3000")
LEADER_ANCHORS = ((7200.0, 6300.0), (10200.0, 2900.0))
LEADER_ROUTES = (
    ((1000.0, 1000.0, 0.0), (1000.0, 6000.0, 0.0), (7000.0, 6000.0, 0.0)),
    ((3000.0, 2000.0, 0.0), (7600.0, 1600.0, 0.0), (10100.0, 2600.0, 0.0)),
)


def _point(x: float, y: float, z: float = 0.0) -> Any:
    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        (float(x), float(y), float(z)),
    )


def _points(*coordinates: tuple[float, float, float]) -> Any:
    flattened = tuple(value for point in coordinates for value in point)
    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        flattened,
    )


def _get_drawing1(app: Any) -> Any:
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == DOCUMENT_NAME.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {DOCUMENT_NAME}, found {len(matches)}")
    return matches[0]


def _ensure_layer(doc: Any, name: str, color: int, lineweight: int) -> Any:
    try:
        layer = doc.Layers.Item(name)
    except Exception:
        layer = doc.Layers.Add(name)
    layer.Color = color
    try:
        layer.Lineweight = lineweight
    except Exception:
        # Some ZWCAD editions expose layer color but not writable COM lineweight.
        pass
    return layer


def _add_line(modelspace: Any, start: tuple[float, float], end: tuple[float, float], layer: str) -> Any:
    entity = modelspace.AddLine(_point(*start), _point(*end))
    entity.Layer = layer
    return entity


def _add_mtext(
    modelspace: Any,
    anchor: tuple[float, float],
    width: float,
    text: str,
    height: float,
    layer: str,
) -> Any:
    if height < MIN_TEXT_HEIGHT:
        raise ValueError(f"MText height must be at least {MIN_TEXT_HEIGHT}")
    entity = modelspace.AddMText(_point(*anchor), width, text)
    entity.Height = height
    entity.Layer = layer
    return entity


def _add_leader_annotation(
    modelspace: Any,
    arrow: tuple[float, float, float],
    elbow: tuple[float, float, float],
    landing: tuple[float, float, float],
    anchor: tuple[float, float],
    text: str,
) -> tuple[Any, Any]:
    annotation = _add_mtext(modelspace, anchor, 2400.0, text, 300.0, ANNO_LAYER)
    leader = modelspace.AddLeader(_points(arrow, elbow, landing), annotation, 1)
    leader.Layer = ANNO_LAYER
    return leader, annotation


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(first[0] - second[0], first[1] - second[1])


def _validate_demo(
    doc: Any,
    created: list[Any],
    leaders: tuple[Any, Any],
    annotations: tuple[Any, Any],
    anchors: tuple[tuple[float, float], tuple[float, float]],
    landings: tuple[tuple[float, float], tuple[float, float]],
) -> dict[str, Any]:
    after = {str(entity.Handle).casefold(): entity for entity in doc.ModelSpace}
    handles = tuple(str(entity.Handle) for entity in created)
    if len(after) != len(created) or not all(handle.casefold() in after for handle in handles):
        raise RuntimeError("created-object postcondition failed")

    if any(str(leader.ObjectName).casefold() != "acdbleader" for leader in leaders):
        raise RuntimeError("expected two actual AcDbLeader objects")
    if any(str(annotation.ObjectName).casefold() != "acdbmtext" for annotation in annotations):
        raise RuntimeError("expected two actual AcDbMText annotations")

    expected_text = ("1000,1000,1000", "3000")
    if tuple(str(annotation.TextString) for annotation in annotations) != expected_text:
        raise RuntimeError("leader annotation text postcondition failed")
    if any(float(annotation.Height) < MIN_TEXT_HEIGHT for annotation in annotations):
        raise RuntimeError("leader annotation height postcondition failed")
    if any(str(entity.Layer) != ANNO_LAYER for entity in (*leaders, *annotations)):
        raise RuntimeError("leader annotation layer postcondition failed")

    actual_anchors = tuple(
        (float(annotation.InsertionPoint[0]), float(annotation.InsertionPoint[1])) for annotation in annotations
    )
    actual_landings = tuple((float(leader.Coordinates[-3]), float(leader.Coordinates[-2])) for leader in leaders)
    if any(_distance(actual, expected) > 1e-6 for actual, expected in zip(actual_anchors, anchors, strict=True)):
        raise RuntimeError("leader text anchor postcondition failed")
    # ZWCAD snaps the final leader vertex to the attached MText boundary.
    # Verify the actual attachment is close to its approved anchor instead of
    # requiring the pre-attachment input vertex byte-for-byte.
    attachment_distances = tuple(
        _distance(actual, anchor) for actual, anchor in zip(actual_landings, actual_anchors, strict=True)
    )
    if any(distance > 600.0 for distance in attachment_distances):
        raise RuntimeError("leader landing is too far from its annotation anchor")

    delta_x = abs(actual_anchors[0][0] - actual_anchors[1][0])
    delta_y = abs(actual_anchors[0][1] - actual_anchors[1][1])
    landing_distance = _distance(actual_landings[0], actual_landings[1])
    if delta_x < MIN_LEADER_SEPARATION or delta_y < MIN_LEADER_SEPARATION:
        raise RuntimeError("leader text anchors are not sufficiently separated in both X and Y")
    if landing_distance < MIN_LEADER_SEPARATION:
        raise RuntimeError("leader landings are not sufficiently separated")

    counts: dict[str, int] = {}
    for entity in created:
        object_name = str(entity.ObjectName)
        counts[object_name] = counts.get(object_name, 0) + 1
    folded_counts = {name.casefold(): count for name, count in counts.items()}
    expected_counts = {"acdbline": 13, "acdbarc": 1, "acdbmtext": 5, "acdbleader": 2}
    if folded_counts != expected_counts:
        raise RuntimeError(f"unexpected demo object counts: {counts}")
    return {
        "handles": handles,
        "object_type_counts": counts,
        "leader_anchor_delta": {"x": delta_x, "y": delta_y},
        "leader_landing_distance": landing_distance,
        "leader_attachment_distances": attachment_distances,
    }


def draw_clean_demo() -> dict[str, Any]:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    doc = _get_drawing1(app)
    doc.Activate()
    modelspace = doc.ModelSpace
    before_count = int(modelspace.Count)
    anchors = LEADER_ANCHORS
    landings = tuple((route[-1][0], route[-1][1]) for route in LEADER_ROUTES)
    if before_count != 0:
        existing = list(modelspace)
        found_leaders = tuple(
            entity
            for entity in existing
            if str(entity.Layer) == ANNO_LAYER and str(entity.ObjectName).casefold() == "acdbleader"
        )
        found_annotations = tuple(
            entity
            for entity in existing
            if str(entity.Layer) == ANNO_LAYER and str(entity.ObjectName).casefold() == "acdbmtext"
        )
        if len(found_leaders) != 2 or len(found_annotations) != 2:
            raise RuntimeError(
                f"refusing to draw over non-empty {DOCUMENT_NAME}: found {before_count} objects without exact demo signature"
            )
        annotation_by_text = {str(entity.TextString): entity for entity in found_annotations}
        if set(annotation_by_text) != set(LEADER_TEXTS):
            raise RuntimeError("existing demo leader texts do not match the approved layout")
        annotations = tuple(annotation_by_text[text] for text in LEADER_TEXTS)
        leader_by_annotation = {str(entity.Annotation.Handle).casefold(): entity for entity in found_leaders}
        leaders = tuple(leader_by_annotation[str(annotation.Handle).casefold()] for annotation in annotations)
        doc.StartUndoMark()
        try:
            for annotation, anchor in zip(annotations, anchors, strict=True):
                annotation.InsertionPoint = _point(*anchor)
            for leader, route in zip(leaders, LEADER_ROUTES, strict=True):
                leader.Coordinates = _points(*route)
        finally:
            doc.EndUndoMark()
        verification = _validate_demo(doc, existing, leaders, annotations, anchors, landings)
        doc.Regen(1)
        app.ZoomExtents()
        return {
            "status": "existing_ok",
            "document": str(doc.Name),
            "before_count": before_count,
            "after_count": int(modelspace.Count),
            "created_count": 0,
            "layers": (WALL_LAYER, DOOR_LAYER, TEXT_LAYER, ANNO_LAYER),
            "room_size": {"width": 6000.0, "height": 4000.0},
            "undo_group_created": True,
            "saved": bool(doc.Saved),
            "postcondition_verified": True,
            **verification,
        }

    created: list[Any] = []
    leaders: list[Any] = []
    annotations: list[Any] = []
    doc.StartUndoMark()
    try:
        _ensure_layer(doc, WALL_LAYER, 7, 50)
        _ensure_layer(doc, DOOR_LAYER, 3, 35)
        _ensure_layer(doc, TEXT_LAYER, 2, 25)
        _ensure_layer(doc, ANNO_LAYER, 4, 25)

        # 6000 x 4000 room, double-line 200-unit wall with a 1000-unit opening.
        wall_segments = (
            ((0.0, 0.0), (0.0, 4000.0)),
            ((200.0, 200.0), (200.0, 3800.0)),
            ((0.0, 4000.0), (6000.0, 4000.0)),
            ((200.0, 3800.0), (5800.0, 3800.0)),
            ((6000.0, 0.0), (6000.0, 4000.0)),
            ((5800.0, 200.0), (5800.0, 3800.0)),
            ((0.0, 0.0), (2500.0, 0.0)),
            ((3500.0, 0.0), (6000.0, 0.0)),
            ((200.0, 200.0), (2500.0, 200.0)),
            ((3500.0, 200.0), (5800.0, 200.0)),
            ((2500.0, 0.0), (2500.0, 200.0)),
            ((3500.0, 0.0), (3500.0, 200.0)),
        )
        created.extend(_add_line(modelspace, start, end, WALL_LAYER) for start, end in wall_segments)

        # Door leaf and 90-degree swing arc at the opening.
        created.append(_add_line(modelspace, (2500.0, 200.0), (2500.0, 1200.0), DOOR_LAYER))
        swing = modelspace.AddArc(_point(2500.0, 200.0), 1000.0, 0.0, math.pi / 2)
        swing.Layer = DOOR_LAYER
        created.append(swing)

        created.append(_add_mtext(modelspace, (0.0, 4850.0), 6000.0, "HS-CAD / xiCAD MCP DEMO", 350.0, TEXT_LAYER))
        created.append(_add_mtext(modelspace, (2200.0, 2700.0), 2200.0, "ROOM 101", 300.0, TEXT_LAYER))
        created.append(_add_mtext(modelspace, (2200.0, 2200.0), 2200.0, "AREA 24.00 m2", 280.0, TEXT_LAYER))

        leader_specs = tuple(
            (*route, anchor, text)
            for route, anchor, text in zip(LEADER_ROUTES, anchors, LEADER_TEXTS, strict=True)
        )
        for arrow, elbow, landing, anchor, text in leader_specs:
            leader, annotation = _add_leader_annotation(modelspace, arrow, elbow, landing, anchor, text)
            leaders.append(leader)
            annotations.append(annotation)
            created.extend((annotation, leader))
    finally:
        doc.EndUndoMark()

    verification = _validate_demo(
        doc,
        created,
        (leaders[0], leaders[1]),
        (annotations[0], annotations[1]),
        anchors,
        landings,
    )
    doc.Regen(1)
    app.ZoomExtents()
    return {
        "status": "ok",
        "document": str(doc.Name),
        "before_count": before_count,
        "after_count": int(modelspace.Count),
        "created_count": len(created),
        "layers": (WALL_LAYER, DOOR_LAYER, TEXT_LAYER, ANNO_LAYER),
        "room_size": {"width": 6000.0, "height": 4000.0},
        "undo_group_created": True,
        "saved": bool(doc.Saved),
        "postcondition_verified": True,
        **verification,
    }


def main() -> int:
    try:
        result = draw_clean_demo()
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
