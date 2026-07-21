from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from math import degrees
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch5 import DrawingSpace, TextEntityKind, TextEntitySnapshot
from .headless_core_batch7 import (
    SequentialEditRequest,
    StyleScope,
    TextSplitRequest,
    TextStackRequest,
    TextStyleRequest,
    TextSwapRequest,
    TextWidthRequest,
    plan_sequential_edit,
    plan_text_split,
    plan_text_stack,
    plan_text_style,
    plan_text_swap,
    plan_text_width,
)


class LiveTseExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: SequentialEditRequest
    expected_entities: tuple[TextEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveTsoExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: TextStackRequest
    expected_entities: tuple[TextEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveTspExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: TextSplitRequest
    expected_entities: tuple[TextEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveTstExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: TextStyleRequest
    expected_entities: tuple[TextEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveTswExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: TextSwapRequest
    expected_entities: tuple[TextEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveTwExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: TextWidthRequest
    expected_entities: tuple[TextEntitySnapshot, ...]
    expected_width_factors: tuple[float, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch7bResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...]
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
    doc = matches[0]
    doc.Activate()
    return doc


def _layout_entities(doc: Any) -> dict[str, tuple[Any, DrawingSpace]]:
    result: dict[str, tuple[Any, DrawingSpace]] = {}
    for block in doc.Blocks:
        if not bool(block.IsLayout):
            continue
        space = DrawingSpace.MODEL if str(block.Name).casefold() == "*model_space" else DrawingSpace.PAPER
        for entity in block:
            result[str(entity.Handle).casefold()] = (entity, space)
    return result


_KINDS = {
    "acdbtext": TextEntityKind.TEXT,
    "acdbmtext": TextEntityKind.MTEXT,
    "acdbattribute": TextEntityKind.ATTRIB,
    "acdbattributedefinition": TextEntityKind.ATTDEF,
}


def _snapshot(doc: Any, handle: str) -> tuple[TextEntitySnapshot, Any]:
    found = _layout_entities(doc).get(handle.casefold())
    if found is None:
        raise ValueError(f"text entity not found: {handle}")
    entity, space = found
    object_name = str(entity.ObjectName).casefold()
    kind = _KINDS.get(object_name)
    if kind is None:
        raise ValueError(f"unsupported live text entity type for {handle}: {entity.ObjectName}")
    layer = str(entity.Layer)
    layer_record = doc.Layers.Item(layer)
    point = tuple(float(value) for value in entity.InsertionPoint)
    height = float(entity.TextHeight if kind is TextEntityKind.MTEXT else entity.Height)
    return (
        TextEntitySnapshot(
            handle=str(entity.Handle),
            text=str(entity.TextString),
            kind=kind,
            layer=layer,
            text_style=str(entity.StyleName),
            text_height=height,
            insertion_point=Point3D(x=point[0], y=point[1], z=point[2]),
            rotation_degrees=degrees(float(entity.Rotation)),
            space=space,
            locked_layer=bool(layer_record.Lock),
            is_xref="|" in layer,
        ),
        entity,
    )


def _snapshots(doc: Any, handles: tuple[str, ...]) -> tuple[tuple[TextEntitySnapshot, ...], dict[str, Any]]:
    snapshots: list[TextEntitySnapshot] = []
    objects: dict[str, Any] = {}
    for handle in handles:
        snapshot, entity = _snapshot(doc, handle)
        snapshots.append(snapshot)
        objects[snapshot.handle.casefold()] = entity
    return tuple(snapshots), objects


def _preview(
    request: Any,
    handles: tuple[str, ...],
    planner: Callable[[Any, tuple[TextEntitySnapshot, ...]], Any],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    snapshots, _objects = _snapshots(doc, handles)
    plan = planner(request, snapshots)
    payload = {
        "request": request.model_dump(mode="json"),
        "expected_entities": [item.model_dump(mode="json") for item in snapshots],
        **(extra or {}),
    }
    return {
        **payload,
        "command_alias": plan.command_alias,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
    }


def preview_live_tse(request: SequentialEditRequest) -> dict[str, Any]:
    return _preview(request, tuple(edit.handle for edit in request.edits), plan_sequential_edit)


def preview_live_tso(request: TextStackRequest) -> dict[str, Any]:
    return _preview(request, request.target_handles, plan_text_stack)


def preview_live_tsp(request: TextSplitRequest) -> dict[str, Any]:
    result = _preview(request, request.target_handles, plan_text_split)
    if any(item["space"] != DrawingSpace.MODEL.value for item in result["expected_entities"]):
        raise ValueError("live TSP currently supports model-space sources only")
    return result


def preview_live_tst(request: TextStyleRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    if request.scope is not StyleScope.SELECTED:
        raise ValueError("live TST requires selected scope")
    doc = _drawing(request.document_id)
    try:
        doc.TextStyles.Item(request.target_style)
    except Exception as exc:
        raise ValueError(f"text style not found: {request.target_style}") from exc
    snapshots, _objects = _snapshots(doc, request.target_handles)
    plan = plan_text_style(request, snapshots, alias="TST")
    payload = {
        "request": request.model_dump(mode="json"),
        "expected_entities": [item.model_dump(mode="json") for item in snapshots],
    }
    return {
        **payload,
        "command_alias": plan.command_alias,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
    }


def preview_live_tsw(request: TextSwapRequest) -> dict[str, Any]:
    return _preview(request, (request.first_handle, request.second_handle), plan_text_swap)


def preview_live_tw(request: TextWidthRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    snapshots, objects = _snapshots(doc, request.target_handles)
    plan = plan_text_width(request, snapshots)
    unsupported = [
        s.handle for s in snapshots if s.kind not in {TextEntityKind.TEXT, TextEntityKind.ATTRIB, TextEntityKind.ATTDEF}
    ]
    if unsupported:
        raise ValueError(f"TW WidthFactor is unsupported for: {unsupported}")
    factors = tuple(float(objects[item.handle.casefold()].ScaleFactor) for item in snapshots)
    payload = {
        "request": request.model_dump(mode="json"),
        "expected_entities": [item.model_dump(mode="json") for item in snapshots],
        "expected_width_factors": factors,
    }
    return {
        **payload,
        "command_alias": plan.command_alias,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
    }


def _validate_execution(
    request: Any,
    expected: tuple[TextEntitySnapshot, ...],
    approval_fingerprint: str,
    *,
    extra: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    payload = {
        "request": request.model_dump(mode="json"),
        "expected_entities": [item.model_dump(mode="json") for item in expected],
        **(extra or {}),
    }
    if approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact text request")
    doc = _drawing(request.document_id)
    current, objects = _snapshots(doc, tuple(item.handle for item in expected))
    if current != expected:
        raise ValueError("text entity state no longer matches the approved plan")
    return doc, objects


def _finish(
    doc: Any,
    alias: str,
    changed: tuple[str, ...],
    created: tuple[str, ...] = (),
    erased: tuple[str, ...] = (),
) -> LiveBatch7bResult:
    remaining = _layout_entities(doc)
    if not all(handle.casefold() in remaining for handle in (*changed, *created)):
        raise RuntimeError(f"{alias} created/changed entity postcondition failed")
    if not all(handle.casefold() not in remaining for handle in erased):
        raise RuntimeError(f"{alias} erased entity postcondition failed")
    return LiveBatch7bResult(
        document_name=str(doc.Name),
        command_alias=alias,
        changed_handles=changed,
        created_handles=created,
        erased_handles=erased,
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def execute_live_tse(request: LiveTseExecuteRequest) -> LiveBatch7bResult:
    doc, objects = _validate_execution(request.request, request.expected_entities, request.approval_fingerprint)
    plan = plan_sequential_edit(request.request, request.expected_entities)
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            objects[change.handle.casefold()].TextString = change.replacement_text
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        if str(objects[change.handle.casefold()].TextString) != change.replacement_text:
            raise RuntimeError(f"TSE text postcondition failed: {change.handle}")
    return _finish(doc, "TSE", tuple(change.handle for change in plan.changes))


def execute_live_tso(request: LiveTsoExecuteRequest) -> LiveBatch7bResult:
    doc, objects = _validate_execution(request.request, request.expected_entities, request.approval_fingerprint)
    plan = plan_text_stack(request.request, request.expected_entities)
    doc.StartUndoMark()
    try:
        for move in plan.moves:
            objects[move.handle.casefold()].InsertionPoint = _variant_point(move.to_point)
    finally:
        doc.EndUndoMark()
    for move in plan.moves:
        actual = tuple(float(value) for value in objects[move.handle.casefold()].InsertionPoint)
        if any(
            abs(a - b) > 1e-8 for a, b in zip(actual, (move.to_point.x, move.to_point.y, move.to_point.z), strict=True)
        ):
            raise RuntimeError(f"TSO position postcondition failed: {move.handle}")
    return _finish(doc, "TSO", tuple(move.handle for move in plan.moves))


def _variant_point(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])


def execute_live_tsp(request: LiveTspExecuteRequest) -> LiveBatch7bResult:
    if any(item.space is not DrawingSpace.MODEL for item in request.expected_entities):
        raise ValueError("live TSP currently supports model-space sources only")
    doc, objects = _validate_execution(request.request, request.expected_entities, request.approval_fingerprint)
    plan = plan_text_split(request.request, request.expected_entities)
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        for piece in plan.pieces:
            entity = doc.ModelSpace.AddText(piece.text, _variant_point(piece.insertion_point), piece.text_height)
            entity.Layer = piece.layer
            entity.StyleName = piece.text_style
            created.append(entity)
        for handle in plan.erase_source_handles:
            objects[handle.casefold()].Delete()
    finally:
        doc.EndUndoMark()
    for entity, piece in zip(created, plan.pieces, strict=True):
        if str(entity.TextString) != piece.text:
            raise RuntimeError(f"TSP text postcondition failed: {entity.Handle}")
    return _finish(
        doc,
        "TSP",
        (),
        tuple(str(entity.Handle) for entity in created),
        plan.erase_source_handles,
    )


def execute_live_tst(request: LiveTstExecuteRequest) -> LiveBatch7bResult:
    if request.request.scope is not StyleScope.SELECTED:
        raise ValueError("live TST requires selected scope")
    doc, objects = _validate_execution(request.request, request.expected_entities, request.approval_fingerprint)
    try:
        doc.TextStyles.Item(request.request.target_style)
    except Exception as exc:
        raise ValueError(f"text style not found: {request.request.target_style}") from exc
    plan = plan_text_style(request.request, request.expected_entities, alias="TST")
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            objects[change.handle.casefold()].StyleName = change.replacement_style
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        if str(objects[change.handle.casefold()].StyleName) != change.replacement_style:
            raise RuntimeError(f"TST style postcondition failed: {change.handle}")
    return _finish(doc, "TST", tuple(change.handle for change in plan.changes))


def execute_live_tsw(request: LiveTswExecuteRequest) -> LiveBatch7bResult:
    doc, objects = _validate_execution(request.request, request.expected_entities, request.approval_fingerprint)
    plan = plan_text_swap(request.request, request.expected_entities)
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            objects[change.handle.casefold()].TextString = change.replacement_text
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        if str(objects[change.handle.casefold()].TextString) != change.replacement_text:
            raise RuntimeError(f"TSW text postcondition failed: {change.handle}")
    return _finish(doc, "TSW", tuple(change.handle for change in plan.changes))


def execute_live_tw(request: LiveTwExecuteRequest) -> LiveBatch7bResult:
    extra = {"expected_width_factors": request.expected_width_factors}
    doc, objects = _validate_execution(
        request.request,
        request.expected_entities,
        request.approval_fingerprint,
        extra=extra,
    )
    current = tuple(float(objects[item.handle.casefold()].ScaleFactor) for item in request.expected_entities)
    if current != request.expected_width_factors:
        raise ValueError("text width factors no longer match the approved plan")
    plan = plan_text_width(request.request, request.expected_entities)
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            objects[change.handle.casefold()].ScaleFactor = change.width_factor
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        if abs(float(objects[change.handle.casefold()].ScaleFactor) - change.width_factor) > 1e-9:
            raise RuntimeError(f"TW width postcondition failed: {change.handle}")
    return _finish(doc, "TW", tuple(change.handle for change in plan.changes))


def register_live_text_batch7b_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 7B text operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 7B text operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_tse", preview_live_tse, preview),
        ("xicad_execute_live_tse", execute_live_tse, execute),
        ("xicad_preview_live_tso", preview_live_tso, preview),
        ("xicad_execute_live_tso", execute_live_tso, execute),
        ("xicad_preview_live_tsp", preview_live_tsp, preview),
        ("xicad_execute_live_tsp", execute_live_tsp, execute),
        ("xicad_preview_live_tst", preview_live_tst, preview),
        ("xicad_execute_live_tst", execute_live_tst, execute),
        ("xicad_preview_live_tsw", preview_live_tsw, preview),
        ("xicad_execute_live_tsw", execute_live_tsw, execute),
        ("xicad_preview_live_tw", preview_live_tw, preview),
        ("xicad_execute_live_tw", execute_live_tw, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
