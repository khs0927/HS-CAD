from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch20a import CurveSnapshot, CutRequest, plan_cut
from .headless_core_batch20b import (
    CopyPlan,
    CopyRotateRequest,
    CopyToCurrentLayerRequest,
    CopyToNewLayerRequest,
    DynamicArrayRequest,
    LinearArrayRequest,
    Matrix4,
    PolarArrayRequest,
    plan_copy_rotate,
    plan_copy_to_current_layer,
    plan_copy_to_new_layer,
    plan_dynamic_array,
    plan_linear_array,
    plan_polar_array,
)

CopyRequest = (
    DynamicArrayRequest
    | PolarArrayRequest
    | LinearArrayRequest
    | CopyToNewLayerRequest
    | CopyRotateRequest
    | CopyToCurrentLayerRequest
)


class LiveLineEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    handle: str
    start: Point3D
    end: Point3D
    layer: str
    color: int
    linetype: str
    lineweight: int
    thickness: float
    locked_layer: bool
    is_xref: bool


class LiveLayerEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    exists: bool
    color: int | None = None
    linetype: str | None = None
    lineweight: int | None = None
    locked: bool = False
    is_xref: bool = False


class LiveCopyExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: CopyRequest
    expected_sources: tuple[LiveLineEvidence, ...]
    expected_target_layers: tuple[LiveLayerEvidence, ...] = ()
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch20Result(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    created_layers: tuple[str, ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


CUT_BLOCKED = (
    "ProposedCurveEdit omits output layer and entity-property policy; automatic trim/fillet legacy side selection "
    "is unrecovered"
)


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


def _line(doc: Any, handle: str) -> tuple[LiveLineEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"copy source not found: {handle}")
    if str(entity.ObjectName).casefold() != "acdbline":
        raise ValueError("live Batch 20 copy supports AcDbLine sources only")
    layer = str(entity.Layer)
    state = LiveLineEvidence(
        handle=str(entity.Handle),
        start=_point(entity.StartPoint),
        end=_point(entity.EndPoint),
        layer=layer,
        color=int(entity.Color),
        linetype=str(entity.Linetype),
        lineweight=int(entity.Lineweight),
        thickness=float(entity.Thickness),
        locked_layer=bool(doc.Layers.Item(layer).Lock),
        is_xref="|" in layer,
    )
    if state.locked_layer or state.is_xref:
        raise ValueError(f"copy source is locked or xref-dependent: {handle}")
    return state, entity


def _layers(doc: Any) -> dict[str, Any]:
    return {str(layer.Name).casefold(): layer for layer in doc.Layers}


def _layer(doc: Any, name: str) -> LiveLayerEvidence:
    layer = _layers(doc).get(name.casefold())
    if layer is None:
        return LiveLayerEvidence(name=name, exists=False)
    actual = str(layer.Name)
    return LiveLayerEvidence(
        name=actual,
        exists=True,
        color=int(layer.Color),
        linetype=str(layer.Linetype),
        lineweight=int(layer.Lineweight),
        locked=bool(layer.Lock),
        is_xref="|" in actual,
    )


def _plan(request: CopyRequest) -> CopyPlan:
    if isinstance(request, DynamicArrayRequest):
        return plan_dynamic_array(request)
    if isinstance(request, PolarArrayRequest):
        return plan_polar_array(request)
    if isinstance(request, LinearArrayRequest):
        return plan_linear_array(request)
    if isinstance(request, CopyToNewLayerRequest):
        return plan_copy_to_new_layer(request)
    if isinstance(request, CopyRotateRequest):
        return plan_copy_rotate(request)
    return plan_copy_to_current_layer(request)


def _target_layers(doc: Any, request: CopyRequest, plan: CopyPlan) -> tuple[LiveLayerEvidence, ...]:
    names = tuple(dict.fromkeys(spec.target_layer for spec in plan.copies if spec.target_layer is not None))
    states = tuple(_layer(doc, name) for name in names)
    if isinstance(request, CopyToNewLayerRequest):
        if any(state.exists for state in states):
            raise ValueError("CNL target layer already exists; new-layer semantics require absence")
        try:
            doc.Linetypes.Item(request.new_layer.linetype)
        except Exception as exc:
            raise ValueError(f"CNL linetype is unavailable: {request.new_layer.linetype}") from exc
    elif any(not state.exists or state.locked or state.is_xref for state in states):
        raise ValueError("copy target layer is unavailable, locked, or xref-dependent")
    return states


def _copy_payload(
    alias: str,
    request: CopyRequest,
    sources: tuple[LiveLineEvidence, ...],
    layers: tuple[LiveLayerEvidence, ...],
) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "request": request.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
        "expected_target_layers": [item.model_dump(mode="json") for item in layers],
    }


def _preview_copy(request: CopyRequest, expected_alias: str) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    plan = _plan(request)
    if plan.command_alias != expected_alias:
        raise ValueError(f"{expected_alias} preview received a different request type")
    doc = _drawing(request.document_id)
    handles = tuple(dict.fromkeys(spec.source_handle for spec in plan.copies))
    sources = tuple(_line(doc, handle)[0] for handle in handles)
    layers = _target_layers(doc, request, plan)
    payload = _copy_payload(expected_alias, request, sources, layers)
    return {
        **payload,
        "plan": plan.model_dump(mode="json"),
        "create_count": len(plan.copies),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(plan.copies),
        "live_executable": True,
        "scope_note": "AcDbLine-only copies; source entity properties are preserved by COM Copy",
    }


def preview_live_ard(request: DynamicArrayRequest) -> dict[str, Any]:
    return _preview_copy(request, "ARD")


def preview_live_arp(request: PolarArrayRequest) -> dict[str, Any]:
    return _preview_copy(request, "ARP")


def preview_live_arv(request: LinearArrayRequest) -> dict[str, Any]:
    return _preview_copy(request, "ARV")


def preview_live_cnl(request: CopyToNewLayerRequest) -> dict[str, Any]:
    return _preview_copy(request, "CNL")


def preview_live_cr(request: CopyRotateRequest) -> dict[str, Any]:
    return _preview_copy(request, "CR")


def preview_live_ctl(request: CopyToCurrentLayerRequest) -> dict[str, Any]:
    return _preview_copy(request, "CTL")


def _transform(point: Point3D, matrix: Matrix4) -> Point3D:
    values = (point.x, point.y, point.z, 1.0)
    return Point3D(
        x=sum(matrix[0][index] * values[index] for index in range(4)),
        y=sum(matrix[1][index] * values[index] for index in range(4)),
        z=sum(matrix[2][index] * values[index] for index in range(4)),
    )


def execute_live_copy(request: LiveCopyExecuteRequest) -> LiveBatch20Result:
    plan = _plan(request.request)
    payload = _copy_payload(plan.command_alias, request.request, request.expected_sources, request.expected_target_layers)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact copy request")
    doc = _drawing(request.request.document_id)
    current_pairs = tuple(_line(doc, item.handle) for item in request.expected_sources)
    if tuple(item[0] for item in current_pairs) != request.expected_sources:
        raise ValueError("copy source state no longer matches the approved plan")
    if tuple(_layer(doc, item.name) for item in request.expected_target_layers) != request.expected_target_layers:
        raise ValueError("copy target-layer state no longer matches the approved plan")
    objects = {state.handle.casefold(): entity for state, entity in current_pairs}
    created_layers: list[str] = []
    created: list[tuple[Any, Point3D, Point3D, LiveLineEvidence, str | None]] = []
    doc.StartUndoMark()
    try:
        if isinstance(request.request, CopyToNewLayerRequest):
            definition = request.request.new_layer
            layer = doc.Layers.Add(definition.name)
            layer.Color, layer.Linetype, layer.Lineweight = definition.color, definition.linetype, definition.lineweight
            created_layers.append(definition.name)
        evidence = {item.handle.casefold(): item for item in request.expected_sources}
        for spec in plan.copies:
            source = evidence[spec.source_handle.casefold()]
            entity = objects[spec.source_handle.casefold()].Copy()
            start, end = _transform(source.start, spec.transform), _transform(source.end, spec.transform)
            entity.StartPoint, entity.EndPoint = _variant(start), _variant(end)
            if spec.target_layer is not None:
                entity.Layer = spec.target_layer
            created.append((entity, start, end, source, spec.target_layer))
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    for entity, start, end, source, target_layer in created:
        if (
            str(entity.Handle).casefold() not in available
            or _point(entity.StartPoint) != start
            or _point(entity.EndPoint) != end
            or str(entity.Layer).casefold() != (target_layer or source.layer).casefold()
            or int(entity.Color) != source.color
            or str(entity.Linetype) != source.linetype
            or int(entity.Lineweight) != source.lineweight
            or abs(float(entity.Thickness) - source.thickness) > 1e-9
        ):
            raise RuntimeError(f"{plan.command_alias} postcondition failed")
    if isinstance(request.request, CopyToNewLayerRequest):
        definition = request.request.new_layer
        state = _layer(doc, definition.name)
        if (
            not state.exists
            or state.color != definition.color
            or (state.linetype or "").casefold() != definition.linetype.casefold()
            or state.lineweight != definition.lineweight
        ):
            raise RuntimeError("CNL layer postcondition failed")
    return LiveBatch20Result(
        document_name=str(doc.Name),
        command_alias=plan.command_alias,
        created_handles=tuple(str(item[0].Handle) for item in created),
        created_layers=tuple(created_layers),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def preview_live_cut(request: CutRequest, snapshots: tuple[CurveSnapshot, ...]) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    plan = plan_cut(request, snapshots)
    payload = {
        "command_alias": request.alias.value,
        "request": request.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in snapshots],
        "plan": plan.model_dump(mode="json"),
    }
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "live_executable": False,
        "blocked_reason": CUT_BLOCKED,
    }


def register_live_batch20_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(title="Preview live xiCAD Batch 20 operation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    execute = ToolAnnotations(title="Execute live xiCAD Batch 20 operation", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
    registrations = tuple(
        (f"xicad_preview_live_{alias.lower()}", preview_live_cut, preview) for alias in ("FE", "FM", "FR", "FT", "FX", "XT")
    ) + (
        ("xicad_preview_live_ard", preview_live_ard, preview),
        ("xicad_execute_live_ard", execute_live_copy, execute),
        ("xicad_preview_live_arp", preview_live_arp, preview),
        ("xicad_execute_live_arp", execute_live_copy, execute),
        ("xicad_preview_live_arv", preview_live_arv, preview),
        ("xicad_execute_live_arv", execute_live_copy, execute),
        ("xicad_preview_live_cnl", preview_live_cnl, preview),
        ("xicad_execute_live_cnl", execute_live_copy, execute),
        ("xicad_preview_live_cr", preview_live_cr, preview),
        ("xicad_execute_live_cr", execute_live_copy, execute),
        ("xicad_preview_live_ctl", preview_live_ctl, preview),
        ("xicad_execute_live_ctl", execute_live_copy, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
