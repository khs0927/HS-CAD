from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch17 import HatchSnapshot
from .headless_core_batch18 import (
    CadTableSnapshot,
    CadToExcelRequest,
    ExcelToCadRequest,
    HatchCloneRequest,
    HatchExportRequest,
    StairPlanRequest,
    TableWidthRequest,
    TrussRequest,
    WallOpeningRequest,
    WindowRequest,
    ZigZagRequest,
    plan_cad_to_excel,
    plan_excel_to_cad,
    plan_hatch_clone,
    plan_hatch_export,
    plan_stair_plan,
    plan_table_width,
    plan_truss,
    plan_wall_opening,
    plan_window,
    plan_zigzag,
)


class LiveLayerEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    color: int
    linetype: str
    locked: bool
    is_xref: bool


class LiveTrussExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: TrussRequest
    expected_chord_layer: LiveLayerEvidence
    expected_web_layer: LiveLayerEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveZigZagExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ZigZagRequest
    expected_layer: LiveLayerEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch18Result(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


BLOCKED = {
    "STP": "tread lines omit turning flights, landings, handrails, arrows, cut lines, anti-slip, text, and numbering",
    "TAJ": "ZWCAD Table cell/column ActiveX snapshot and setter semantics are not proven in the target drawing",
    "W1": "opening line/division fractions omit frame, glazing, wall-gap, elevation, and grouping geometry",
    "W2": "opening line/division fractions omit sliding leaves, frame, glazing, elevation, and grouping geometry",
    "W3": "catalog xiWin3 and planner xiWin2/W3 evidence disagree, and full window geometry is absent",
    "WO": "opening line omits wall cleanup, offsets, internal/external projections, and elevation geometry",
    "C2E": "external Excel automation is outside CAD Undo; planner data remains CAD-free",
    "E2C": "external Excel provenance and complete CAD table style/merge semantics are not defined",
    "HC": "hatch snapshot omits pattern, angle, scale, color and target boundary ownership semantics",
    "HEX": "file write is explicitly blocked; planner definition data remains CAD-free",
}


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _drawing(name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _layer(doc: Any, name: str) -> LiveLayerEvidence:
    try:
        layer = doc.Layers.Item(name)
    except Exception as exc:
        raise ValueError(f"output layer is unavailable: {name}") from exc
    actual = str(layer.Name)
    state = LiveLayerEvidence(
        name=actual,
        color=int(layer.Color),
        linetype=str(layer.Linetype),
        locked=bool(layer.Lock),
        is_xref="|" in actual,
    )
    if state.locked or state.is_xref:
        raise ValueError(f"output layer is locked or xref-dependent: {name}")
    return state


def _entities(doc: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for block in doc.Blocks:
        if bool(block.IsLayout):
            for entity in block:
                result[str(entity.Handle).casefold()] = entity
    return result


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


def _payload(alias: str, request: Any, **evidence: Any) -> dict[str, Any]:
    return {"command_alias": alias, "request": request.model_dump(mode="json"), **evidence}


def preview_live_truss(request: TrussRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    plan = plan_truss(request)
    chord, web = _layer(doc, plan.chord_layer), _layer(doc, plan.web_layer)
    payload = _payload(
        "TRUSS",
        request,
        expected_chord_layer=chord.model_dump(mode="json"),
        expected_web_layer=web.model_dump(mode="json"),
    )
    return {
        **payload,
        "plan": plan.model_dump(mode="json"),
        "create_count": 2 + len(plan.webs),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
    }


def preview_live_zigzag(request: ZigZagRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    plan = plan_zigzag(request)
    if len({point.z for point in plan.vertices}) != 1:
        raise ValueError("live ZIGZAG requires one elevation for AcDbPolyline output")
    doc = _drawing(request.document_id)
    layer = _layer(doc, plan.layer)
    payload = _payload("ZIGZAG", request, expected_layer=layer.model_dump(mode="json"))
    return {
        **payload,
        "plan": plan.model_dump(mode="json"),
        "create_count": 1,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
    }


def execute_live_truss(request: LiveTrussExecuteRequest) -> LiveBatch18Result:
    payload = _payload(
        "TRUSS",
        request.request,
        expected_chord_layer=request.expected_chord_layer.model_dump(mode="json"),
        expected_web_layer=request.expected_web_layer.model_dump(mode="json"),
    )
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact TRUSS request")
    doc = _drawing(request.request.document_id)
    if _layer(doc, request.expected_chord_layer.name) != request.expected_chord_layer or _layer(
        doc, request.expected_web_layer.name
    ) != request.expected_web_layer:
        raise ValueError("TRUSS layer state no longer matches the approved plan")
    plan = plan_truss(request.request)
    specs = ((plan.lower_chord, plan.chord_layer), (plan.upper_chord, plan.chord_layer), *(
        (line, plan.web_layer) for line in plan.webs
    ))
    created: list[tuple[Any, tuple[Point3D, Point3D], str]] = []
    doc.StartUndoMark()
    try:
        for (start, end), layer in specs:
            entity = doc.ModelSpace.AddLine(_variant(start), _variant(end))
            entity.Layer = layer
            created.append((entity, (start, end), layer))
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    for entity, (start, end), layer in created:
        if (
            str(entity.Handle).casefold() not in available
            or _point(entity.StartPoint) != start
            or _point(entity.EndPoint) != end
            or str(entity.Layer).casefold() != layer.casefold()
        ):
            raise RuntimeError("TRUSS postcondition failed")
    return _result(doc, "TRUSS", tuple(str(item[0].Handle) for item in created))


def execute_live_zigzag(request: LiveZigZagExecuteRequest) -> LiveBatch18Result:
    payload = _payload(
        "ZIGZAG", request.request, expected_layer=request.expected_layer.model_dump(mode="json")
    )
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact ZIGZAG request")
    doc = _drawing(request.request.document_id)
    if _layer(doc, request.expected_layer.name) != request.expected_layer:
        raise ValueError("ZIGZAG layer state no longer matches the approved plan")
    plan = plan_zigzag(request.request)
    doc.StartUndoMark()
    try:
        entity = doc.ModelSpace.AddLightWeightPolyline(_coordinates(plan.vertices))
        entity.Elevation = plan.vertices[0].z
        entity.Layer = plan.layer
        entity.Closed = False
    finally:
        doc.EndUndoMark()
    expected = tuple(value for point in plan.vertices for value in (point.x, point.y))
    if (
        str(entity.Handle).casefold() not in _entities(doc)
        or tuple(float(value) for value in entity.Coordinates) != expected
        or bool(entity.Closed)
        or str(entity.Layer).casefold() != plan.layer.casefold()
    ):
        raise RuntimeError("ZIGZAG postcondition failed")
    return _result(doc, "ZIGZAG", (str(entity.Handle),))


def _result(doc: Any, alias: str, handles: tuple[str, ...]) -> LiveBatch18Result:
    return LiveBatch18Result(
        document_name=str(doc.Name),
        command_alias=alias,
        created_handles=handles,
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def _blocked(alias: str, request: Any, plan: Any, **evidence: Any) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    payload = _payload(alias, request, plan=plan.model_dump(mode="json"), **evidence)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "live_executable": False,
        "blocked_reason": BLOCKED[alias],
    }


def preview_live_stp(request: StairPlanRequest) -> dict[str, Any]:
    return _blocked("STP", request, plan_stair_plan(request))


def preview_live_taj(request: TableWidthRequest, snapshots: tuple[CadTableSnapshot, ...]) -> dict[str, Any]:
    return _blocked("TAJ", request, plan_table_width(request, snapshots), expected_tables=[s.model_dump(mode="json") for s in snapshots])


def preview_live_window(request: WindowRequest) -> dict[str, Any]:
    alias = request.variant.value.upper()
    return _blocked(alias, request, plan_window(request))


def preview_live_wo(request: WallOpeningRequest) -> dict[str, Any]:
    return _blocked("WO", request, plan_wall_opening(request))


def preview_live_c2e(request: CadToExcelRequest, snapshots: tuple[CadTableSnapshot, ...]) -> dict[str, Any]:
    return _blocked("C2E", request, plan_cad_to_excel(request, snapshots), expected_tables=[s.model_dump(mode="json") for s in snapshots])


def preview_live_e2c(request: ExcelToCadRequest) -> dict[str, Any]:
    return _blocked("E2C", request, plan_excel_to_cad(request))


def preview_live_hc(request: HatchCloneRequest, snapshots: tuple[HatchSnapshot, ...]) -> dict[str, Any]:
    return _blocked("HC", request, plan_hatch_clone(request, snapshots), expected_hatches=[s.model_dump(mode="json") for s in snapshots])


def preview_live_hex(request: HatchExportRequest, snapshots: tuple[HatchSnapshot, ...]) -> dict[str, Any]:
    return _blocked("HEX", request, plan_hatch_export(request, snapshots), expected_hatches=[s.model_dump(mode="json") for s in snapshots])


def register_live_batch18_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(title="Preview live xiCAD Batch 18 operation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    execute = ToolAnnotations(title="Execute live xiCAD Batch 18 operation", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
    registrations = (
        ("xicad_preview_live_stp", preview_live_stp, preview),
        ("xicad_preview_live_truss", preview_live_truss, preview),
        ("xicad_execute_live_truss", execute_live_truss, execute),
        ("xicad_preview_live_w1", preview_live_window, preview),
        ("xicad_preview_live_w2", preview_live_window, preview),
        ("xicad_preview_live_w3", preview_live_window, preview),
        ("xicad_preview_live_wo", preview_live_wo, preview),
        ("xicad_preview_live_zigzag", preview_live_zigzag, preview),
        ("xicad_execute_live_zigzag", execute_live_zigzag, execute),
        ("xicad_preview_live_c2e", preview_live_c2e, preview),
        ("xicad_preview_live_e2c", preview_live_e2c, preview),
        ("xicad_preview_live_hc", preview_live_hc, preview),
        ("xicad_preview_live_hex", preview_live_hex, preview),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
