from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from math import radians
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch5 import TextEntitySnapshot
from .headless_core_batch8 import (
    ContainerSnapshot,
    DynamicTitleRequest,
    EqualSpacingTextRequest,
    ShadowRepresentation,
    StyleMergeRequest,
    TextCenterRequest,
    TextShadowRequest,
    plan_dynamic_title,
    plan_equal_spacing_text,
    plan_style_merge,
    plan_text_center,
    plan_text_shadow,
)
from .live_text_batch7b import _drawing, _layout_entities, _snapshots, _variant_point


class LiveTextCenterCommand(StrEnum):
    TO = "TO"
    TOA = "TOA"


class LiveTextCenterExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    command_alias: LiveTextCenterCommand
    request: TextCenterRequest
    expected_entities: tuple[TextEntitySnapshot, ...]
    expected_containers: tuple[ContainerSnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveTextShadowExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: TextShadowRequest
    expected_entities: tuple[TextEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveStyleMergeExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: StyleMergeRequest
    expected_entities: tuple[TextEntitySnapshot, ...]
    expected_style_names: tuple[str, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveDynamicTitleExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: DynamicTitleRequest
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveEqualSpacingExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: EqualSpacingTextRequest
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch8bResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...] = ()
    created_handles: tuple[str, ...] = ()
    removed_style_names: tuple[str, ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _require_preview(request: Any) -> None:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")


def _require_named(collection: Any, name: str, kind: str) -> Any:
    try:
        return collection.Item(name)
    except Exception as exc:
        raise ValueError(f"{kind} not found: {name}") from exc


def _container(doc: Any, handle: str) -> ContainerSnapshot:
    found = _layout_entities(doc).get(handle.casefold())
    if found is None:
        raise ValueError(f"container not found: {handle}")
    entity, _space = found
    try:
        minimum, maximum = entity.GetBoundingBox()
    except Exception as exc:
        raise ValueError(f"container has no usable bounding box: {handle}") from exc
    low = tuple(float(value) for value in minimum)
    high = tuple(float(value) for value in maximum)
    width, height = high[0] - low[0], high[1] - low[1]
    if width <= 0 or height <= 0:
        raise ValueError(f"container bounding box is degenerate: {handle}")
    return ContainerSnapshot(
        handle=str(entity.Handle),
        center={"x": (low[0] + high[0]) / 2, "y": (low[1] + high[1]) / 2, "z": (low[2] + high[2]) / 2},
        width=width,
        height=height,
    )


def _center_payload(
    command_alias: LiveTextCenterCommand,
    request: TextCenterRequest,
    entities: tuple[TextEntitySnapshot, ...],
    containers: tuple[ContainerSnapshot, ...],
) -> dict[str, Any]:
    return {
        "command_alias": command_alias.value,
        "request": request.model_dump(mode="json"),
        "expected_entities": [item.model_dump(mode="json") for item in entities],
        "expected_containers": [item.model_dump(mode="json") for item in containers],
    }


def _preview_center(request: TextCenterRequest, command: LiveTextCenterCommand) -> dict[str, Any]:
    _require_preview(request)
    doc = _drawing(request.document_id)
    handles = tuple(pair.text_handle for pair in request.pairs)
    entities, _objects = _snapshots(doc, handles)
    container_handles = tuple(dict.fromkeys(pair.container_handle.casefold() for pair in request.pairs))
    first_names = {pair.container_handle.casefold(): pair.container_handle for pair in request.pairs}
    containers = tuple(_container(doc, first_names[handle]) for handle in container_handles)
    plan = plan_text_center(request, entities, containers, alias=command.value)
    payload = _center_payload(command, request, entities, containers)
    return {
        **payload,
        "move_count": len(plan.moves),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
    }


def preview_live_to(request: TextCenterRequest) -> dict[str, Any]:
    return _preview_center(request, LiveTextCenterCommand.TO)


def preview_live_toa(request: TextCenterRequest) -> dict[str, Any]:
    return _preview_center(request, LiveTextCenterCommand.TOA)


def execute_live_text_center(
    request: LiveTextCenterExecuteRequest,
    *,
    allowed_alias: LiveTextCenterCommand,
) -> LiveBatch8bResult:
    if request.command_alias is not allowed_alias:
        raise ValueError(f"this tool only executes {allowed_alias}")
    payload = _center_payload(
        request.command_alias,
        request.request,
        request.expected_entities,
        request.expected_containers,
    )
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact text-center request")
    doc = _drawing(request.request.document_id)
    current, objects = _snapshots(doc, tuple(item.handle for item in request.expected_entities))
    containers = tuple(_container(doc, item.handle) for item in request.expected_containers)
    if current != request.expected_entities or containers != request.expected_containers:
        raise ValueError("text or container state no longer matches the approved plan")
    plan = plan_text_center(request.request, current, containers, alias=request.command_alias.value)
    doc.StartUndoMark()
    try:
        for move in plan.moves:
            objects[move.handle.casefold()].InsertionPoint = _variant_point(move.to_point)
    finally:
        doc.EndUndoMark()
    for move in plan.moves:
        actual = tuple(float(value) for value in objects[move.handle.casefold()].InsertionPoint)
        expected = (move.to_point.x, move.to_point.y, move.to_point.z)
        if any(abs(a - b) > 1e-8 for a, b in zip(actual, expected, strict=True)):
            raise RuntimeError(f"{request.command_alias} position postcondition failed: {move.handle}")
    return LiveBatch8bResult(
        document_name=str(doc.Name),
        command_alias=request.command_alias,
        changed_handles=tuple(move.handle for move in plan.moves),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def execute_live_to(request: LiveTextCenterExecuteRequest) -> LiveBatch8bResult:
    return execute_live_text_center(request, allowed_alias=LiveTextCenterCommand.TO)


def execute_live_toa(request: LiveTextCenterExecuteRequest) -> LiveBatch8bResult:
    return execute_live_text_center(request, allowed_alias=LiveTextCenterCommand.TOA)


def _entity_payload(request: Any, entities: tuple[TextEntitySnapshot, ...]) -> dict[str, Any]:
    return {
        "request": request.model_dump(mode="json"),
        "expected_entities": [item.model_dump(mode="json") for item in entities],
    }


def preview_live_tsh(request: TextShadowRequest) -> dict[str, Any]:
    _require_preview(request)
    if request.representation is not ShadowRepresentation.TEXT_COPY:
        raise ValueError("live TSH supports text_copy only; solid outline lacks deterministic COM geometry")
    doc = _drawing(request.document_id)
    _require_named(doc.Layers, request.layer, "layer")
    entities, _objects = _snapshots(doc, request.target_handles)
    plan = plan_text_shadow(request, entities)
    payload = _entity_payload(request, entities)
    return {
        **payload,
        "command_alias": plan.command_alias,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
    }


def execute_live_tsh(request: LiveTextShadowExecuteRequest) -> LiveBatch8bResult:
    if request.request.representation is not ShadowRepresentation.TEXT_COPY:
        raise ValueError("live TSH supports text_copy only")
    payload = _entity_payload(request.request, request.expected_entities)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact TSH request")
    doc = _drawing(request.request.document_id)
    _require_named(doc.Layers, request.request.layer, "layer")
    current, objects = _snapshots(doc, tuple(item.handle for item in request.expected_entities))
    if current != request.expected_entities:
        raise ValueError("TSH source state no longer matches the approved plan")
    plan = plan_text_shadow(request.request, current)
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        for shadow in plan.shadows:
            source = objects[shadow.source_handle.casefold()]
            copied = source.Copy()
            copied.InsertionPoint = _variant_point(shadow.insertion_point)
            copied.Layer = shadow.layer
            copied.Color = shadow.color_index
            created.append(copied)
    finally:
        doc.EndUndoMark()
    after = _layout_entities(doc)
    for copied, shadow in zip(created, plan.shadows, strict=True):
        if (
            str(copied.Handle).casefold() not in after
            or str(copied.Layer) != shadow.layer
            or int(copied.Color) != shadow.color_index
        ):
            raise RuntimeError(f"TSH postcondition failed: {copied.Handle}")
    return LiveBatch8bResult(
        document_name=str(doc.Name),
        command_alias="TSH",
        created_handles=tuple(str(item.Handle) for item in created),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def _all_text_snapshots(doc: Any) -> tuple[TextEntitySnapshot, ...]:
    result: list[TextEntitySnapshot] = []
    for handle in sorted(_layout_entities(doc)):
        try:
            snapshots, _objects = _snapshots(doc, (handle,))
        except ValueError:
            continue
        result.extend(snapshots)
    return tuple(result)


def _style_names(doc: Any) -> tuple[str, ...]:
    return tuple(sorted((str(style.Name) for style in doc.TextStyles), key=str.casefold))


def _style_payload(
    request: StyleMergeRequest,
    entities: tuple[TextEntitySnapshot, ...],
    style_names: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "request": request.model_dump(mode="json"),
        "expected_entities": [item.model_dump(mode="json") for item in entities],
        "expected_style_names": style_names,
    }


def preview_live_tsm(request: StyleMergeRequest) -> dict[str, Any]:
    _require_preview(request)
    if request.remove_source_styles:
        raise ValueError("live TSM cannot safely prove non-text references before deleting source styles")
    doc = _drawing(request.document_id)
    _require_named(doc.TextStyles, request.target_style, "target text style")
    for name in request.source_styles:
        _require_named(doc.TextStyles, name, "source text style")
    entities = _all_text_snapshots(doc)
    names = _style_names(doc)
    plan = plan_style_merge(request, entities)
    payload = _style_payload(request, entities, names)
    return {
        **payload,
        "command_alias": plan.command_alias,
        "change_count": len(plan.entity_style_changes),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(plan.entity_style_changes),
    }


def execute_live_tsm(request: LiveStyleMergeExecuteRequest) -> LiveBatch8bResult:
    if request.request.remove_source_styles:
        raise ValueError("live TSM does not delete source style records")
    payload = _style_payload(request.request, request.expected_entities, request.expected_style_names)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact TSM request")
    doc = _drawing(request.request.document_id)
    entities = _all_text_snapshots(doc)
    names = _style_names(doc)
    if entities != request.expected_entities or names != request.expected_style_names:
        raise ValueError("text/style inventory no longer matches the approved TSM plan")
    plan = plan_style_merge(request.request, entities)
    _current, objects = _snapshots(doc, tuple(plan.entity_style_changes))
    changed = tuple(plan.entity_style_changes)
    if changed:
        doc.StartUndoMark()
        try:
            for handle, target in plan.entity_style_changes.items():
                objects[handle.casefold()].StyleName = target
        finally:
            doc.EndUndoMark()
    for handle, target in plan.entity_style_changes.items():
        if str(objects[handle.casefold()].StyleName) != target:
            raise RuntimeError(f"TSM style postcondition failed: {handle}")
    return LiveBatch8bResult(
        document_name=str(doc.Name),
        command_alias="TSM",
        changed_handles=changed,
        undo_mark_opened=bool(changed),
        undo_mark_closed=bool(changed),
        postcondition_verified=True,
    )


def _create_payload(request: Any) -> dict[str, Any]:
    return {"request": request.model_dump(mode="json")}


def _preview_create(request: Any, planner: Any) -> dict[str, Any]:
    _require_preview(request)
    doc = _drawing(request.document_id)
    _require_named(doc.Layers, request.layer, "layer")
    _require_named(doc.TextStyles, request.text_style, "text style")
    plan = planner(request)
    payload = _create_payload(request)
    return {
        **payload,
        "command_alias": plan.command_alias,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
    }


def preview_live_dat(request: DynamicTitleRequest) -> dict[str, Any]:
    return _preview_create(request, plan_dynamic_title)


def preview_live_ltx(request: EqualSpacingTextRequest) -> dict[str, Any]:
    return _preview_create(request, plan_equal_spacing_text)


def _create_text(doc: Any, spec: Any, *, text: str | None = None) -> Any:
    entity = doc.ModelSpace.AddText(
        text if text is not None else spec.text, _variant_point(spec.insertion_point), spec.text_height
    )
    entity.Layer = spec.layer
    entity.StyleName = spec.text_style
    entity.Rotation = radians(spec.rotation_degrees)
    return entity


def execute_live_dat(request: LiveDynamicTitleExecuteRequest) -> LiveBatch8bResult:
    payload = _create_payload(request.request)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact DAT request")
    doc = _drawing(request.request.document_id)
    _require_named(doc.Layers, request.request.layer, "layer")
    _require_named(doc.TextStyles, request.request.text_style, "text style")
    plan = plan_dynamic_title(request.request)
    doc.StartUndoMark()
    try:
        entity = _create_text(doc, plan.preview, text=plan.field_expression)
    finally:
        doc.EndUndoMark()
    if str(entity.TextString) != plan.field_expression or str(entity.Handle).casefold() not in _layout_entities(doc):
        raise RuntimeError("DAT field-text postcondition failed")
    return LiveBatch8bResult(
        document_name=str(doc.Name),
        command_alias="DAT",
        created_handles=(str(entity.Handle),),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def execute_live_ltx(request: LiveEqualSpacingExecuteRequest) -> LiveBatch8bResult:
    payload = _create_payload(request.request)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact LTX request")
    doc = _drawing(request.request.document_id)
    _require_named(doc.Layers, request.request.layer, "layer")
    _require_named(doc.TextStyles, request.request.text_style, "text style")
    plan = plan_equal_spacing_text(request.request)
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        created.extend(_create_text(doc, spec) for spec in plan.creates)
    finally:
        doc.EndUndoMark()
    after = _layout_entities(doc)
    for entity, spec in zip(created, plan.creates, strict=True):
        if str(entity.Handle).casefold() not in after or str(entity.TextString) != spec.text:
            raise RuntimeError(f"LTX postcondition failed: {entity.Handle}")
    return LiveBatch8bResult(
        document_name=str(doc.Name),
        command_alias="LTX",
        created_handles=tuple(str(item.Handle) for item in created),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_text_batch8b_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 8B text operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 8B text operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_to", preview_live_to, preview),
        ("xicad_execute_live_to", execute_live_to, execute),
        ("xicad_preview_live_toa", preview_live_toa, preview),
        ("xicad_execute_live_toa", execute_live_toa, execute),
        ("xicad_preview_live_tsh", preview_live_tsh, preview),
        ("xicad_execute_live_tsh", execute_live_tsh, execute),
        ("xicad_preview_live_tsm", preview_live_tsm, preview),
        ("xicad_execute_live_tsm", execute_live_tsm, execute),
        ("xicad_preview_live_dat", preview_live_dat, preview),
        ("xicad_execute_live_dat", execute_live_dat, execute),
        ("xicad_preview_live_ltx", preview_live_ltx, preview),
        ("xicad_execute_live_ltx", execute_live_ltx, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
