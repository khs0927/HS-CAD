from __future__ import annotations

import hashlib
import json
from math import hypot
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch17 import (
    ElevatorRequest,
    EscalatorPlanRequest,
    HatchBoundaryRequest,
    HatchPointRequest,
    HeatGridRequest,
    InsulationRequest,
    plan_elevator,
    plan_escalator_plan,
    plan_heat_grid,
    plan_insulation,
)
from .live_batch16a import ZWCADLiveBatch16aAdapter


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


class _Preview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)


class LiveElvPreviewRequest(_Preview):
    request: ElevatorRequest


class LiveElvExecuteRequest(LiveElvPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveEpdPreviewRequest(_Preview):
    request: EscalatorPlanRequest


class LiveEpdExecuteRequest(LiveEpdPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveHgridPreviewRequest(_Preview):
    request: HeatGridRequest


class LiveHgridExecuteRequest(LiveHgridPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveHbPreviewRequest(_Preview):
    request: HatchBoundaryRequest


class LiveHpPreviewRequest(_Preview):
    request: HatchPointRequest


class LiveInsPreviewRequest(_Preview):
    request: InsulationRequest


class LiveBatch17aResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    postcondition_verified: bool


class ZWCADLiveBatch17aAdapter(ZWCADLiveBatch16aAdapter):
    pass


def _check_document(wrapper: _Preview) -> None:
    if wrapper.request.document_id.casefold() != wrapper.document_name.casefold():
        raise ValueError("request document_id must match document_name")


def _body(wrapper: _Preview) -> dict[str, Any]:
    return wrapper.model_dump(mode="json")


def _preview(wrapper: _Preview, plan: BaseModel) -> dict[str, Any]:
    body = _body(wrapper)
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def _verify_fingerprint(wrapper: BaseModel, fingerprint: str) -> None:
    body = wrapper.model_dump(mode="json", exclude={"approval_fingerprint"})
    if fingerprint != _hash(body):
        raise ValueError("approval fingerprint mismatch")


def _approved(request: BaseModel, fingerprint: str) -> BaseModel:
    return request.model_copy(update={"dry_run": False, "approval": Approval(approved=True, fingerprint=fingerprint)})


def _rectangle(center: Point3D, width: float, depth: float) -> tuple[Point3D, ...]:
    return tuple(
        Point3D(x=center.x + x, y=center.y + y, z=center.z)
        for x, y in (
            (-width / 2, -depth / 2),
            (width / 2, -depth / 2),
            (width / 2, depth / 2),
            (-width / 2, depth / 2),
        )
    )


def preview_live_elv(request: LiveElvPreviewRequest) -> dict[str, Any]:
    _check_document(request)
    adapter = ZWCADLiveBatch17aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.shaft_layer)
    adapter.validate_output_layer(request.request.car_layer)
    return _preview(request, plan_elevator(request.request))


def execute_live_elv(request: LiveElvExecuteRequest) -> LiveBatch17aResult:
    _check_document(request)
    _verify_fingerprint(request, request.approval_fingerprint)
    adapter = ZWCADLiveBatch17aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.shaft_layer)
    adapter.validate_output_layer(request.request.car_layer)
    plan = plan_elevator(_approved(request.request, request.approval_fingerprint))
    created, expected = [], []
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        shaft = _rectangle(plan.shaft.center, plan.shaft.width, plan.shaft.depth)
        created.append(adapter.lwpolyline(shaft, plan.shaft.layer, True))
        expected.append((shaft, True, plan.shaft.layer))
        for car in plan.cars:
            vertices = _rectangle(car.center, car.width, car.depth)
            created.append(adapter.lwpolyline(vertices, car.layer, True))
            expected.append((vertices, True, car.layer))
            y = car.center.y - car.depth / 2
            door = (
                Point3D(x=car.center.x - plan.door_width / 2, y=y, z=car.center.z),
                Point3D(x=car.center.x + plan.door_width / 2, y=y, z=car.center.z),
            )
            created.append(adapter.line(door[0], door[1], car.layer))
            expected.append((door, False, car.layer))
    finally:
        doc.EndUndoMark()
    return _verify_geometry(adapter, "ELV", created, expected)


def _offset_segment(start: Point3D, end: Point3D, distance: float) -> tuple[Point3D, Point3D]:
    dx, dy = end.x - start.x, end.y - start.y
    length = hypot(dx, dy)
    nx, ny = -dy / length * distance, dx / length * distance
    return (
        Point3D(x=start.x + nx, y=start.y + ny, z=start.z),
        Point3D(x=end.x + nx, y=end.y + ny, z=end.z),
    )


def preview_live_epd(request: LiveEpdPreviewRequest) -> dict[str, Any]:
    _check_document(request)
    adapter = ZWCADLiveBatch17aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.layer)
    return _preview(request, plan_escalator_plan(request.request))


def execute_live_epd(request: LiveEpdExecuteRequest) -> LiveBatch17aResult:
    _check_document(request)
    _verify_fingerprint(request, request.approval_fingerprint)
    adapter = ZWCADLiveBatch17aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.layer)
    plan = plan_escalator_plan(_approved(request.request, request.approval_fingerprint))
    start, end = plan.centerline
    segments = [
        (start, end),
        _offset_segment(start, end, plan.overall_width / 2),
        _offset_segment(start, end, -plan.overall_width / 2),
        _offset_segment(start, end, plan.tread_width / 2),
        _offset_segment(start, end, -plan.tread_width / 2),
    ]
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        created = [adapter.line(a, b, plan.layer) for a, b in segments]
    finally:
        doc.EndUndoMark()
    expected = [(segment, False, plan.layer) for segment in segments]
    return _verify_geometry(adapter, "EPD", created, expected)


def preview_live_hgrid(request: LiveHgridPreviewRequest) -> dict[str, Any]:
    _check_document(request)
    adapter = ZWCADLiveBatch17aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.layer)
    return _preview(request, plan_heat_grid(request.request))


def execute_live_hgrid(request: LiveHgridExecuteRequest) -> LiveBatch17aResult:
    _check_document(request)
    _verify_fingerprint(request, request.approval_fingerprint)
    adapter = ZWCADLiveBatch17aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.layer)
    plan = plan_heat_grid(_approved(request.request, request.approval_fingerprint))
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        created = [adapter.lwpolyline(plan.path, plan.layer)]
    finally:
        doc.EndUndoMark()
    return _verify_geometry(adapter, "HGRID", created, [(plan.path, False, plan.layer)])


def preview_live_hb(request: LiveHbPreviewRequest) -> dict[str, Any]:
    del request
    raise RuntimeError("HB is blocked: ZWCAD ActiveX does not expose reliable ordered hatch loop geometry")


def execute_live_hb(_request: Any) -> LiveBatch17aResult:
    raise RuntimeError("HB cannot execute through the conservative ActiveX adapter")


def preview_live_hp(request: LiveHpPreviewRequest) -> dict[str, Any]:
    del request
    raise RuntimeError("HP is blocked: hatch pattern origin mutation is not consistently exposed by ZWCAD ActiveX")


def execute_live_hp(_request: Any) -> LiveBatch17aResult:
    raise RuntimeError("HP cannot execute through the conservative ActiveX adapter")


def preview_live_ins(request: LiveInsPreviewRequest) -> dict[str, Any]:
    _check_document(request)
    adapter = ZWCADLiveBatch17aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.layer)
    return _preview(request, plan_insulation(request.request))


def execute_live_ins(_request: Any) -> LiveBatch17aResult:
    raise RuntimeError("INS is preview-only: the contract lacks explicit insulation zigzag vertices")


def _verify_geometry(
    adapter: ZWCADLiveBatch17aAdapter,
    alias: str,
    created: list[Any],
    expected: list[tuple[tuple[Point3D, ...], bool, str]],
) -> LiveBatch17aResult:
    handles = tuple(str(entity.Handle) for entity in created)
    after = adapter.entity_objects()
    if not all(handle.casefold() in after for handle in handles):
        raise RuntimeError(f"{alias} created handle postcondition failed")
    states = adapter.geometry(handles)
    if any(
        state.vertices != vertices or state.closed != closed or state.layer != layer
        for state, (vertices, closed, layer) in zip(states, expected, strict=True)
    ):
        raise RuntimeError(f"{alias} geometry postcondition failed")
    return LiveBatch17aResult(
        document_name=str(adapter.connect().Name),
        command_alias=alias,
        created_handles=handles,
        postcondition_verified=True,
    )


def register_live_batch17a_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 17A operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 17A geometry operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_elv", preview_live_elv, preview),
        ("xicad_execute_live_elv", execute_live_elv, execute),
        ("xicad_preview_live_epd", preview_live_epd, preview),
        ("xicad_execute_live_epd", execute_live_epd, execute),
        ("xicad_preview_live_hgrid", preview_live_hgrid, preview),
        ("xicad_execute_live_hgrid", execute_live_hgrid, execute),
        ("xicad_preview_live_hb", preview_live_hb, preview),
        ("xicad_preview_live_hp", preview_live_hp, preview),
        ("xicad_preview_live_ins", preview_live_ins, preview),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
