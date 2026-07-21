from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch11 import (
    ContinueDimensionRequest,
    DimensionExtensionToggleRequest,
    DimensionGapRequest,
    DimensionKind,
    DimensionSnapshot,
    DimensionTextHomeRequest,
    ExtensionArrangeRequest,
    ExtensionLengthRequest,
    ExtensionLineTarget,
    plan_continue_dimension,
    plan_dimension_extension_toggle,
    plan_extension_arrange,
    plan_extension_length,
)


class LiveDdtExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: DimensionExtensionToggleRequest
    expected_dimensions: tuple[DimensionSnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveDeExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ContinueDimensionRequest
    expected_dimensions: tuple[DimensionSnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveDlaExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ExtensionArrangeRequest
    expected_dimensions: tuple[DimensionSnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveDllExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ExtensionLengthRequest
    expected_dimensions: tuple[DimensionSnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveDimensionBatch11Result(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...] = ()
    created_handles: tuple[str, ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


_KINDS = {
    "acdbaligneddimension": DimensionKind.ALIGNED,
    "acdbrotateddimension": DimensionKind.ROTATED,
}


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _drawing(document_name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == document_name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {document_name!r}, found {len(matches)}")
    doc = matches[0]
    doc.Activate()
    return doc


def _point(value: Any) -> Point3D:
    values = tuple(float(item) for item in value)
    return Point3D(x=values[0], y=values[1], z=values[2])


def _layout_objects(doc: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for block in doc.Blocks:
        if bool(block.IsLayout):
            for entity in block:
                result[str(entity.Handle).casefold()] = entity
    return result


def _snapshot(doc: Any, handle: str) -> tuple[DimensionSnapshot, Any]:
    entity = _layout_objects(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"dimension not found: {handle}")
    kind = _KINDS.get(str(entity.ObjectName).casefold())
    if kind is None:
        raise ValueError(f"live dimension type is unsupported: {entity.ObjectName}")
    layer = str(entity.Layer)
    layer_record = doc.Layers.Item(layer)
    text_position = _point(entity.TextPosition)
    extension_length = float(entity.ExtensionLineExtend)
    scale = float(entity.ScaleFactor)
    return (
        DimensionSnapshot(
            handle=str(entity.Handle),
            kind=kind,
            layer=layer,
            style=str(entity.StyleName),
            measurement=float(entity.Measurement),
            text_override=str(entity.TextOverride),
            text_position=text_position,
            # ActiveX has no default-text or dimension-line point accessor.
            # These placeholders are not used by the supported DDT/DE/DLA/DLL adapters.
            default_text_position=text_position,
            dimension_line_point=text_position,
            first_extension_origin=_point(entity.ExtLine1Point),
            second_extension_origin=_point(entity.ExtLine2Point),
            first_extension_suppressed=bool(entity.ExtLine1Suppress),
            second_extension_suppressed=bool(entity.ExtLine2Suppress),
            first_extension_length=extension_length,
            second_extension_length=extension_length,
            dimscale=scale,
            ltscale=float(entity.LinetypeScale),
            object_scale=scale,
            locked_layer=bool(layer_record.Lock),
            is_xref="|" in layer,
        ),
        entity,
    )


def _snapshots(doc: Any, handles: tuple[str, ...]) -> tuple[tuple[DimensionSnapshot, ...], dict[str, Any]]:
    snapshots: list[DimensionSnapshot] = []
    objects: dict[str, Any] = {}
    for handle in handles:
        snapshot, entity = _snapshot(doc, handle)
        snapshots.append(snapshot)
        objects[snapshot.handle.casefold()] = entity
    return tuple(snapshots), objects


def _payload(alias: str, request: Any, dimensions: tuple[DimensionSnapshot, ...]) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "request": request.model_dump(mode="json"),
        "expected_dimensions": [item.model_dump(mode="json") for item in dimensions],
    }


def _preview(request: Any, alias: str, handles: tuple[str, ...], planner: Any) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    dimensions, _objects = _snapshots(doc, handles)
    if any(item.kind is not DimensionKind.ALIGNED for item in dimensions):
        raise ValueError(f"live {alias} currently supports proven AcDbAlignedDimension semantics only")
    plan = planner(request, dimensions)
    payload = _payload(alias, request, dimensions)
    changes = getattr(plan, "changes", getattr(plan, "creates", ()))
    return {
        **payload,
        "change_count": len(changes),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(changes),
    }


def preview_live_ddt(request: DimensionExtensionToggleRequest) -> dict[str, Any]:
    return _preview(
        request,
        "DDT",
        request.target_handles,
        plan_dimension_extension_toggle,
    )


def preview_live_de(request: ContinueDimensionRequest) -> dict[str, Any]:
    return _preview(request, "DE", (request.source_handle,), plan_continue_dimension)


def preview_live_dg(request: DimensionGapRequest) -> dict[str, Any]:
    del request
    raise ValueError("live DG is blocked: ActiveX exposes no editable dimension-line point")


def preview_live_dh(request: DimensionTextHomeRequest) -> dict[str, Any]:
    del request
    raise ValueError("live DH is blocked: ActiveX exposes no default text-position accessor")


def preview_live_dla(request: ExtensionArrangeRequest) -> dict[str, Any]:
    return _preview(request, "DLA", request.target_handles, plan_extension_arrange)


def preview_live_dll(request: ExtensionLengthRequest) -> dict[str, Any]:
    if request.target is not ExtensionLineTarget.BOTH:
        raise ValueError("live DLL requires BOTH because ActiveX exposes one shared ExtensionLineExtend")
    return _preview(request, "DLL", request.target_handles, plan_extension_length)


def _validate(
    alias: str,
    request: Any,
    expected: tuple[DimensionSnapshot, ...],
    approval_fingerprint: str,
) -> tuple[Any, dict[str, Any]]:
    if approval_fingerprint != _fingerprint(_payload(alias, request, expected)):
        raise ValueError("approval fingerprint does not match the exact dimension request")
    doc = _drawing(request.document_id)
    current, objects = _snapshots(doc, tuple(item.handle for item in expected))
    if current != expected:
        raise ValueError("dimension state no longer matches the approved plan")
    return doc, objects


def _variant(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])


def execute_live_ddt(request: LiveDdtExecuteRequest) -> LiveDimensionBatch11Result:
    doc, objects = _validate("DDT", request.request, request.expected_dimensions, request.approval_fingerprint)
    plan = plan_dimension_extension_toggle(request.request, request.expected_dimensions)
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            entity = objects[change.handle.casefold()]
            entity.ExtLine1Suppress = change.replacement_first
            entity.ExtLine2Suppress = change.replacement_second
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        entity = objects[change.handle.casefold()]
        if (bool(entity.ExtLine1Suppress), bool(entity.ExtLine2Suppress)) != (
            change.replacement_first,
            change.replacement_second,
        ):
            raise RuntimeError(f"DDT postcondition failed: {change.handle}")
    return LiveDimensionBatch11Result(
        document_name=str(doc.Name),
        command_alias="DDT",
        changed_handles=tuple(item.handle for item in plan.changes),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_dimension_batch11b_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 11B dimension operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 11B dimension operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_ddt", preview_live_ddt, preview),
        ("xicad_execute_live_ddt", execute_live_ddt, execute),
        ("xicad_preview_live_de", preview_live_de, preview),
        ("xicad_execute_live_de", execute_live_de, execute),
        ("xicad_preview_live_dg", preview_live_dg, preview),
        ("xicad_preview_live_dh", preview_live_dh, preview),
        ("xicad_preview_live_dla", preview_live_dla, preview),
        ("xicad_execute_live_dla", execute_live_dla, execute),
        ("xicad_preview_live_dll", preview_live_dll, preview),
        ("xicad_execute_live_dll", execute_live_dll, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)


def execute_live_de(request: LiveDeExecuteRequest) -> LiveDimensionBatch11Result:
    doc, objects = _validate("DE", request.request, request.expected_dimensions, request.approval_fingerprint)
    source = request.expected_dimensions[0]
    if source.kind is not DimensionKind.ALIGNED:
        raise ValueError("live DE supports AcDbAlignedDimension only")
    plan = plan_continue_dimension(request.request, request.expected_dimensions)
    previous = objects[source.handle.casefold()]
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        for spec in plan.creates:
            entity = previous.Copy()
            entity.ExtLine1Point = _variant(spec.first_extension_origin)
            entity.ExtLine2Point = _variant(spec.second_extension_origin)
            created.append(entity)
            previous = entity
    finally:
        doc.EndUndoMark()
    after = _layout_objects(doc)
    for entity, spec in zip(created, plan.creates, strict=True):
        if (
            str(entity.Handle).casefold() not in after
            or _point(entity.ExtLine1Point) != spec.first_extension_origin
            or _point(entity.ExtLine2Point) != spec.second_extension_origin
        ):
            raise RuntimeError(f"DE postcondition failed: {entity.Handle}")
    return LiveDimensionBatch11Result(
        document_name=str(doc.Name),
        command_alias="DE",
        created_handles=tuple(str(item.Handle) for item in created),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def execute_live_dla(request: LiveDlaExecuteRequest) -> LiveDimensionBatch11Result:
    doc, objects = _validate("DLA", request.request, request.expected_dimensions, request.approval_fingerprint)
    plan = plan_extension_arrange(request.request, request.expected_dimensions)
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            entity = objects[change.handle.casefold()]
            entity.ExtLine1Point = _variant(change.replacement_first)
            entity.ExtLine2Point = _variant(change.replacement_second)
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        entity = objects[change.handle.casefold()]
        if (
            _point(entity.ExtLine1Point) != change.replacement_first
            or _point(entity.ExtLine2Point) != change.replacement_second
        ):
            raise RuntimeError(f"DLA postcondition failed: {change.handle}")
    return LiveDimensionBatch11Result(
        document_name=str(doc.Name),
        command_alias="DLA",
        changed_handles=tuple(item.handle for item in plan.changes),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def execute_live_dll(request: LiveDllExecuteRequest) -> LiveDimensionBatch11Result:
    if request.request.target is not ExtensionLineTarget.BOTH:
        raise ValueError("live DLL requires BOTH")
    doc, objects = _validate("DLL", request.request, request.expected_dimensions, request.approval_fingerprint)
    plan = plan_extension_length(request.request, request.expected_dimensions)
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            if abs(change.replacement_first - change.replacement_second) > 1e-9:
                raise ValueError("ActiveX shared extension length cannot represent unequal values")
            objects[change.handle.casefold()].ExtensionLineExtend = change.replacement_first
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        if abs(float(objects[change.handle.casefold()].ExtensionLineExtend) - change.replacement_first) > 1e-9:
            raise RuntimeError(f"DLL postcondition failed: {change.handle}")
    return LiveDimensionBatch11Result(
        document_name=str(doc.Name),
        command_alias="DLL",
        changed_handles=tuple(item.handle for item in plan.changes),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )
