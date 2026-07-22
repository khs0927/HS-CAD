from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch16 import (
    CurtainWallRequest,
    DoorRequest,
    EscalatorElevationRequest,
    ExplodedViewRequest,
    plan_escalator_elevation,
    plan_exploded_view,
)
from .live_door_d1 import execute_live_d1, preview_live_d1


class LiveLayerEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    color: int
    linetype: str
    locked: bool
    is_xref: bool


class LiveDevExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ExplodedViewRequest
    expected_layer: LiveLayerEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveEedExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: EscalatorElevationRequest
    expected_layer: LiveLayerEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch16bResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    value = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


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


def _payload(alias: str, request: Any, layer: LiveLayerEvidence) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "request": request.model_dump(mode="json"),
        "expected_layer": layer.model_dump(mode="json"),
    }


def _variant(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])


def _entities(doc: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for block in doc.Blocks:
        if bool(block.IsLayout):
            for entity in block:
                result[str(entity.Handle).casefold()] = entity
    return result


def preview_live_dev(request: ExplodedViewRequest) -> dict[str, Any]:
    if request.draw_vertical:
        raise ValueError("live DEV vertical separators are blocked: the plan supplies points but no second endpoints")
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    plan = plan_exploded_view(request)
    layer = _layer(doc, plan.border_layer)
    payload = _payload("DEV", request, layer)
    return {
        **payload,
        "create_count": len(plan.horizontal_lines),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(plan.horizontal_lines),
    }


def preview_live_eed(request: EscalatorElevationRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    plan = plan_escalator_elevation(request)
    layer = _layer(doc, plan.layer)
    payload = _payload("EED", request, layer)
    return {
        **payload,
        "create_count": 1,
        "rise": plan.rise,
        "run": plan.run,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "scope_note": "creates the exact escalator slope line defined by the Batch 16 plan",
    }


def _execute_lines(
    alias: str,
    request: Any,
    layer: LiveLayerEvidence,
    fingerprint: str,
    lines: Any,
) -> LiveBatch16bResult:
    if fingerprint != _fingerprint(_payload(alias, request, layer)):
        raise ValueError("approval fingerprint does not match the exact drawing request")
    doc = _drawing(request.document_id)
    if _layer(doc, layer.name) != layer:
        raise ValueError("output layer state no longer matches the approved plan")
    created = []
    doc.StartUndoMark()
    try:
        for start, end in lines:
            entity = doc.ModelSpace.AddLine(_variant(start), _variant(end))
            entity.Layer = layer.name
            created.append((entity, start, end))
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    for entity, start, end in created:
        if str(entity.Handle).casefold() not in available:
            raise RuntimeError(f"{alias} postcondition failed: created line unavailable")
        if _point(entity.StartPoint) != start or _point(entity.EndPoint) != end:
            raise RuntimeError(f"{alias} postcondition failed: line endpoints differ")
    return LiveBatch16bResult(
        document_name=str(doc.Name),
        command_alias=alias,
        created_handles=tuple(str(item[0].Handle) for item in created),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def _point(value: Any) -> Point3D:
    values = tuple(float(item) for item in value)
    return Point3D(x=values[0], y=values[1], z=values[2])


def execute_live_dev(request: LiveDevExecuteRequest) -> LiveBatch16bResult:
    if request.request.draw_vertical:
        raise ValueError("live DEV executor supports horizontal borders only")
    plan = plan_exploded_view(request.request)
    return _execute_lines(
        "DEV", request.request, request.expected_layer, request.approval_fingerprint, plan.horizontal_lines
    )


def execute_live_eed(request: LiveEedExecuteRequest) -> LiveBatch16bResult:
    plan = plan_escalator_elevation(request.request)
    return _execute_lines(
        "EED", request.request, request.expected_layer, request.approval_fingerprint, (plan.endpoints,)
    )


def preview_live_cw(request: CurtainWallRequest) -> dict[str, Any]:
    del request
    raise ValueError("live CW is blocked: division fractions do not define bar, cap, and glass output geometry")


def preview_live_door(request: DoorRequest) -> dict[str, Any]:
    alias = request.variant.value.upper()
    raise ValueError(f"live {alias} is blocked: opening line and ratios do not define frame, leaf, and swing geometry")


def register_live_batch16b_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 16B operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 16B operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_cw", preview_live_cw, preview),
        ("xicad_preview_live_d1", preview_live_d1, preview),
        ("xicad_execute_live_d1", execute_live_d1, execute),
        ("xicad_preview_live_d2", preview_live_door, preview),
        ("xicad_preview_live_d3", preview_live_door, preview),
        ("xicad_preview_live_dev", preview_live_dev, preview),
        ("xicad_execute_live_dev", execute_live_dev, execute),
        ("xicad_preview_live_eed", preview_live_eed, preview),
        ("xicad_execute_live_eed", execute_live_eed, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
