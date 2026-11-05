from __future__ import annotations

import hashlib
import json
from math import cos, radians, sin
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch21a import (
    DivideArcCopyRequest,
    DivideCopyRequest,
    ExtendLineRequest,
    JoinLineRequest,
    LineSnapshot,
    MlineConvertRequest,
    MlineSnapshot,
    MultiCopyRequest,
    plan_divide_arc_copy,
    plan_divide_copy,
    plan_extend_line,
    plan_join_line,
    plan_mline_convert,
    plan_multi_copy,
)
from .headless_core_batch21b import (
    BothSidesOffsetRequest,
    IntegratedOffsetRequest,
    MeasureRequest,
    ObjectAlignAngleRequest,
    ObjectAlignRequest,
    OffsetEraseRequest,
    plan_both_sides_offset,
    plan_integrated_offset,
    plan_measure,
    plan_object_align,
    plan_object_align_angle,
    plan_offset_erase,
)

TransformRequest = (
    DivideArcCopyRequest | DivideCopyRequest | MultiCopyRequest | ObjectAlignRequest | ObjectAlignAngleRequest
)
OffsetRequest = BothSidesOffsetRequest | OffsetEraseRequest | IntegratedOffsetRequest
ExecutableRequest = TransformRequest | ExtendLineRequest | OffsetRequest | JoinLineRequest


class LiveLineEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
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


class LiveBatch21ExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ExecutableRequest
    expected_sources: tuple[LiveLineEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch21Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...] = ()
    changed_handles: tuple[str, ...] = ()
    erased_handles: tuple[str, ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


BLOCKED = {
    "MM": "placement entity type and legacy marker/block policy are unrecovered",
    "MLC": "MLINE style decomposition and component provenance cannot be verified through the recovered contract",
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


def _xy_variant(points: tuple[Point3D, ...]) -> Any:
    import pythoncom
    import win32com.client

    coordinates = [coordinate for point in points for coordinate in (point.x, point.y)]
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, coordinates)


def _line(doc: Any, handle: str) -> tuple[LiveLineEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None or str(entity.ObjectName).casefold() != "acdbline":
        raise ValueError(f"Batch 21 live execution requires an AcDbLine source: {handle}")
    layer = str(entity.Layer)
    evidence = LiveLineEvidence(
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
    if evidence.locked_layer or evidence.is_xref:
        raise ValueError(f"Batch 21 source is locked or xref-dependent: {handle}")
    return evidence, entity


def _handles(request: ExecutableRequest) -> tuple[str, ...]:
    if isinstance(request, (DivideArcCopyRequest, DivideCopyRequest, MultiCopyRequest)):
        return request.source_handles
    if isinstance(request, (ObjectAlignRequest, ObjectAlignAngleRequest)):
        return tuple(item.handle for item in request.items)
    if isinstance(request, ExtendLineRequest):
        return request.target_handles
    if isinstance(request, JoinLineRequest):
        return request.ordered_handles
    if isinstance(request, BothSidesOffsetRequest | OffsetEraseRequest):
        return (request.source_handle,)
    return request.connected_source_handles


def _line_snapshots(states: tuple[LiveLineEvidence, ...]) -> tuple[LineSnapshot, ...]:
    return tuple(
        LineSnapshot(
            handle=s.handle, start=s.start, end=s.end, layer=s.layer, is_xref=s.is_xref, locked_layer=s.locked_layer
        )
        for s in states
    )


def _plan(request: ExecutableRequest, states: tuple[LiveLineEvidence, ...]) -> Any:
    if isinstance(request, DivideArcCopyRequest):
        return plan_divide_arc_copy(request)
    if isinstance(request, DivideCopyRequest):
        return plan_divide_copy(request)
    if isinstance(request, MultiCopyRequest):
        return plan_multi_copy(request)
    if isinstance(request, ObjectAlignRequest):
        return plan_object_align(request)
    if isinstance(request, ObjectAlignAngleRequest):
        return plan_object_align_angle(request)
    if isinstance(request, ExtendLineRequest):
        return plan_extend_line(request, _line_snapshots(states))
    if isinstance(request, JoinLineRequest):
        return plan_join_line(request, _line_snapshots(states))
    if isinstance(request, BothSidesOffsetRequest):
        return plan_both_sides_offset(request)
    if isinstance(request, OffsetEraseRequest):
        return plan_offset_erase(request)
    return plan_integrated_offset(request)


def _alias(request: Any) -> str:
    return {
        DivideArcCopyRequest: "DAC",
        DivideCopyRequest: "DVC",
        ExtendLineRequest: "EXL",
        JoinLineRequest: "JL",
        MultiCopyRequest: "MC",
        MlineConvertRequest: "MLC",
        MeasureRequest: "MM",
        ObjectAlignRequest: "OA",
        ObjectAlignAngleRequest: "OAA",
        BothSidesOffsetRequest: "OB",
        OffsetEraseRequest: "OE",
        IntegratedOffsetRequest: "OI",
    }[type(request)]


def _payload(alias: str, request: Any, states: tuple[LiveLineEvidence, ...], plan: Any) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "request": request.model_dump(mode="json"),
        "expected_sources": [s.model_dump(mode="json") for s in states],
        "plan": plan.model_dump(mode="json"),
    }


def _preview_executable(request: ExecutableRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    doc = _drawing(request.document_id)
    if isinstance(request, JoinLineRequest):
        target = doc.Layers.Item(request.target_layer)
        if bool(target.Lock) or "|" in str(target.Name):
            raise ValueError("JL target layer is locked or xref-dependent")
    states = tuple(_line(doc, handle)[0] for handle in _handles(request))
    plan = _plan(request, states)
    alias = _alias(request)
    payload = _payload(alias, request, states, plan)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "AcDbLine sources only; exact geometry and entity properties are stale-checked",
    }


def _preview_blocked(request: Any, plan: Any) -> dict[str, Any]:
    alias = _alias(request)
    payload = {"command_alias": alias, "request": request.model_dump(mode="json"), "plan": plan.model_dump(mode="json")}
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "live_executable": False,
        "blocked_reason": BLOCKED[alias],
    }


def preview_live_dac(request: DivideArcCopyRequest) -> dict[str, Any]:
    return _preview_executable(request)


def preview_live_dvc(request: DivideCopyRequest) -> dict[str, Any]:
    return _preview_executable(request)


def preview_live_exl(request: ExtendLineRequest) -> dict[str, Any]:
    return _preview_executable(request)


def preview_live_mc(request: MultiCopyRequest) -> dict[str, Any]:
    return _preview_executable(request)


def preview_live_oa(request: ObjectAlignRequest) -> dict[str, Any]:
    return _preview_executable(request)


def preview_live_oaa(request: ObjectAlignAngleRequest) -> dict[str, Any]:
    return _preview_executable(request)


def preview_live_ob(request: BothSidesOffsetRequest) -> dict[str, Any]:
    return _preview_executable(request)


def preview_live_oe(request: OffsetEraseRequest) -> dict[str, Any]:
    return _preview_executable(request)


def preview_live_oi(request: IntegratedOffsetRequest) -> dict[str, Any]:
    return _preview_executable(request)


def preview_live_mm(request: MeasureRequest) -> dict[str, Any]:
    return _preview_blocked(request, plan_measure(request))


def preview_live_jl(request: JoinLineRequest) -> dict[str, Any]:
    return _preview_executable(request)


def preview_live_mlc(request: MlineConvertRequest, snapshots: tuple[MlineSnapshot, ...]) -> dict[str, Any]:
    return _preview_blocked(request, plan_mline_convert(request, snapshots))


def _transform(point: Point3D, transform: Any) -> Point3D:
    if hasattr(transform, "translation"):
        angle = radians(transform.rotation_degrees)
        c, s = cos(angle), sin(angle)
        center = transform.rotation_center
        x, y = point.x - center.x, point.y - center.y
        return Point3D(
            x=center.x + c * x - s * y + transform.translation.x,
            y=center.y + s * x + c * y + transform.translation.y,
            z=point.z + transform.translation.z,
        )
    matrix = transform.transform
    values = (point.x, point.y, point.z, 1.0)
    return Point3D(
        x=sum(matrix[0][i] * values[i] for i in range(4)),
        y=sum(matrix[1][i] * values[i] for i in range(4)),
        z=sum(matrix[2][i] * values[i] for i in range(4)),
    )


def execute_live_batch21(request: LiveBatch21ExecuteRequest) -> LiveBatch21Result:
    alias = _alias(request.request)
    doc = _drawing(request.request.document_id)
    current = tuple(_line(doc, state.handle) for state in request.expected_sources)
    if tuple(item[0] for item in current) != request.expected_sources:
        raise ValueError("Batch 21 source state no longer matches the approved preview")
    plan = _plan(request.request, request.expected_sources)
    payload = _payload(alias, request.request, request.expected_sources, plan)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 21 plan")
    objects = {state.handle.casefold(): entity for state, entity in current}
    created: list[Any] = []
    changed: list[Any] = []
    erased: list[str] = []
    expected_geometry: list[tuple[Any, Point3D, Point3D, str]] = []
    expected_polylines: list[tuple[Any, tuple[Point3D, ...], str]] = []
    doc.StartUndoMark()
    try:
        if alias in {"DAC", "DVC", "MC", "OA", "OAA"}:
            for spec in plan.transforms:
                source = request.expected_sources[
                    [s.handle.casefold() for s in request.expected_sources].index(spec.source_handle.casefold())
                ]
                entity = (
                    objects[spec.source_handle.casefold()].Copy()
                    if getattr(spec, "copy_entity", True)
                    else objects[spec.source_handle.casefold()]
                )
                entity.StartPoint = _variant(_transform(source.start, spec))
                entity.EndPoint = _variant(_transform(source.end, spec))
                expected_geometry.append(
                    (entity, _transform(source.start, spec), _transform(source.end, spec), source.layer)
                )
                (created if entity is not objects[spec.source_handle.casefold()] else changed).append(entity)
        elif alias == "EXL":
            for handle, endpoints in plan.endpoints.items():
                entity = objects[handle.casefold()]
                entity.StartPoint, entity.EndPoint = _variant(endpoints[0]), _variant(endpoints[1])
                changed.append(entity)
                expected_geometry.append((entity, endpoints[0], endpoints[1], str(entity.Layer)))
        elif alias == "JL":
            elevations = {round(point.z, 9) for point in plan.vertices}
            if len(elevations) != 1:
                raise ValueError("JL live AcDbPolyline output requires all vertices on one elevation")
            layer = doc.Layers.Item(plan.target_layer)
            if bool(layer.Lock) or "|" in str(layer.Name):
                raise ValueError("JL target layer is locked or xref-dependent")
            entity = doc.ModelSpace.AddLightWeightPolyline(_xy_variant(plan.vertices))
            entity.Layer = plan.target_layer
            entity.Elevation = plan.vertices[0].z
            entity.Closed = False
            created.append(entity)
            expected_polylines.append((entity, plan.vertices, plan.target_layer))
            for handle in plan.delete_handles:
                objects[handle.casefold()].Delete()
                erased.append(handle)
        else:
            for output in plan.creates:
                for start, end in zip(output.vertices, output.vertices[1:], strict=False):
                    entity = doc.ModelSpace.AddLine(_variant(start), _variant(end))
                    entity.Layer = output.layer
                    created.append(entity)
                    expected_geometry.append((entity, start, end, output.layer))
                if output.closed:
                    entity = doc.ModelSpace.AddLine(_variant(output.vertices[-1]), _variant(output.vertices[0]))
                    entity.Layer = output.layer
                    created.append(entity)
                    expected_geometry.append((entity, output.vertices[-1], output.vertices[0], output.layer))
            for handle in plan.delete_handles:
                objects[handle.casefold()].Delete()
                erased.append(handle)
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    if any(str(entity.Handle).casefold() not in available for entity in created + changed):
        raise RuntimeError(f"{alias} postcondition failed: output entity missing")
    if any(
        _point(entity.StartPoint) != start
        or _point(entity.EndPoint) != end
        or str(entity.Layer).casefold() != layer.casefold()
        for entity, start, end, layer in expected_geometry
    ):
        raise RuntimeError(f"{alias} postcondition failed: output geometry or layer mismatch")
    if any(
        tuple(float(value) for value in entity.Coordinates)
        != tuple(coordinate for point in vertices for coordinate in (point.x, point.y))
        or float(entity.Elevation) != vertices[0].z
        or bool(entity.Closed)
        or str(entity.Layer).casefold() != layer.casefold()
        for entity, vertices, layer in expected_polylines
    ):
        raise RuntimeError(f"{alias} postcondition failed: polyline geometry or layer mismatch")
    if any(handle.casefold() in available for handle in erased):
        raise RuntimeError(f"{alias} postcondition failed: source was not erased")
    return LiveBatch21Result(
        document_name=str(doc.Name),
        command_alias=alias,
        created_handles=tuple(str(e.Handle) for e in created),
        changed_handles=tuple(str(e.Handle) for e in changed),
        erased_handles=tuple(erased),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_batch21_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 21 operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 21 operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    functions = {
        "dac": preview_live_dac,
        "dvc": preview_live_dvc,
        "exl": preview_live_exl,
        "jl": preview_live_jl,
        "mc": preview_live_mc,
        "mlc": preview_live_mlc,
        "mm": preview_live_mm,
        "oa": preview_live_oa,
        "oaa": preview_live_oaa,
        "ob": preview_live_ob,
        "oe": preview_live_oe,
        "oi": preview_live_oi,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
        if alias.upper() not in BLOCKED:
            mcp.tool(name=f"xicad_execute_live_{alias}", annotations=execute)(execute_live_batch21)
