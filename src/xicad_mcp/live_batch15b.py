from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch15 import (
    DocumentSnapshot,
    ExplorerRequest,
    FrameSize,
    OpenDrawingRequest,
    QuickQuitRequest,
    StartRequest,
    SteelRequest,
    plan_explorer,
    plan_open_drawing,
    plan_quick_quit,
    plan_start,
    plan_steel,
)


class LiveLayerState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    exists: bool
    color: int | None = None
    linetype: str | None = None
    locked: bool = False
    is_xref: bool = False


class LiveSttExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: StartRequest
    expected_variables: dict[str, float]
    expected_layers: tuple[LiveLayerState, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBeExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: SteelRequest
    expected_layer: LiveLayerState
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch15bResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_system_variables: tuple[str, ...] = ()
    changed_layers: tuple[str, ...] = ()
    created_handles: tuple[str, ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _application() -> Any:
    import win32com.client

    return win32com.client.GetActiveObject("ZWCAD.Application.2026")


def _drawing(document_name: str) -> Any:
    app = _application()
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == document_name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {document_name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _layers(doc: Any) -> dict[str, Any]:
    return {str(layer.Name).casefold(): layer for layer in doc.Layers}


def _layer_state(doc: Any, name: str) -> LiveLayerState:
    layer = _layers(doc).get(name.casefold())
    if layer is None:
        return LiveLayerState(name=name, exists=False)
    actual_name = str(layer.Name)
    return LiveLayerState(
        name=actual_name,
        exists=True,
        color=int(layer.Color),
        linetype=str(layer.Linetype),
        locked=bool(layer.Lock),
        is_xref="|" in actual_name,
    )


def _entities(doc: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for block in doc.Blocks:
        if bool(block.IsLayout):
            for entity in block:
                result[str(entity.Handle).casefold()] = entity
    return result


def _variant_coordinates(points: tuple[Any, ...]) -> Any:
    import pythoncom
    import win32com.client

    values = [coordinate for point in points for coordinate in (point.x, point.y)]
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)


def _stt_payload(
    request: StartRequest,
    variables: dict[str, float],
    layers: tuple[LiveLayerState, ...],
) -> dict[str, Any]:
    return {
        "command_alias": "STT",
        "request": request.model_dump(mode="json"),
        "expected_variables": variables,
        "expected_layers": [layer.model_dump(mode="json") for layer in layers],
    }


def preview_live_stt(request: StartRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    if request.reference_file is not None:
        raise ValueError("live STT reference attachment is blocked: attachment policy is not specified")
    if request.frame_size is not FrameSize.NONE:
        raise ValueError("live STT frame insertion is blocked: block units and insertion semantics are not specified")
    doc = _drawing(request.document_id)
    plan = plan_start(request)
    variables = {name: float(doc.GetVariable(name)) for name in plan.system_variables}
    states = tuple(_layer_state(doc, spec.name) for spec in plan.create_layers)
    for spec, state in zip(plan.create_layers, states, strict=True):
        if state.is_xref:
            raise ValueError(f"live STT cannot modify xref-dependent layer: {state.name}")
        try:
            doc.Linetypes.Item(spec.linetype)
        except Exception as exc:
            raise ValueError(f"live STT linetype is unavailable: {spec.linetype}") from exc
    payload = _stt_payload(request, variables, states)
    return {
        **payload,
        "system_variable_change_count": len(plan.system_variables),
        "layer_change_count": len(plan.create_layers),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(plan.system_variables or plan.create_layers),
    }


def execute_live_stt(request: LiveSttExecuteRequest) -> LiveBatch15bResult:
    payload = _stt_payload(request.request, request.expected_variables, request.expected_layers)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact STT request")
    doc = _drawing(request.request.document_id)
    current_variables = {name: float(doc.GetVariable(name)) for name in request.expected_variables}
    current_layers = tuple(_layer_state(doc, state.name) for state in request.expected_layers)
    if current_variables != request.expected_variables or current_layers != request.expected_layers:
        raise ValueError("drawing setup state no longer matches the approved STT plan")
    plan = plan_start(request.request)
    doc.StartUndoMark()
    try:
        for name, value in plan.system_variables.items():
            doc.SetVariable(name, value)
        for spec in plan.create_layers:
            layer = _layers(doc).get(spec.name.casefold()) or doc.Layers.Add(spec.name)
            layer.Color = spec.color
            layer.Linetype = spec.linetype
    finally:
        doc.EndUndoMark()
    for name, value in plan.system_variables.items():
        if abs(float(doc.GetVariable(name)) - value) > 1e-9:
            raise RuntimeError(f"STT system-variable postcondition failed: {name}")
    for spec in plan.create_layers:
        state = _layer_state(doc, spec.name)
        if not state.exists or state.color != spec.color or (state.linetype or "").casefold() != spec.linetype.casefold():
            raise RuntimeError(f"STT layer postcondition failed: {spec.name}")
    return LiveBatch15bResult(
        document_name=str(doc.Name),
        command_alias="STT",
        changed_system_variables=tuple(plan.system_variables),
        changed_layers=tuple(spec.name for spec in plan.create_layers),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def _be_payload(request: SteelRequest, layer: LiveLayerState) -> dict[str, Any]:
    return {
        "command_alias": "BE",
        "request": request.model_dump(mode="json"),
        "expected_layer": layer.model_dump(mode="json"),
    }


def preview_live_be(request: SteelRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    plan = plan_steel(request)
    layer = _layer_state(doc, plan.layer)
    if not layer.exists or layer.locked or layer.is_xref:
        raise ValueError(f"live BE output layer is unavailable or locked: {plan.layer}")
    if len({point.z for point in plan.outline}) != 1:
        raise ValueError("live BE requires one output elevation")
    payload = _be_payload(request, layer)
    return {
        **payload,
        "create_count": 1,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "scope_note": "creates the exact closed outer-envelope polyline defined by the Batch 15 plan",
    }


def execute_live_be(request: LiveBeExecuteRequest) -> LiveBatch15bResult:
    payload = _be_payload(request.request, request.expected_layer)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact BE request")
    doc = _drawing(request.request.document_id)
    if _layer_state(doc, request.expected_layer.name) != request.expected_layer:
        raise ValueError("BE output layer state no longer matches the approved plan")
    plan = plan_steel(request.request)
    entity = None
    doc.StartUndoMark()
    try:
        entity = doc.ModelSpace.AddLightWeightPolyline(_variant_coordinates(plan.outline))
        entity.Elevation = plan.outline[0].z
        entity.Layer = plan.layer
        entity.Closed = True
    finally:
        doc.EndUndoMark()
    after = _entities(doc)
    if str(entity.Handle).casefold() not in after:
        raise RuntimeError("BE postcondition failed: created polyline is unavailable")
    coordinates = tuple(float(value) for value in entity.Coordinates)
    expected = tuple(coordinate for point in plan.outline for coordinate in (point.x, point.y))
    if coordinates != expected or not bool(entity.Closed) or str(entity.Layer).casefold() != plan.layer.casefold():
        raise RuntimeError("BE postcondition failed: created envelope differs from the approved plan")
    return LiveBatch15bResult(
        document_name=str(doc.Name),
        command_alias="BE",
        created_handles=(str(entity.Handle),),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def preview_live_exp(request: ExplorerRequest) -> dict[str, Any]:
    plan = plan_explorer(request)
    payload = {"command_alias": "EXP", "request": request.model_dump(mode="json")}
    return {
        **payload,
        "folder_path": plan.folder_path,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "blocked_reason": "external Explorer process launch is outside the CAD Undo boundary",
    }


def preview_live_open(request: OpenDrawingRequest) -> dict[str, Any]:
    plan = plan_open_drawing(request)
    payload = {"command_alias": plan.command_alias, "request": request.model_dump(mode="json")}
    return {
        **payload,
        "target_path": plan.target_path,
        "read_only": plan.read_only,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "blocked_reason": "opening another document is outside the active drawing Undo boundary",
    }


def preview_live_ol(request: OpenDrawingRequest) -> dict[str, Any]:
    if request.operation != "list_select":
        raise ValueError("OL requires operation=list_select")
    return preview_live_open(request)


def preview_live_on(request: OpenDrawingRequest) -> dict[str, Any]:
    if request.operation != "next":
        raise ValueError("ON requires operation=next")
    return preview_live_open(request)


def preview_live_qq(request: QuickQuitRequest) -> dict[str, Any]:
    app = _application()
    by_name = {str(doc.Name).casefold(): doc for doc in app.Documents}
    snapshots = []
    for name in request.target_document_ids:
        doc = by_name.get(name.casefold())
        if doc is None:
            raise ValueError(f"QQ document not found: {name}")
        full_name = str(doc.FullName)
        snapshots.append(
            DocumentSnapshot(
                document_id=str(doc.Name),
                path=full_name if full_name and full_name.casefold() != str(doc.Name).casefold() else None,
                modified=not bool(doc.Saved),
                read_only=bool(doc.ReadOnly),
            )
        )
    plan = plan_quick_quit(request, snapshots)
    payload = {
        "command_alias": "QQ",
        "request": request.model_dump(mode="json"),
        "expected_documents": [item.model_dump(mode="json") for item in snapshots],
    }
    return {
        **payload,
        "actions": [item.model_dump(mode="json") for item in plan.actions],
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "blocked_reason": "document save/close cannot be restored by drawing Undo",
    }


def register_live_batch15b_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 15B operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 15B operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_exp", preview_live_exp, preview),
        ("xicad_preview_live_ol", preview_live_ol, preview),
        ("xicad_preview_live_on", preview_live_on, preview),
        ("xicad_preview_live_qq", preview_live_qq, preview),
        ("xicad_preview_live_stt", preview_live_stt, preview),
        ("xicad_execute_live_stt", execute_live_stt, execute),
        ("xicad_preview_live_be", preview_live_be, preview),
        ("xicad_execute_live_be", execute_live_be, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
