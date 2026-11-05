from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .maintenance_cores import (
    AllPointDeleteRequest,
    DrawingSpace,
    EntityRef,
    LayerFilterDeleteRequest,
    LayerFilterRef,
    plan_all_point_delete,
    plan_layer_filter_delete,
)


class LiveApdPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str = Field(min_length=1)
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)


class LiveApdExecuteRequest(LiveApdPreviewRequest):
    expected_entities: tuple[EntityRef, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveApdResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str
    matched_handles: tuple[str, ...]
    deleted_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


class LiveLayerFilterCommand(StrEnum):
    LFD = "LFD"
    LPD = "LPD"


class LiveLayerFilterPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str = Field(min_length=1)
    command_alias: LiveLayerFilterCommand
    delete_all_user_filters: bool = True
    include_names: tuple[str, ...] = ()
    preserve_names: tuple[str, ...] = ()


class LiveLayerFilterExecuteRequest(LiveLayerFilterPreviewRequest):
    expected_filter_names: tuple[str, ...]
    expected_selected_names: tuple[str, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LayerFilterDeleteEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    absent: bool


class LiveLayerFilterResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str
    command_alias: LiveLayerFilterCommand
    deleted_names: tuple[str, ...]
    evidence: tuple[LayerFilterDeleteEvidence, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _drawing(document_name: str) -> Any:
    # Keep pywin32 optional for contract imports and CAD-free planning.
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == document_name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {document_name!r}, found {len(matches)}")
    doc = matches[0]
    doc.Activate()
    return doc


def _layout_blocks(doc: Any, spaces: tuple[DrawingSpace, ...]) -> tuple[tuple[DrawingSpace, Any], ...]:
    selected = set(spaces)
    result: list[tuple[DrawingSpace, Any]] = []
    for block in doc.Blocks:
        if not bool(block.IsLayout):
            continue
        name = str(block.Name).casefold()
        space = DrawingSpace.MODEL if name == "*model_space" else DrawingSpace.PAPER
        if space in selected:
            result.append((space, block))
    return tuple(result)


def _point_entities(doc: Any, spaces: tuple[DrawingSpace, ...]) -> tuple[tuple[EntityRef, Any], ...]:
    found: list[tuple[EntityRef, Any]] = []
    for space, block in _layout_blocks(doc, spaces):
        for entity in block:
            if str(entity.ObjectName).casefold() == "acdbpoint":
                found.append(
                    (
                        EntityRef(handle=str(entity.Handle), dxf_type="POINT", space=space),
                        entity,
                    )
                )
    return tuple(sorted(found, key=lambda item: item[0].handle.casefold()))


def preview_live_apd(request: LiveApdPreviewRequest) -> dict[str, Any]:
    # Reuse the structured contract to validate the requested spaces.
    plan_all_point_delete(
        AllPointDeleteRequest(document_id=request.document_name, spaces=request.spaces)
    )
    doc = _drawing(request.document_name)
    entities = tuple(ref for ref, _entity in _point_entities(doc, request.spaces))
    payload = {
        **request.model_dump(mode="json"),
        "expected_entities": [entity.model_dump(mode="json") for entity in entities],
    }
    return {
        **payload,
        "command_alias": "APD",
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(entities),
    }


def execute_live_apd(request: LiveApdExecuteRequest) -> LiveApdResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact APD request")
    doc = _drawing(request.document_name)
    current = _point_entities(doc, request.spaces)
    current_refs = tuple(ref for ref, _entity in current)
    if current_refs != request.expected_entities:
        raise ValueError("APD point inventory no longer matches the approved plan")

    opened = False
    closed = False
    if current:
        try:
            doc.StartUndoMark()
            opened = True
            for _ref, entity in current:
                entity.Delete()
        finally:
            if opened:
                doc.EndUndoMark()
                closed = True

    remaining = {ref.handle.casefold() for ref, _entity in _point_entities(doc, request.spaces)}
    handles = tuple(ref.handle for ref in current_refs)
    verified = all(handle.casefold() not in remaining for handle in handles)
    if not verified:
        raise RuntimeError("APD postcondition failed")
    return LiveApdResult(
        document_name=str(doc.Name),
        matched_handles=handles,
        deleted_handles=handles,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
        postcondition_verified=True,
    )


def _layer_filter_dictionary(doc: Any) -> Any | None:
    try:
        return doc.Dictionaries.Item("ACAD_LAYERFILTERS")
    except Exception:
        return None


def _filter_entries(doc: Any) -> tuple[tuple[LayerFilterRef, Any], ...]:
    dictionary = _layer_filter_dictionary(doc)
    if dictionary is None:
        return ()
    entries: list[tuple[LayerFilterRef, Any]] = []
    for index in range(int(dictionary.Count)):
        item = dictionary.Item(index)
        name = str(dictionary.GetName(item))
        entries.append((LayerFilterRef(name=name, system=False), item))
    return tuple(sorted(entries, key=lambda entry: entry[0].name.casefold()))


def _filter_plan(request: LiveLayerFilterPreviewRequest, doc: Any):
    refs = tuple(ref for ref, _item in _filter_entries(doc))
    return refs, plan_layer_filter_delete(
        LayerFilterDeleteRequest(
            document_id=str(doc.Name),
            aliases=(request.command_alias.value,),
            delete_all_user_filters=request.delete_all_user_filters,
            include_names=request.include_names,
            preserve_names=request.preserve_names,
        ),
        refs,
    )


def preview_live_layer_filter_delete(request: LiveLayerFilterPreviewRequest) -> dict[str, Any]:
    doc = _drawing(request.document_name)
    refs, plan = _filter_plan(request, doc)
    payload = {
        **request.model_dump(mode="json"),
        "expected_filter_names": [ref.name for ref in refs],
        "expected_selected_names": list(plan.selected_names),
    }
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(plan.selected_names),
    }


def execute_live_layer_filter_delete(
    request: LiveLayerFilterExecuteRequest,
    *,
    allowed_alias: LiveLayerFilterCommand | None = None,
) -> LiveLayerFilterResult:
    if allowed_alias is not None and request.command_alias is not allowed_alias:
        raise ValueError(f"this tool only executes {allowed_alias}")
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact layer-filter request")

    doc = _drawing(request.document_name)
    refs, plan = _filter_plan(request, doc)
    current_names = tuple(ref.name for ref in refs)
    if current_names != request.expected_filter_names or plan.selected_names != request.expected_selected_names:
        raise ValueError("layer-filter inventory no longer matches the approved plan")

    entries = {ref.name.casefold(): item for ref, item in _filter_entries(doc)}
    opened = False
    closed = False
    if plan.selected_names:
        try:
            doc.StartUndoMark()
            opened = True
            for name in plan.selected_names:
                entries[name.casefold()].Delete()
        finally:
            if opened:
                doc.EndUndoMark()
                closed = True

    remaining = {ref.name.casefold() for ref, _item in _filter_entries(doc)}
    evidence = tuple(
        LayerFilterDeleteEvidence(name=name, absent=name.casefold() not in remaining)
        for name in plan.selected_names
    )
    if not all(item.absent for item in evidence):
        raise RuntimeError("layer-filter deletion postcondition failed")
    return LiveLayerFilterResult(
        document_name=str(doc.Name),
        command_alias=request.command_alias,
        deleted_names=plan.selected_names,
        evidence=evidence,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
        postcondition_verified=True,
    )


def execute_live_lfd(request: LiveLayerFilterExecuteRequest) -> LiveLayerFilterResult:
    return execute_live_layer_filter_delete(request, allowed_alias=LiveLayerFilterCommand.LFD)


def execute_live_lpd(request: LiveLayerFilterExecuteRequest) -> LiveLayerFilterResult:
    return execute_live_layer_filter_delete(request, allowed_alias=LiveLayerFilterCommand.LPD)


def register_live_maintenance_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD maintenance",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD maintenance",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_apd", preview_live_apd, preview, "Preview APD point deletion."),
        ("xicad_execute_live_apd", execute_live_apd, execute, "Execute approved APD point deletion."),
        (
            "xicad_preview_live_layer_filter_delete",
            preview_live_layer_filter_delete,
            preview,
            "Preview LFD/LPD layer-filter deletion.",
        ),
        ("xicad_execute_live_lfd", execute_live_lfd, execute, "Execute approved LFD filter deletion."),
        ("xicad_execute_live_lpd", execute_live_lpd, execute, "Execute approved LPD filter deletion."),
    )
    for name, function, tool_annotations, description in registrations:
        mcp.tool(name=name, description=description, annotations=tool_annotations)(function)
