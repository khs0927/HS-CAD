"""Evidence-bounded live adapter for the explicit xiCAD D1 double-leaf profile."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch16 import (
    DoorLeafDivision,
    DoorRequest,
    DoorSwing,
    DoorVariant,
    SwingDisplay,
    plan_door,
)


class LiveD1LayerEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    color: int
    linetype: str
    locked: bool
    is_xref: bool


class LiveD1PolylineSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vertices: tuple[Point3D, ...]
    layer: str


class LiveD1LineSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: Point3D
    end: Point3D
    layer: str


class LiveD1ArcSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    center: Point3D
    radius: float = Field(gt=0)
    start_angle_radians: float
    sweep_angle_radians: float
    layer: str


class LiveD1Geometry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    frame_and_leaf_polylines: tuple[LiveD1PolylineSpec, ...]
    swing_lines: tuple[LiveD1LineSpec, ...]
    swing_arcs: tuple[LiveD1ArcSpec, ...]
    clear_opening_width: float = Field(gt=0)
    leaf_lengths: tuple[float, float]
    opening_side_sign: int


class LiveD1PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request: DoorRequest
    opening_side_point: Point3D


class LiveD1ExecuteRequest(LiveD1PreviewRequest):
    expected_layers: tuple[LiveD1LayerEvidence, LiveD1LayerEvidence, LiveD1LayerEvidence]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveD1Result(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str
    command_alias: str = "D1"
    created_handles: tuple[str, ...]
    created_object_names: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool
    scope: str = "explicit top-level two-leaf D1 profile"


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _same_elevation(*points: Point3D, tolerance: float = 1e-9) -> bool:
    return max(point.z for point in points) - min(point.z for point in points) <= tolerance


def _vector(start: Point3D, end: Point3D) -> tuple[float, float]:
    return end.x - start.x, end.y - start.y


def _point(base: Point3D, ux: float, uy: float, along: float, nx: float, ny: float, across: float) -> Point3D:
    return Point3D(
        x=base.x + ux * along + nx * across,
        y=base.y + uy * along + ny * across,
        z=base.z,
    )


def _rectangle(
    origin: Point3D,
    ux: float,
    uy: float,
    length: float,
    width: float,
    *,
    centered_across: bool,
) -> tuple[Point3D, ...]:
    nx, ny = -uy, ux
    low = -width / 2 if centered_across else 0.0
    high = width / 2 if centered_across else width
    return (
        _point(origin, ux, uy, 0.0, nx, ny, low),
        _point(origin, ux, uy, length, nx, ny, low),
        _point(origin, ux, uy, length, nx, ny, high),
        _point(origin, ux, uy, 0.0, nx, ny, high),
    )


def _rotated_unit(ux: float, uy: float, angle: float) -> tuple[float, float]:
    cosine, sine = math.cos(angle), math.sin(angle)
    return ux * cosine - uy * sine, ux * sine + uy * cosine


def _leaf_ratios(request: DoorRequest) -> tuple[float, float]:
    if request.leaf_division is DoorLeafDivision.ONE_FIXED:
        raise ValueError("live D1 blocks one_fixed: the current contract has no explicit fixed-leaf width")
    if request.leaf_division is DoorLeafDivision.TWO_TO_ONE:
        return 2 / 3, 1 / 3
    return 0.5, 0.5


def build_live_d1_geometry(request: DoorRequest, opening_side_point: Point3D) -> LiveD1Geometry:
    if request.variant is not DoorVariant.D1:
        raise ValueError("live D1 requires variant=d1")
    if request.swing is not DoorSwing.ONE_WAY:
        raise ValueError("live D1 currently supports one_way swing only")
    if request.group_output:
        raise ValueError("live D1 blocks group_output until group rollback and postconditions are recovered")
    if not math.isclose(request.offset, 0.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("live D1 requires offset=0 because legacy offset acquisition is not recovered")
    if not math.isclose(request.threshold_depth, 0.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("live D1 requires threshold_depth=0 in the bounded plan-view profile")
    if not _same_elevation(request.hinge_point, request.opening_end_point, opening_side_point):
        raise ValueError("live D1 requires all acquisition points on one elevation")

    dx, dy = _vector(request.hinge_point, request.opening_end_point)
    opening_width = math.hypot(dx, dy)
    if opening_width <= 1e-9:
        raise ValueError("live D1 opening baseline must have non-zero length")
    ux, uy = dx / opening_width, dy / opening_width
    side_dx, side_dy = _vector(request.hinge_point, opening_side_point)
    cross = ux * side_dy - uy * side_dx
    if math.isclose(cross, 0.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("live D1 opening_side_point must select a non-collinear swing side")
    side_sign = 1 if cross > 0 else -1

    clear_width = opening_width - 2 * request.frame_width
    if clear_width <= 1e-9:
        raise ValueError("live D1 frame widths consume the entire opening")
    ratios = _leaf_ratios(request)
    leaf_lengths = (clear_width * ratios[0], clear_width * ratios[1])

    nx, ny = -uy * side_sign, ux * side_sign
    left_frame = _rectangle(
        request.hinge_point,
        ux,
        uy,
        request.frame_width,
        request.wall_depth,
        centered_across=True,
    )
    right_frame_origin = _point(
        request.opening_end_point,
        ux,
        uy,
        -request.frame_width,
        nx,
        ny,
        0.0,
    )
    right_frame = _rectangle(
        right_frame_origin,
        ux,
        uy,
        request.frame_width,
        request.wall_depth,
        centered_across=True,
    )

    left_hinge = _point(request.hinge_point, ux, uy, request.frame_width, nx, ny, 0.0)
    right_hinge = _point(request.opening_end_point, ux, uy, -request.frame_width, nx, ny, 0.0)
    angle = math.radians(request.opening_angle_degrees)
    left_ux, left_uy = _rotated_unit(ux, uy, side_sign * angle)
    right_ux, right_uy = _rotated_unit(-ux, -uy, -side_sign * angle)
    left_leaf = _rectangle(
        left_hinge,
        left_ux,
        left_uy,
        leaf_lengths[0],
        request.leaf_thickness,
        centered_across=True,
    )
    right_leaf = _rectangle(
        right_hinge,
        right_ux,
        right_uy,
        leaf_lengths[1],
        request.leaf_thickness,
        centered_across=True,
    )

    frame_and_leaf = tuple(
        LiveD1PolylineSpec(vertices=vertices, layer=request.frame_layer)
        for vertices in (left_frame, right_frame, left_leaf, right_leaf)
    )
    swing_lines: tuple[LiveD1LineSpec, ...] = ()
    swing_arcs: tuple[LiveD1ArcSpec, ...] = ()
    base_angle = math.atan2(uy, ux)
    if request.swing_display is SwingDisplay.ARC:
        swing_arcs = (
            LiveD1ArcSpec(
                center=left_hinge,
                radius=leaf_lengths[0],
                start_angle_radians=base_angle,
                sweep_angle_radians=side_sign * angle,
                layer=request.swing_layer,
            ),
            LiveD1ArcSpec(
                center=right_hinge,
                radius=leaf_lengths[1],
                start_angle_radians=base_angle + math.pi,
                sweep_angle_radians=-side_sign * angle,
                layer=request.swing_layer,
            ),
        )
    elif request.swing_display is SwingDisplay.LINE:
        left_closed = _point(left_hinge, ux, uy, leaf_lengths[0], nx, ny, 0.0)
        left_open = _point(left_hinge, left_ux, left_uy, leaf_lengths[0], nx, ny, 0.0)
        right_closed = _point(right_hinge, -ux, -uy, leaf_lengths[1], nx, ny, 0.0)
        right_open = _point(right_hinge, right_ux, right_uy, leaf_lengths[1], nx, ny, 0.0)
        swing_lines = (
            LiveD1LineSpec(start=left_closed, end=left_open, layer=request.swing_layer),
            LiveD1LineSpec(start=right_closed, end=right_open, layer=request.swing_layer),
        )

    return LiveD1Geometry(
        frame_and_leaf_polylines=frame_and_leaf,
        swing_lines=swing_lines,
        swing_arcs=swing_arcs,
        clear_opening_width=clear_width,
        leaf_lengths=leaf_lengths,
        opening_side_sign=side_sign,
    )


def _drawing(name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _layer(doc: Any, name: str) -> LiveD1LayerEvidence:
    try:
        layer = doc.Layers.Item(name)
    except Exception as exc:
        raise ValueError(f"D1 output layer is unavailable: {name}") from exc
    actual = str(layer.Name)
    state = LiveD1LayerEvidence(
        name=actual,
        color=int(layer.Color),
        linetype=str(layer.Linetype),
        locked=bool(layer.Lock),
        is_xref="|" in actual,
    )
    if state.locked or state.is_xref:
        raise ValueError(f"D1 output layer is locked or xref-dependent: {name}")
    return state


def _layers(doc: Any, request: DoorRequest) -> tuple[LiveD1LayerEvidence, LiveD1LayerEvidence, LiveD1LayerEvidence]:
    return (
        _layer(doc, request.frame_layer),
        _layer(doc, request.swing_layer),
        _layer(doc, request.elevation_layer),
    )


def _payload(
    request: LiveD1PreviewRequest,
    geometry: LiveD1Geometry,
    layers: tuple[LiveD1LayerEvidence, LiveD1LayerEvidence, LiveD1LayerEvidence],
) -> dict[str, Any]:
    return {
        "command_alias": "D1",
        "document_name": request.request.document_id,
        "request": request.request.model_dump(mode="json"),
        "opening_side_point": request.opening_side_point.model_dump(mode="json"),
        "geometry": geometry.model_dump(mode="json"),
        "expected_layers": [item.model_dump(mode="json") for item in layers],
        "scope": "explicit top-level two-leaf D1 profile; no wall cutting, grouping, nested entities, or xrefs",
    }


def preview_live_d1(request: LiveD1PreviewRequest) -> dict[str, Any]:
    if not request.request.dry_run:
        raise ValueError("live D1 preview requires dry_run=true")
    plan_door(request.request)
    geometry = build_live_d1_geometry(request.request, request.opening_side_point)
    doc = _drawing(request.request.document_id)
    layers = _layers(doc, request.request)
    payload = _payload(request, geometry, layers)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "official_help_url": "https://izzarder.com/?page=298",
        "create_count": len(geometry.frame_and_leaf_polylines)
        + len(geometry.swing_lines)
        + len(geometry.swing_arcs),
    }


def _variant_point(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        [float(point.x), float(point.y), float(point.z)],
    )


def _lwpolyline(doc: Any, spec: LiveD1PolylineSpec) -> Any:
    import pythoncom
    import win32com.client

    values = [value for point in spec.vertices for value in (float(point.x), float(point.y))]
    variant = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)
    entity = doc.ModelSpace.AddLightWeightPolyline(variant)
    entity.Elevation = spec.vertices[0].z
    entity.Closed = True
    entity.Layer = spec.layer
    return entity


def _line(doc: Any, spec: LiveD1LineSpec) -> Any:
    entity = doc.ModelSpace.AddLine(_variant_point(spec.start), _variant_point(spec.end))
    entity.Layer = spec.layer
    return entity


def _arc(doc: Any, spec: LiveD1ArcSpec) -> Any:
    start = spec.start_angle_radians
    end = start + spec.sweep_angle_radians
    if spec.sweep_angle_radians < 0:
        start, end = end, start
    entity = doc.ModelSpace.AddArc(_variant_point(spec.center), spec.radius, start % (2 * math.pi), end % (2 * math.pi))
    entity.Layer = spec.layer
    return entity


def execute_live_d1(request: LiveD1ExecuteRequest) -> LiveD1Result:
    geometry = build_live_d1_geometry(request.request, request.opening_side_point)
    preview_request = LiveD1PreviewRequest(request=request.request, opening_side_point=request.opening_side_point)
    payload = _payload(preview_request, geometry, request.expected_layers)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact D1 preview")

    doc = _drawing(request.request.document_id)
    if _layers(doc, request.request) != request.expected_layers:
        raise ValueError("D1 output layer state no longer matches the approved preview")

    created: list[tuple[Any, str, str]] = []
    opened = False
    closed = False
    try:
        doc.StartUndoMark()
        opened = True
        try:
            for spec in geometry.frame_and_leaf_polylines:
                created.append((_lwpolyline(doc, spec), "AcDbPolyline", spec.layer))
            for spec in geometry.swing_lines:
                created.append((_line(doc, spec), "AcDbLine", spec.layer))
            for spec in geometry.swing_arcs:
                created.append((_arc(doc, spec), "AcDbArc", spec.layer))
            for entity, expected_type, expected_layer in created:
                if str(entity.ObjectName).casefold() != expected_type.casefold():
                    raise RuntimeError("D1 postcondition failed: object type differs")
                if str(entity.Layer).casefold() != expected_layer.casefold():
                    raise RuntimeError("D1 postcondition failed: layer differs")
                doc.HandleToObject(str(entity.Handle))
        except Exception:
            for entity, _expected_type, _expected_layer in reversed(created):
                try:
                    entity.Delete()
                except Exception:
                    pass
            raise
    finally:
        if opened:
            doc.EndUndoMark()
            closed = True

    return LiveD1Result(
        document_name=str(doc.Name),
        created_handles=tuple(str(item[0].Handle) for item in created),
        created_object_names=tuple(str(item[0].ObjectName) for item in created),
        undo_mark_opened=opened,
        undo_mark_closed=closed,
        postcondition_verified=True,
    )
