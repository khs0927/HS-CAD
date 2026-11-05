from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch13 import (
    BreakSymbolRequest,
    CloudWidthRequest,
    ContourJoinRequest,
    DirectionLineRequest,
    DirectionOperation,
    JumpLineRequest,
    PolylineSnapshot,
    RevisionCloudRequest,
    plan_contour_join,
    plan_direction_line,
)


class LivePolylineEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    snapshot: PolylineSnapshot
    bulges: tuple[float, ...]
    constant_width: float


class LiveCbjExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ContourJoinRequest
    expected_polylines: tuple[LivePolylineEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveDrlExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: DirectionLineRequest
    expected_polylines: tuple[LivePolylineEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveGeometryBatch13bResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...] = ()
    created_handles: tuple[str, ...] = ()
    erased_handles: tuple[str, ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _drawing(document_name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == document_name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {document_name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _entities(doc: Any) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for block in doc.Blocks:
        if bool(block.IsLayout):
            for entity in block:
                found[str(entity.Handle).casefold()] = entity
    return found


def _polyline_evidence(doc: Any, handle: str) -> tuple[LivePolylineEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"polyline not found: {handle}")
    if str(entity.ObjectName).casefold() != "acdbpolyline":
        raise ValueError("live Batch 13B supports AcDbPolyline (LWPolyline) only")
    coordinates = tuple(float(value) for value in entity.Coordinates)
    if len(coordinates) < 4 or len(coordinates) % 2:
        raise ValueError("polyline has invalid ActiveX coordinates")
    elevation = float(entity.Elevation)
    vertices = tuple(
        Point3D(x=coordinates[index], y=coordinates[index + 1], z=elevation)
        for index in range(0, len(coordinates), 2)
    )
    layer = str(entity.Layer)
    snapshot = PolylineSnapshot(
        handle=str(entity.Handle),
        vertices=vertices,
        closed=bool(entity.Closed),
        layer=layer,
        locked_layer=bool(doc.Layers.Item(layer).Lock),
        is_xref="|" in layer,
    )
    bulges = tuple(float(entity.GetBulge(index)) for index in range(len(vertices)))
    return LivePolylineEvidence(
        snapshot=snapshot,
        bulges=bulges,
        constant_width=float(entity.ConstantWidth),
    ), entity


def _evidence(doc: Any, handles: tuple[str, ...]) -> tuple[tuple[LivePolylineEvidence, ...], dict[str, Any]]:
    states: list[LivePolylineEvidence] = []
    objects: dict[str, Any] = {}
    for handle in handles:
        state, entity = _polyline_evidence(doc, handle)
        states.append(state)
        objects[state.snapshot.handle.casefold()] = entity
    return tuple(states), objects


def _payload(alias: str, request: Any, states: tuple[LivePolylineEvidence, ...]) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "request": request.model_dump(mode="json"),
        "expected_polylines": [state.model_dump(mode="json") for state in states],
    }


def _require_straight_zero_width(states: tuple[LivePolylineEvidence, ...], alias: str) -> None:
    if any(any(abs(bulge) > 1e-12 for bulge in state.bulges) for state in states):
        raise ValueError(f"live {alias} blocks curved polyline segments because the planner has no bulge contract")
    if any(abs(state.constant_width) > 1e-12 for state in states):
        raise ValueError(f"live {alias} blocks nonzero polyline width because the planner has no width contract")


def preview_live_cbj(request: ContourJoinRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    if request.contour_handle.casefold() == request.boundary_handle.casefold():
        raise ValueError("CBJ contour and boundary must be distinct")
    doc = _drawing(request.document_id)
    states, _objects = _evidence(doc, (request.contour_handle, request.boundary_handle))
    _require_straight_zero_width(states, "CBJ")
    if states[0].snapshot.closed:
        raise ValueError("live CBJ requires an open contour")
    plan = plan_contour_join(request, tuple(state.snapshot for state in states))
    elevations = {point.z for point in plan.create.vertices}
    if len(elevations) != 1:
        raise ValueError("live CBJ requires coplanar vertices at one elevation")
    payload = _payload("CBJ", request, states)
    return {
        **payload,
        "create_count": 1,
        "erase_count": int(plan.erase_source),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
    }


def preview_live_drl(request: DirectionLineRequest) -> dict[str, Any]:
    if request.operation is not DirectionOperation.REVERSE:
        raise ValueError("live DRL annotate is blocked: the planner does not specify arrow vertices or block geometry")
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    states, _objects = _evidence(doc, request.target_handles)
    _require_straight_zero_width(states, "DRL")
    plan = plan_direction_line(request, tuple(state.snapshot for state in states))
    payload = _payload("DRL", request, states)
    return {
        **payload,
        "change_count": len(plan.reversed_vertices),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(plan.reversed_vertices),
    }


def _validate(alias: str, request: Any, expected: tuple[LivePolylineEvidence, ...], fingerprint: str) -> tuple[Any, dict[str, Any]]:
    if fingerprint != _fingerprint(_payload(alias, request, expected)):
        raise ValueError("approval fingerprint does not match the exact polyline request")
    doc = _drawing(request.document_id)
    current, objects = _evidence(doc, tuple(state.snapshot.handle for state in expected))
    if current != expected:
        raise ValueError("polyline state no longer matches the approved plan")
    _require_straight_zero_width(current, alias)
    return doc, objects


def _variant_coordinates(points: tuple[Point3D, ...]) -> Any:
    import pythoncom
    import win32com.client

    values = [coordinate for point in points for coordinate in (point.x, point.y)]
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)


def execute_live_cbj(request: LiveCbjExecuteRequest) -> LiveGeometryBatch13bResult:
    doc, objects = _validate("CBJ", request.request, request.expected_polylines, request.approval_fingerprint)
    states = tuple(item.snapshot for item in request.expected_polylines)
    plan = plan_contour_join(request.request, states)
    created = None
    contour = objects[request.request.contour_handle.casefold()]
    doc.StartUndoMark()
    try:
        created = doc.ModelSpace.AddLightWeightPolyline(_variant_coordinates(plan.create.vertices))
        created.Elevation = plan.create.vertices[0].z
        created.Layer = plan.create.layer
        created.Closed = plan.create.closed
        if plan.erase_source:
            contour.Delete()
    finally:
        doc.EndUndoMark()
    after = _entities(doc)
    created_state, _created_object = _polyline_evidence(doc, str(created.Handle))
    if created_state.snapshot.vertices != plan.create.vertices or created_state.snapshot.layer != plan.create.layer:
        raise RuntimeError("CBJ postcondition failed: created contour differs from approved geometry")
    erased = (states[0].handle,) if plan.erase_source else ()
    if erased and states[0].handle.casefold() in after:
        raise RuntimeError("CBJ postcondition failed: source contour still exists")
    return _result(doc, "CBJ", created=(str(created.Handle),), erased=erased)


def execute_live_drl(request: LiveDrlExecuteRequest) -> LiveGeometryBatch13bResult:
    if request.request.operation is not DirectionOperation.REVERSE:
        raise ValueError("live DRL executor supports reverse only")
    doc, objects = _validate("DRL", request.request, request.expected_polylines, request.approval_fingerprint)
    plan = plan_direction_line(request.request, tuple(item.snapshot for item in request.expected_polylines))
    doc.StartUndoMark()
    try:
        for handle, vertices in plan.reversed_vertices.items():
            objects[handle.casefold()].Coordinates = _variant_coordinates(vertices)
    finally:
        doc.EndUndoMark()
    for handle, vertices in plan.reversed_vertices.items():
        current, _entity = _polyline_evidence(doc, handle)
        if current.snapshot.vertices != vertices:
            raise RuntimeError(f"DRL postcondition failed: {handle}")
    return _result(doc, "DRL", changed=tuple(plan.reversed_vertices))


def preview_live_bs(request: BreakSymbolRequest) -> dict[str, Any]:
    del request
    raise ValueError("live BS is blocked: the headless plan does not define the break-symbol output vertices")


def preview_live_cm(request: RevisionCloudRequest) -> dict[str, Any]:
    del request
    raise ValueError("live CM is blocked: the headless plan does not define revision-cloud arc segmentation and bulges")


def preview_live_cmw(request: CloudWidthRequest) -> dict[str, Any]:
    del request
    raise ValueError("live CMW is blocked: ActiveX ConstantWidth is not equivalent to the planned sided cloud outline")


def preview_live_jul(request: JumpLineRequest) -> dict[str, Any]:
    del request
    raise ValueError("live JUL is blocked: the headless plan does not define base-line splits and tangent arc geometry")


def _result(
    doc: Any,
    alias: str,
    *,
    changed: tuple[str, ...] = (),
    created: tuple[str, ...] = (),
    erased: tuple[str, ...] = (),
) -> LiveGeometryBatch13bResult:
    return LiveGeometryBatch13bResult(
        document_name=str(doc.Name),
        command_alias=alias,
        changed_handles=changed,
        created_handles=created,
        erased_handles=erased,
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_geometry_batch13b_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 13B geometry operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 13B geometry operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_bs", preview_live_bs, preview),
        ("xicad_preview_live_cbj", preview_live_cbj, preview),
        ("xicad_execute_live_cbj", execute_live_cbj, execute),
        ("xicad_preview_live_cm", preview_live_cm, preview),
        ("xicad_preview_live_cmw", preview_live_cmw, preview),
        ("xicad_preview_live_drl", preview_live_drl, preview),
        ("xicad_execute_live_drl", execute_live_drl, execute),
        ("xicad_preview_live_jul", preview_live_jul, preview),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
