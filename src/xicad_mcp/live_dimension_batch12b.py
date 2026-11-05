from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch11 import DimensionSnapshot
from .headless_core_batch12 import (
    DimensionStyleSnapshot,
    DimensionSupplementRequest,
    DimensionUpdateRequest,
    EditDimensionScaleRequest,
    IntersectionLengthRequest,
    IntersectionOutput,
    LeaderAlignRequest,
    LeaderKind,
    LeaderSnapshot,
    LeaderStyleEditRequest,
    plan_dimension_supplement,
    plan_dimension_update,
    plan_edit_dimension_scale,
    plan_intersection_length,
    plan_leader_align,
)
from .live_dimension_batch11b import (
    _drawing,
    _fingerprint,
    _layout_objects,
    _point,
    _snapshots,
    _variant,
)


class LiveDimensionBatch12bExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: DimensionSupplementRequest | DimensionUpdateRequest | EditDimensionScaleRequest
    expected_dimensions: tuple[DimensionSnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveIlExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: IntersectionLengthRequest
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveLdaExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: LeaderAlignRequest
    expected_leaders: tuple[LeaderSnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveDimensionBatch12bResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...] = ()
    created_handles: tuple[str, ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def _dimension_payload(alias: str, request: Any, dimensions: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "request": request.model_dump(mode="json"),
        "expected_dimensions": [item.model_dump(mode="json") for item in dimensions],
    }


def _style_snapshots(doc: Any) -> tuple[DimensionStyleSnapshot, ...]:
    # DU only consumes style name and xref status. The remaining validated fields
    # are neutral placeholders and are never presented as recovered style state.
    return tuple(
        DimensionStyleSnapshot(
            name=str(style.Name),
            dimscale=1.0,
            text_style="Standard",
            text_height=1.0,
            arrow_size=1.0,
            extension_offset=0.0,
            baseline_spacing=1.0,
            decimal_places=0,
            is_xref="|" in str(style.Name),
        )
        for style in doc.DimStyles
    )


def _preview_dimensions(request: Any, alias: str, planner: Any) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    handles = request.target_handles
    dimensions, _objects = _snapshots(doc, handles)
    if alias == "DU":
        plan = planner(request, _style_snapshots(doc), dimensions)
    else:
        plan = planner(request, dimensions)
    payload = _dimension_payload(alias, request, dimensions)
    return {
        **payload,
        "change_count": len(plan.changes),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(plan.changes),
    }


def preview_live_dto(request: DimensionSupplementRequest) -> dict[str, Any]:
    return _preview_dimensions(request, "DTO", plan_dimension_supplement)


def preview_live_du(request: DimensionUpdateRequest) -> dict[str, Any]:
    return _preview_dimensions(request, "DU", plan_dimension_update)


def preview_live_ed(request: EditDimensionScaleRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    handles = request.target_handles
    snapshot_handles = handles
    if request.match_handle and request.match_handle.casefold() not in {item.casefold() for item in handles}:
        snapshot_handles = (*handles, request.match_handle)
    doc = _drawing(request.document_id)
    dimensions, _objects = _snapshots(doc, snapshot_handles)
    plan = plan_edit_dimension_scale(request, dimensions)
    payload = _dimension_payload("ED", request, dimensions)
    return {
        **payload,
        "change_count": len(plan.changes),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(plan.changes),
    }


def _validate_dimensions(alias: str, wrapped: LiveDimensionBatch12bExecuteRequest) -> tuple[Any, dict[str, Any]]:
    payload = _dimension_payload(alias, wrapped.request, wrapped.expected_dimensions)
    if wrapped.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact dimension request")
    doc = _drawing(wrapped.request.document_id)
    current, objects = _snapshots(doc, tuple(item.handle for item in wrapped.expected_dimensions))
    if current != wrapped.expected_dimensions:
        raise ValueError("dimension state no longer matches the approved plan")
    return doc, objects


def execute_live_dto(request: LiveDimensionBatch12bExecuteRequest) -> LiveDimensionBatch12bResult:
    if not isinstance(request.request, DimensionSupplementRequest):
        raise ValueError("DTO executor requires DimensionSupplementRequest")
    doc, objects = _validate_dimensions("DTO", request)
    plan = plan_dimension_supplement(request.request, request.expected_dimensions)
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            objects[change.handle.casefold()].TextOverride = change.replacement_override
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        if str(objects[change.handle.casefold()].TextOverride) != change.replacement_override:
            raise RuntimeError(f"DTO postcondition failed: {change.handle}")
    return _result(doc, "DTO", changed=tuple(item.handle for item in plan.changes))


def execute_live_du(request: LiveDimensionBatch12bExecuteRequest) -> LiveDimensionBatch12bResult:
    if not isinstance(request.request, DimensionUpdateRequest):
        raise ValueError("DU executor requires DimensionUpdateRequest")
    doc, objects = _validate_dimensions("DU", request)
    plan = plan_dimension_update(request.request, _style_snapshots(doc), request.expected_dimensions)
    preserved = {
        change.handle.casefold(): (str(objects[change.handle.casefold()].TextOverride), _point(objects[change.handle.casefold()].TextPosition))
        for change in plan.changes
    }
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            entity = objects[change.handle.casefold()]
            entity.StyleName = change.replacement_style
            override, position = preserved[change.handle.casefold()]
            if plan.preserve_text_override:
                entity.TextOverride = override
            if plan.preserve_text_position:
                entity.TextPosition = _variant(position)
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        entity = objects[change.handle.casefold()]
        override, position = preserved[change.handle.casefold()]
        if str(entity.StyleName).casefold() != change.replacement_style.casefold():
            raise RuntimeError(f"DU style postcondition failed: {change.handle}")
        if plan.preserve_text_override and str(entity.TextOverride) != override:
            raise RuntimeError(f"DU override postcondition failed: {change.handle}")
        if plan.preserve_text_position and _point(entity.TextPosition) != position:
            raise RuntimeError(f"DU position postcondition failed: {change.handle}")
    return _result(doc, "DU", changed=tuple(item.handle for item in plan.changes))


def execute_live_ed(request: LiveDimensionBatch12bExecuteRequest) -> LiveDimensionBatch12bResult:
    if not isinstance(request.request, EditDimensionScaleRequest):
        raise ValueError("ED executor requires EditDimensionScaleRequest")
    doc, objects = _validate_dimensions("ED", request)
    plan = plan_edit_dimension_scale(request.request, request.expected_dimensions)
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            objects[change.handle.casefold()].ScaleFactor = change.replacement_scale
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        if abs(float(objects[change.handle.casefold()].ScaleFactor) - change.replacement_scale) > 1e-9:
            raise RuntimeError(f"ED postcondition failed: {change.handle}")
    return _result(doc, "ED", changed=tuple(item.handle for item in plan.changes))


def _il_payload(request: IntersectionLengthRequest) -> dict[str, Any]:
    return {"command_alias": "IL", "request": request.model_dump(mode="json")}


def preview_live_il(request: IntersectionLengthRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    plan = plan_intersection_length(request)
    payload = _il_payload(request)
    return {
        **payload,
        "results": [item.model_dump(mode="json") for item in plan.results],
        "create_count": len(plan.dimensions) + len(plan.text_points),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": request.output is not IntersectionOutput.RETURN_ONLY,
    }


def execute_live_il(request: LiveIlExecuteRequest) -> LiveDimensionBatch12bResult:
    if request.request.output is IntersectionOutput.RETURN_ONLY:
        raise ValueError("IL return_only is CAD-free and does not require a live executor")
    if request.approval_fingerprint != _fingerprint(_il_payload(request.request)):
        raise ValueError("approval fingerprint does not match the exact IL request")
    doc = _drawing(request.request.document_id)
    plan = plan_intersection_length(request.request)
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        for spec in plan.dimensions:
            entity = doc.ModelSpace.AddDimAligned(
                _variant(spec.first_point), _variant(spec.second_point), _variant(spec.dimension_line_point)
            )
            entity.StyleName = spec.style
            created.append(entity)
        if plan.text_points:
            height = float(doc.GetVariable("TEXTSIZE"))
            for result, point in zip(plan.results, plan.text_points, strict=True):
                created.append(doc.ModelSpace.AddText(result.rendered, _variant(point), height))
    finally:
        doc.EndUndoMark()
    available = _layout_objects(doc)
    if any(str(item.Handle).casefold() not in available for item in created):
        raise RuntimeError("IL postcondition failed: created entity is unavailable")
    return _result(doc, "IL", created=tuple(str(item.Handle) for item in created))


def _leader_snapshot(doc: Any, handle: str) -> tuple[LeaderSnapshot, Any]:
    entity = _layout_objects(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"leader not found: {handle}")
    if str(entity.ObjectName).casefold() != "acdb2dleader":
        raise ValueError("live LDA supports proven classic AcDb2dLeader coordinate semantics only")
    coordinates = tuple(float(value) for value in entity.Coordinates)
    if len(coordinates) < 6 or len(coordinates) % 3:
        raise ValueError("leader coordinates are incomplete")
    layer = str(entity.Layer)
    return (
        LeaderSnapshot(
            handle=str(entity.Handle),
            kind=LeaderKind.LEADER,
            style=str(entity.StyleName),
            start_point=Point3D(x=coordinates[0], y=coordinates[1], z=coordinates[2]),
            end_point=Point3D(x=coordinates[-3], y=coordinates[-2], z=coordinates[-1]),
            locked_layer=bool(doc.Layers.Item(layer).Lock),
            is_xref="|" in layer,
        ),
        entity,
    )


def _leader_payload(request: LeaderAlignRequest, leaders: tuple[LeaderSnapshot, ...]) -> dict[str, Any]:
    return {
        "command_alias": "LDA",
        "request": request.model_dump(mode="json"),
        "expected_leaders": [item.model_dump(mode="json") for item in leaders],
    }


def preview_live_lda(request: LeaderAlignRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    leaders = tuple(_leader_snapshot(doc, handle)[0] for handle in request.target_handles)
    plan = plan_leader_align(request, leaders)
    payload = _leader_payload(request, leaders)
    return {
        **payload,
        "change_count": len(plan.changes),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(plan.changes),
    }


def _coordinate_variant(values: list[float]) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)


def execute_live_lda(request: LiveLdaExecuteRequest) -> LiveDimensionBatch12bResult:
    if request.approval_fingerprint != _fingerprint(_leader_payload(request.request, request.expected_leaders)):
        raise ValueError("approval fingerprint does not match the exact LDA request")
    doc = _drawing(request.request.document_id)
    pairs = [_leader_snapshot(doc, item.handle) for item in request.expected_leaders]
    current = tuple(item[0] for item in pairs)
    if current != request.expected_leaders:
        raise ValueError("leader state no longer matches the approved plan")
    objects = {snapshot.handle.casefold(): entity for snapshot, entity in pairs}
    plan = plan_leader_align(request.request, current)
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            entity = objects[change.handle.casefold()]
            coordinates = list(float(value) for value in entity.Coordinates)
            offset = 0 if request.request.endpoint == "start" else len(coordinates) - 3
            coordinates[offset : offset + 3] = [
                change.replacement_point.x,
                change.replacement_point.y,
                change.replacement_point.z,
            ]
            entity.Coordinates = _coordinate_variant(coordinates)
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        snapshot, _entity = _leader_snapshot(doc, change.handle)
        actual = snapshot.start_point if request.request.endpoint == "start" else snapshot.end_point
        if actual != change.replacement_point:
            raise RuntimeError(f"LDA postcondition failed: {change.handle}")
    return _result(doc, "LDA", changed=tuple(item.handle for item in plan.changes))


def preview_live_lse(request: LeaderStyleEditRequest) -> dict[str, Any]:
    del request
    raise ValueError(
        "live LSE is blocked: ZWCAD ActiveX does not expose a proven writable Leader/MLeader style collection contract"
    )


def _result(
    doc: Any,
    alias: str,
    *,
    changed: tuple[str, ...] = (),
    created: tuple[str, ...] = (),
) -> LiveDimensionBatch12bResult:
    return LiveDimensionBatch12bResult(
        document_name=str(doc.Name),
        command_alias=alias,
        changed_handles=changed,
        created_handles=created,
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_dimension_batch12b_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 12B operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 12B operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_dto", preview_live_dto, preview),
        ("xicad_execute_live_dto", execute_live_dto, execute),
        ("xicad_preview_live_du", preview_live_du, preview),
        ("xicad_execute_live_du", execute_live_du, execute),
        ("xicad_preview_live_ed", preview_live_ed, preview),
        ("xicad_execute_live_ed", execute_live_ed, execute),
        ("xicad_preview_live_il", preview_live_il, preview),
        ("xicad_execute_live_il", execute_live_il, execute),
        ("xicad_preview_live_lda", preview_live_lda, preview),
        ("xicad_execute_live_lda", execute_live_lda, execute),
        ("xicad_preview_live_lse", preview_live_lse, preview),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
