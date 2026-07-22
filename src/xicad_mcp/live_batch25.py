from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch25a import (
    CommonTextRequest,
    EnergyAreaTableRequest,
    SlopeRequest,
    SpecialCharacterRequest,
    TextOnObjectRequest,
    TextPointIncrementRequest,
    plan_common_text,
    plan_energy_area_table,
    plan_slope,
    plan_special_character,
    plan_text_on_object,
    plan_text_point_increment,
)
from .headless_core_batch25b import (
    BoundingBoxRequest,
    MakeTextLinetypeRequest,
    PerpendicularCurveRequest,
    PolylineCloseRequest,
    TextBoxRequest,
    TextsToTableRequest,
    plan_bounding_box,
    plan_make_text_linetype,
    plan_perpendicular_curve,
    plan_polyline_close,
    plan_text_box,
    plan_texts_to_table,
)

ExecutableRequest = (
    SlopeRequest
    | CommonTextRequest
    | SpecialCharacterRequest
    | TextPointIncrementRequest
    | TextOnObjectRequest
    | BoundingBoxRequest
    | PolylineCloseRequest
    | PerpendicularCurveRequest
)


class LiveEntityEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    object_name: str
    layer: str
    geometry_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    locked_layer: bool
    is_xref: bool


class LiveLayerEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    locked: bool
    is_xref: bool


class LiveBatch25ExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ExecutableRequest
    expected_sources: tuple[LiveEntityEvidence, ...]
    expected_target_layers: tuple[LiveLayerEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch25Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    changed_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


BLOCKED = {
    "ZAE": "compiled area classification, summation, hatch mapping, and exact table construction are unrecovered",
    "TTT": "compiled frame recognition, row/column clustering, table geometry, and multi-file output are unrecovered",
    "TX": "compiled text extents, shape/mask construction, draw order, grouping, and associative linkage are unrecovered",
    "MTLT": "compiled pattern derivation, LIN serialization, loading, and replacement behavior are unrecovered",
}


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _drawing(name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _entities(doc: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for block in doc.Blocks:
        if bool(block.IsLayout):
            for entity in block:
                result[str(entity.Handle).casefold()] = entity
    return result


def _json_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return [_json_value(item) for item in value]
    except TypeError:
        return str(value)


def _geometry_fingerprint(entity: Any) -> str:
    payload: dict[str, Any] = {}
    for name in (
        "Coordinates", "StartPoint", "EndPoint", "Center", "Radius", "StartAngle",
        "EndAngle", "Closed", "TextString", "InsertionPoint", "Height", "Rotation",
        "Area", "Length",
    ):
        try:
            payload[name] = _json_value(getattr(entity, name))
        except Exception:
            continue
    try:
        minimum, maximum = entity.GetBoundingBox()
        payload["BoundingBox"] = [_json_value(minimum), _json_value(maximum)]
    except Exception:
        pass
    return _fingerprint(payload)


def _entity(doc: Any, handle: str) -> tuple[LiveEntityEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"Batch 25 entity does not exist: {handle}")
    layer = str(entity.Layer)
    locked = bool(doc.Layers.Item(layer).Lock)
    is_xref = "|" in layer
    if locked or is_xref:
        raise ValueError(f"Batch 25 entity is locked or xref-dependent: {handle}")
    return LiveEntityEvidence(
        handle=str(entity.Handle), object_name=str(entity.ObjectName), layer=layer,
        geometry_fingerprint=_geometry_fingerprint(entity), locked_layer=locked, is_xref=is_xref,
    ), entity


def _layer(doc: Any, name: str) -> LiveLayerEvidence:
    try:
        layer = doc.Layers.Item(name)
    except Exception as exc:
        raise ValueError(f"Batch 25 target layer does not exist: {name}") from exc
    actual = str(layer.Name)
    state = LiveLayerEvidence(name=actual, locked=bool(layer.Lock), is_xref="|" in actual)
    if state.locked or state.is_xref:
        raise ValueError(f"Batch 25 target layer is locked or xref-dependent: {name}")
    return state


def _point(value: Any) -> Point3D:
    values = tuple(float(item) for item in value)
    return Point3D(x=values[0], y=values[1], z=values[2])


def _variant(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])


def _coordinates(points: tuple[Point3D, ...]) -> Any:
    import pythoncom
    import win32com.client

    values = [coordinate for point in points for coordinate in (point.x, point.y)]
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)


def _plan(request: Any) -> Any:
    planners = {
        SlopeRequest: plan_slope, EnergyAreaTableRequest: plan_energy_area_table,
        CommonTextRequest: plan_common_text, SpecialCharacterRequest: plan_special_character,
        TextPointIncrementRequest: plan_text_point_increment, TextOnObjectRequest: plan_text_on_object,
        TextsToTableRequest: plan_texts_to_table, TextBoxRequest: plan_text_box,
        MakeTextLinetypeRequest: plan_make_text_linetype, BoundingBoxRequest: plan_bounding_box,
        PolylineCloseRequest: plan_polyline_close, PerpendicularCurveRequest: plan_perpendicular_curve,
    }
    for request_type, planner in planners.items():
        if isinstance(request, request_type):
            return planner(request)
    raise TypeError(f"unsupported Batch 25 request: {type(request).__name__}")


def _source_handles(request: ExecutableRequest) -> tuple[str, ...]:
    if isinstance(request, TextPointIncrementRequest):
        return (request.source.source_handle,)
    if isinstance(request, TextOnObjectRequest):
        return tuple(item.object_handle for item in request.targets)
    if isinstance(request, BoundingBoxRequest):
        return tuple(item.handle for item in request.entities)
    if isinstance(request, PolylineCloseRequest):
        return tuple(item.handle for item in request.polylines)
    if isinstance(request, PerpendicularCurveRequest):
        return tuple(item.handle for item in request.curves)
    return ()


def _target_layer_names(request: ExecutableRequest) -> tuple[str, ...]:
    if isinstance(request, SlopeRequest):
        return (request.layer,)
    if isinstance(request, (CommonTextRequest, SpecialCharacterRequest, TextOnObjectRequest)):
        return (request.layer,)
    if isinstance(request, TextPointIncrementRequest):
        return tuple(dict.fromkeys(item.layer for item in request.placements))
    if isinstance(request, BoundingBoxRequest):
        return (request.output_layer,)
    if isinstance(request, PerpendicularCurveRequest):
        return (request.output_layer,)
    return ()


def _validate_request_sources(request: ExecutableRequest, objects: tuple[Any, ...]) -> None:
    if isinstance(request, TextPointIncrementRequest):
        expected = request.source.prefix + ("-" if request.source.value < 0 else "") + str(abs(request.source.value)).zfill(request.source.minimum_digits) + request.source.suffix
        if str(objects[0].TextString) != expected:
            raise ValueError("TIP source text does not match its explicit numeric snapshot")
    elif isinstance(request, PolylineCloseRequest):
        for snapshot, entity in zip(request.polylines, objects, strict=True):
            if str(entity.ObjectName).casefold() not in {"acdbpolyline", "acdblwpolyline"} or bool(entity.Closed):
                raise ValueError(f"PC requires an open polyline: {snapshot.handle}")
            coordinates = tuple(float(value) for value in entity.Coordinates)
            expected = tuple(coordinate for point in snapshot.vertices for coordinate in (point.x, point.y))
            if len(coordinates) != len(expected) or any(abs(a - b) > 1e-9 for a, b in zip(coordinates, expected, strict=True)):
                raise ValueError(f"PC vertices do not match the live polyline: {snapshot.handle}")
    elif isinstance(request, BoundingBoxRequest):
        for snapshot, entity in zip(request.entities, objects, strict=True):
            try:
                minimum, maximum = entity.GetBoundingBox()
            except Exception as exc:
                raise ValueError(f"PBB cannot read live extents: {snapshot.handle}") from exc
            if _point(minimum) != snapshot.minimum or _point(maximum) != snapshot.maximum:
                raise ValueError(f"PBB extents do not match the live entity: {snapshot.handle}")


def _payload(request: ExecutableRequest, plan: Any, sources: tuple[LiveEntityEvidence, ...], layers: tuple[LiveLayerEvidence, ...]) -> dict[str, Any]:
    return {
        "command_alias": plan.command_alias, "document_name": request.document_id,
        "request": request.model_dump(mode="json"), "plan": plan.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
        "expected_target_layers": [item.model_dump(mode="json") for item in layers],
    }


def _preview_executable(request: ExecutableRequest, expected_alias: str) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _plan(request)
    if plan.command_alias != expected_alias:
        raise ValueError(f"{expected_alias} preview received a different request type")
    doc = _drawing(request.document_id)
    pairs = tuple(_entity(doc, handle) for handle in _source_handles(request))
    _validate_request_sources(request, tuple(pair[1] for pair in pairs))
    sources = tuple(pair[0] for pair in pairs)
    layers = tuple(_layer(doc, name) for name in _target_layer_names(request))
    payload = _payload(request, plan, sources, layers)
    return {
        **payload, "approval_fingerprint": _fingerprint(payload), "mutation": True,
        "live_executable": True,
        "scope_note": "exact handles/layers and caller-approved primitive results are stale-checked around one Undo group; legacy equivalence is not claimed",
    }


def _preview_blocked(request: Any) -> dict[str, Any]:
    plan = _plan(request)
    payload = {"command_alias": plan.command_alias, "document_name": request.document_id, "request": request.model_dump(mode="json"), "plan": plan.model_dump(mode="json")}
    return {**payload, "approval_fingerprint": _fingerprint(payload), "mutation": False, "live_executable": False, "blocked_reason": BLOCKED[plan.command_alias]}


def preview_live_sl(request: SlopeRequest) -> dict[str, Any]: return _preview_executable(request, "SL")
def preview_live_zae(request: EnergyAreaTableRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_qt(request: CommonTextRequest) -> dict[str, Any]: return _preview_executable(request, "QT")
def preview_live_qw(request: SpecialCharacterRequest) -> dict[str, Any]: return _preview_executable(request, "QW")
def preview_live_tip(request: TextPointIncrementRequest) -> dict[str, Any]: return _preview_executable(request, "TIP")
def preview_live_too(request: TextOnObjectRequest) -> dict[str, Any]: return _preview_executable(request, "TOO")
def preview_live_ttt(request: TextsToTableRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_tx(request: TextBoxRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_mtlt(request: MakeTextLinetypeRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_pbb(request: BoundingBoxRequest) -> dict[str, Any]: return _preview_executable(request, "PBB")
def preview_live_pc(request: PolylineCloseRequest) -> dict[str, Any]: return _preview_executable(request, "PC")
def preview_live_pec(request: PerpendicularCurveRequest) -> dict[str, Any]: return _preview_executable(request, "PEC")


def _add_text(doc: Any, spec: Any) -> Any:
    entity = doc.ModelSpace.AddText(spec.text, _variant(spec.insertion_point), spec.text_height)
    entity.Layer = spec.layer
    entity.Rotation = math.radians(spec.rotation_degrees)
    return entity


def _add_polyline(doc: Any, points: tuple[Point3D, ...], layer: str, closed: bool) -> Any:
    entity = doc.ModelSpace.AddLightWeightPolyline(_coordinates(points))
    entity.Layer = layer
    entity.Closed = closed
    return entity


def execute_live_batch25(request: LiveBatch25ExecuteRequest) -> LiveBatch25Result:
    plan = _plan(request.request)
    payload = _payload(request.request, plan, request.expected_sources, request.expected_target_layers)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 25 preview")
    doc = _drawing(request.request.document_id)
    current_pairs = tuple(_entity(doc, item.handle) for item in request.expected_sources)
    if tuple(pair[0] for pair in current_pairs) != request.expected_sources:
        raise ValueError("Batch 25 source state no longer matches the approved preview")
    _validate_request_sources(request.request, tuple(pair[1] for pair in current_pairs))
    if tuple(_layer(doc, item.name) for item in request.expected_target_layers) != request.expected_target_layers:
        raise ValueError("Batch 25 target-layer state no longer matches the approved preview")
    created: list[Any] = []
    changed: list[Any] = []
    expected_texts: list[tuple[Any, Any]] = []
    expected_polylines: list[tuple[Any, tuple[Point3D, ...], str, bool]] = []
    expected_lines: list[tuple[Any, Point3D, Point3D, str]] = []
    doc.StartUndoMark()
    try:
        if plan.command_alias == "SL":
            text = _add_text(doc, plan.text)
            created.append(text)
            expected_texts.append((text, plan.text))
            if plan.triangle_vertices:
                polyline = _add_polyline(doc, plan.triangle_vertices, plan.text.layer, True)
                created.append(polyline)
                expected_polylines.append((polyline, plan.triangle_vertices, plan.text.layer, True))
        elif plan.command_alias in {"QT", "QW"}:
            text = _add_text(doc, plan.create)
            created.append(text)
            expected_texts.append((text, plan.create))
        elif plan.command_alias in {"TIP", "TOO"}:
            for spec in plan.creates:
                text = _add_text(doc, spec)
                created.append(text)
                expected_texts.append((text, spec))
        elif plan.command_alias == "PBB":
            polyline = _add_polyline(doc, plan.vertices, plan.output_layer, plan.close_polyline)
            created.append(polyline)
            expected_polylines.append((polyline, plan.vertices, plan.output_layer, plan.close_polyline))
        elif plan.command_alias == "PC":
            by_handle = {state.handle.casefold(): entity for state, entity in current_pairs}
            for update in plan.updates:
                entity = by_handle[update.handle.casefold()]
                entity.Closed = True
                changed.append(entity)
        elif plan.command_alias == "PEC":
            for spec in plan.lines:
                entity = doc.ModelSpace.AddLine(_variant(spec.start_point), _variant(spec.end_point))
                entity.Layer = spec.output_layer
                created.append(entity)
                expected_lines.append((entity, spec.start_point, spec.end_point, spec.output_layer))
        else:
            raise ValueError(f"Batch 25 live execution is not exposed for {plan.command_alias}")
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    if any(str(item.Handle).casefold() not in available for item in created + changed):
        raise RuntimeError(f"{plan.command_alias} postcondition failed: output entity is missing")
    for entity, spec in expected_texts:
        if str(entity.TextString) != spec.text or _point(entity.InsertionPoint) != spec.insertion_point or abs(float(entity.Height) - spec.text_height) > 1e-9 or abs(float(entity.Rotation) - math.radians(spec.rotation_degrees)) > 1e-9 or str(entity.Layer).casefold() != spec.layer.casefold():
            raise RuntimeError(f"{plan.command_alias} postcondition failed: text properties differ")
    for entity, points, layer, closed in expected_polylines:
        coordinates = tuple(float(value) for value in entity.Coordinates)
        expected = tuple(value for point in points for value in (point.x, point.y))
        if coordinates != expected or bool(entity.Closed) is not closed or str(entity.Layer).casefold() != layer.casefold():
            raise RuntimeError(f"{plan.command_alias} postcondition failed: polyline properties differ")
    for entity, start, end, layer in expected_lines:
        if _point(entity.StartPoint) != start or _point(entity.EndPoint) != end or str(entity.Layer).casefold() != layer.casefold():
            raise RuntimeError("PEC postcondition failed: line properties differ")
    if plan.command_alias == "PC" and any(not bool(item.Closed) for item in changed):
        raise RuntimeError("PC postcondition failed: polyline remains open")
    return LiveBatch25Result(
        document_name=str(doc.Name), command_alias=plan.command_alias,
        created_handles=tuple(str(item.Handle) for item in created), changed_handles=tuple(str(item.Handle) for item in changed),
        undo_mark_opened=True, undo_mark_closed=True, postcondition_verified=True,
    )


def register_live_batch25_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(title="Preview live xiCAD Batch 25 operation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    execute = ToolAnnotations(title="Execute live xiCAD Batch 25 operation", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
    functions = {
        "sl": preview_live_sl, "zae": preview_live_zae, "qt": preview_live_qt, "qw": preview_live_qw,
        "tip": preview_live_tip, "too": preview_live_too, "ttt": preview_live_ttt, "tx": preview_live_tx,
        "mtlt": preview_live_mtlt, "pbb": preview_live_pbb, "pc": preview_live_pc, "pec": preview_live_pec,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
        if alias.upper() not in BLOCKED:
            mcp.tool(name=f"xicad_execute_live_{alias}", annotations=execute)(execute_live_batch25)
