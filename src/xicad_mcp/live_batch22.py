from __future__ import annotations

import hashlib
import json
from math import cos, radians, sin
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch22a import (
    OffsetCurrentLayerRequest,
    OffsetMultiRequest,
    RandomCopyRequest,
    RotateMultiRequest,
    SolidMoveBackRequest,
    ToleranceOffsetRequest,
    plan_offset_current_layer,
    plan_offset_multi,
    plan_offset_tolerance,
    plan_random_copy,
    plan_rotate_multi,
    plan_solid_move_back,
)
from .headless_core_batch22b import (
    BoxMoveRequest,
    DboxAutoCopyRequest,
    DynamicScaleRequest,
    ScaleMultiRequest,
    SequentialScaleRequest,
    WallRecoverRequest,
    plan_box_move,
    plan_dbox_auto_copy,
    plan_dynamic_scale,
    plan_scale_multi,
    plan_sequential_scale,
    plan_wall_recover,
)

OffsetRequest = OffsetMultiRequest | OffsetCurrentLayerRequest | ToleranceOffsetRequest
ExecutableRequest = (
    OffsetRequest
    | RotateMultiRequest
    | ScaleMultiRequest
    | SequentialScaleRequest
    | WallRecoverRequest
    | BoxMoveRequest
    | DboxAutoCopyRequest
)


class LiveLineEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    object_name: str
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
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    color: int
    linetype: str
    lineweight: int
    locked: bool
    is_xref: bool


class LiveBatch22ExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ExecutableRequest
    expected_sources: tuple[LiveLineEvidence, ...]
    expected_target_layers: tuple[LiveLayerEvidence, ...] = ()
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch22Result(BaseModel):
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
    "RDC": "legacy base point and placement transform are unrecovered; deterministic destinations alone are insufficient",
    "SB": "ZWCAD draw-order collection semantics and legacy relative-order policy are not recovered",
    "DAS": "legacy dynamic scale linkage and annotation construction are compiled and unrecovered",
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


def _point(value: Any) -> Point3D:
    values = tuple(float(item) for item in value)
    return Point3D(x=values[0], y=values[1], z=values[2])


def _variant(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])


def _line(doc: Any, handle: str) -> tuple[LiveLineEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None or str(entity.ObjectName).casefold() != "acdbline":
        raise ValueError(f"Batch 22 live execution requires an AcDbLine source: {handle}")
    layer = str(entity.Layer)
    state = LiveLineEvidence(
        handle=str(entity.Handle),
        object_name=str(entity.ObjectName),
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
        raise ValueError(f"Batch 22 source is locked or xref-dependent: {handle}")
    return state, entity


def _layer(doc: Any, name: str) -> LiveLayerEvidence:
    try:
        layer = doc.Layers.Item(name)
    except Exception as exc:
        raise ValueError(f"Batch 22 target layer does not exist: {name}") from exc
    actual = str(layer.Name)
    state = LiveLayerEvidence(
        name=actual,
        color=int(layer.Color),
        linetype=str(layer.Linetype),
        lineweight=int(layer.Lineweight),
        locked=bool(layer.Lock),
        is_xref="|" in actual,
    )
    if state.locked or state.is_xref:
        raise ValueError(f"Batch 22 target layer is locked or xref-dependent: {name}")
    return state


def _plan(request: Any) -> Any:
    if isinstance(request, OffsetMultiRequest):
        return plan_offset_multi(request)
    if isinstance(request, OffsetCurrentLayerRequest):
        return plan_offset_current_layer(request)
    if isinstance(request, ToleranceOffsetRequest):
        return plan_offset_tolerance(request)
    if isinstance(request, RandomCopyRequest):
        return plan_random_copy(request)
    if isinstance(request, RotateMultiRequest):
        return plan_rotate_multi(request)
    if isinstance(request, SolidMoveBackRequest):
        return plan_solid_move_back(request)
    if isinstance(request, ScaleMultiRequest):
        return plan_scale_multi(request)
    if isinstance(request, SequentialScaleRequest):
        return plan_sequential_scale(request)
    if isinstance(request, WallRecoverRequest):
        return plan_wall_recover(request)
    if isinstance(request, BoxMoveRequest):
        return plan_box_move(request)
    if isinstance(request, DynamicScaleRequest):
        return plan_dynamic_scale(request)
    return plan_dbox_auto_copy(request)


def _source_handles(request: ExecutableRequest) -> tuple[str, ...]:
    if isinstance(request, OffsetMultiRequest):
        return (request.source_handle,)
    if isinstance(request, (OffsetCurrentLayerRequest, ToleranceOffsetRequest)):
        return request.source_handles
    if isinstance(request, RotateMultiRequest):
        return tuple(item.handle for item in request.targets)
    if isinstance(request, ScaleMultiRequest):
        return tuple(item.handle for item in request.items)
    if isinstance(request, SequentialScaleRequest):
        return tuple(item.handle for item in request.items)
    if isinstance(request, WallRecoverRequest):
        return tuple(dict.fromkeys(request.boundary_line_handles + request.intermediate_delete_handles))
    return request.source_handles if isinstance(request, BoxMoveRequest) else request.source_entity_handles


def _target_layer_names(plan: Any) -> tuple[str, ...]:
    if hasattr(plan, "operations") and plan.command_alias.startswith("O"):
        return tuple(dict.fromkeys(item.target_layer for item in plan.operations if item.target_layer is not None))
    if plan.command_alias == "WR":
        return tuple(dict.fromkeys(item.layer for item in plan.creates))
    return ()


def _payload(
    alias: str,
    request: Any,
    sources: tuple[LiveLineEvidence, ...],
    layers: tuple[LiveLayerEvidence, ...],
    plan: Any,
) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
        "expected_target_layers": [item.model_dump(mode="json") for item in layers],
        "plan": plan.model_dump(mode="json"),
    }


def _preview_executable(request: ExecutableRequest, expected_alias: str) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _plan(request)
    if plan.command_alias != expected_alias:
        raise ValueError(f"{expected_alias} preview received a different request type")
    doc = _drawing(request.document_id)
    sources = tuple(_line(doc, handle)[0] for handle in _source_handles(request))
    layers = tuple(_layer(doc, name) for name in _target_layer_names(plan))
    payload = _payload(expected_alias, request, sources, layers, plan)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "AcDbLine only; exact geometry, entity properties, layers, document, and handles are stale-checked",
    }


def _preview_blocked(request: Any) -> dict[str, Any]:
    plan = _plan(request)
    payload = {
        "command_alias": plan.command_alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
    }
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "live_executable": False,
        "blocked_reason": BLOCKED[plan.command_alias],
    }


def preview_live_om(request: OffsetMultiRequest) -> dict[str, Any]:
    return _preview_executable(request, "OM")


def preview_live_oo(request: OffsetCurrentLayerRequest) -> dict[str, Any]:
    return _preview_executable(request, "OO")


def preview_live_ot(request: ToleranceOffsetRequest) -> dict[str, Any]:
    return _preview_executable(request, "OT")


def preview_live_rdc(request: RandomCopyRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_rm(request: RotateMultiRequest) -> dict[str, Any]:
    return _preview_executable(request, "RM")


def preview_live_sb(request: SolidMoveBackRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_sm(request: ScaleMultiRequest) -> dict[str, Any]:
    return _preview_executable(request, "SM")


def preview_live_ss(request: SequentialScaleRequest) -> dict[str, Any]:
    return _preview_executable(request, "SS")


def preview_live_wr(request: WallRecoverRequest) -> dict[str, Any]:
    return _preview_executable(request, "WR")


def preview_live_bmt(request: BoxMoveRequest) -> dict[str, Any]:
    return _preview_executable(request, "BMT")


def preview_live_das(request: DynamicScaleRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_dbc(request: DboxAutoCopyRequest) -> dict[str, Any]:
    return _preview_executable(request, "DBC")


def _rotate(point: Point3D, center: Point3D, angle_degrees: float) -> Point3D:
    angle = radians(angle_degrees)
    c, s = cos(angle), sin(angle)
    x, y = point.x - center.x, point.y - center.y
    return Point3D(x=center.x + c * x - s * y, y=center.y + s * x + c * y, z=point.z)


def _matrix(point: Point3D, matrix: Any) -> Point3D:
    values = (point.x, point.y, point.z, 1.0)
    return Point3D(
        x=sum(matrix[0][index] * values[index] for index in range(4)),
        y=sum(matrix[1][index] * values[index] for index in range(4)),
        z=sum(matrix[2][index] * values[index] for index in range(4)),
    )


def _translate(point: Point3D, displacement: Point3D) -> Point3D:
    return Point3D(x=point.x + displacement.x, y=point.y + displacement.y, z=point.z + displacement.z)


def _offset_endpoints(start: Point3D, end: Point3D, distance: float) -> tuple[Point3D, Point3D]:
    dx, dy = end.x - start.x, end.y - start.y
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 1e-12:
        raise ValueError("Batch 22 cannot offset a zero-length line")
    displacement = Point3D(x=-dy * distance / length, y=dx * distance / length)
    return _translate(start, displacement), _translate(end, displacement)


def _offset_result(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        if len(value) != 1:
            raise RuntimeError("Batch 22 line offset must produce exactly one entity")
        value = value[0]
    if str(value.ObjectName).casefold() != "acdbline":
        raise RuntimeError("Batch 22 line offset did not produce an AcDbLine")
    return value


def execute_live_batch22(request: LiveBatch22ExecuteRequest) -> LiveBatch22Result:
    plan = _plan(request.request)
    payload = _payload(
        plan.command_alias,
        request.request,
        request.expected_sources,
        request.expected_target_layers,
        plan,
    )
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 22 plan")
    doc = _drawing(request.request.document_id)
    current = tuple(_line(doc, item.handle) for item in request.expected_sources)
    if tuple(item[0] for item in current) != request.expected_sources:
        raise ValueError("Batch 22 source state no longer matches the approved preview")
    if tuple(_layer(doc, item.name) for item in request.expected_target_layers) != request.expected_target_layers:
        raise ValueError("Batch 22 target-layer state no longer matches the approved preview")
    objects = {state.handle.casefold(): entity for state, entity in current}
    evidence = {state.handle.casefold(): state for state in request.expected_sources}
    created: list[Any] = []
    changed: list[Any] = []
    erased: list[str] = []
    expected: list[tuple[Any, Point3D, Point3D, str, LiveLineEvidence | None]] = []
    doc.StartUndoMark()
    try:
        alias = plan.command_alias
        if alias in {"OM", "OO", "OT"}:
            tokens: dict[str, Any] = {}
            for operation in plan.operations:
                source = tokens.get(operation.source_handle, objects.get(operation.source_handle.casefold()))
                if source is None:
                    raise RuntimeError(f"offset source token is unavailable: {operation.source_handle}")
                source_state = _line(doc, str(source.Handle))[0]
                entity = _offset_result(source.Offset(operation.signed_distance))
                if operation.target_layer is not None:
                    entity.Layer = operation.target_layer
                tokens[operation.result_token] = entity
                created.append(entity)
                start, end = _offset_endpoints(source_state.start, source_state.end, operation.signed_distance)
                expected.append(
                    (entity, start, end, operation.target_layer or source_state.layer, source_state)
                )
        elif alias == "RM":
            for operation in plan.operations:
                source = evidence[operation.handle.casefold()]
                entity = objects[operation.handle.casefold()].Copy() if operation.keep_original else objects[operation.handle.casefold()]
                start = _rotate(source.start, operation.center, operation.angle_degrees)
                end = _rotate(source.end, operation.center, operation.angle_degrees)
                entity.StartPoint, entity.EndPoint = _variant(start), _variant(end)
                (created if operation.keep_original else changed).append(entity)
                expected.append((entity, start, end, source.layer, source))
        elif alias in {"SM", "SS"}:
            for transform in plan.transforms:
                source = evidence[transform.source_handle.casefold()]
                entity = objects[transform.source_handle.casefold()]
                start, end = _matrix(source.start, transform.matrix), _matrix(source.end, transform.matrix)
                entity.StartPoint, entity.EndPoint = _variant(start), _variant(end)
                changed.append(entity)
                expected.append((entity, start, end, source.layer, source))
        elif alias == "WR":
            for output in plan.creates:
                entity = doc.ModelSpace.AddLine(_variant(output.start), _variant(output.end))
                entity.Layer = output.layer
                created.append(entity)
                expected.append((entity, output.start, output.end, output.layer, None))
            for handle in plan.delete_handles:
                objects[handle.casefold()].Delete()
                erased.append(handle)
        else:
            for transform in plan.transforms:
                source = evidence[transform.source_handle.casefold()]
                original = objects[transform.source_handle.casefold()]
                entity = original.Copy() if transform.copy_entity else original
                start = _translate(source.start, transform.displacement)
                end = _translate(source.end, transform.displacement)
                entity.StartPoint, entity.EndPoint = _variant(start), _variant(end)
                (created if transform.copy_entity else changed).append(entity)
                expected.append((entity, start, end, source.layer, source))
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    if any(str(entity.Handle).casefold() not in available for entity in created + changed):
        raise RuntimeError(f"{plan.command_alias} postcondition failed: output entity missing")
    if any(handle.casefold() in available for handle in erased):
        raise RuntimeError(f"{plan.command_alias} postcondition failed: source was not erased")
    for entity, start, end, layer, source in expected:
        if _point(entity.StartPoint) != start or _point(entity.EndPoint) != end or str(entity.Layer).casefold() != layer.casefold():
            raise RuntimeError(f"{plan.command_alias} postcondition failed: geometry or layer mismatch")
        if source is not None and (
            int(entity.Color) != source.color
            or str(entity.Linetype) != source.linetype
            or int(entity.Lineweight) != source.lineweight
            or abs(float(entity.Thickness) - source.thickness) > 1e-9
        ):
            raise RuntimeError(f"{plan.command_alias} postcondition failed: entity properties changed")
    return LiveBatch22Result(
        document_name=str(doc.Name),
        command_alias=plan.command_alias,
        created_handles=tuple(str(item.Handle) for item in created),
        changed_handles=tuple(str(item.Handle) for item in changed),
        erased_handles=tuple(erased),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_batch22_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 22 operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 22 operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    functions = {
        "om": preview_live_om,
        "oo": preview_live_oo,
        "ot": preview_live_ot,
        "rdc": preview_live_rdc,
        "rm": preview_live_rm,
        "sb": preview_live_sb,
        "sm": preview_live_sm,
        "ss": preview_live_ss,
        "wr": preview_live_wr,
        "bmt": preview_live_bmt,
        "das": preview_live_das,
        "dbc": preview_live_dbc,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
        if alias.upper() not in BLOCKED:
            mcp.tool(name=f"xicad_execute_live_{alias}", annotations=execute)(execute_live_batch22)
