from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import DrawingSpace
from .headless_core_batch9 import (
    ChangeLayerRequest,
    ColorToLayerRequest,
    EntityVisibilityRequest,
    LayerEntitySnapshot,
    LayerMergeRequest,
    LayerSnapshot,
    SetCurrentLayerRequest,
    plan_change_layer,
    plan_color_to_layer,
    plan_entity_visibility,
    plan_layer_merge,
    plan_set_current_layer,
)


class LiveVisibilityCommand(StrEnum):
    ESF = "ESF"
    ESO = "ESO"


class LiveVisibilityExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    command_alias: LiveVisibilityCommand
    request: EntityVisibilityRequest
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveEwExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: SetCurrentLayerRequest
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveLamExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: LayerMergeRequest
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveLcExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ChangeLayerRequest
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveLccExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ColorToLayerRequest
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveLayerBatch9Result(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...] = ()
    changed_layers: tuple[str, ...] = ()
    removed_layers: tuple[str, ...] = ()
    current_layer: str | None = None
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


def _layers(doc: Any) -> tuple[LayerSnapshot, ...]:
    current = str(doc.ActiveLayer.Name).casefold()
    result = tuple(
        LayerSnapshot(
            name=str(layer.Name),
            color_index=int(layer.Color),
            linetype=str(layer.Linetype),
            is_on=bool(layer.LayerOn),
            is_frozen=bool(layer.Freeze),
            is_locked=bool(layer.Lock),
            is_xref="|" in str(layer.Name),
            is_current=str(layer.Name).casefold() == current,
        )
        for layer in doc.Layers
    )
    return tuple(sorted(result, key=lambda item: item.name.casefold()))


def _entities(doc: Any) -> tuple[tuple[LayerEntitySnapshot, Any], ...]:
    result: list[tuple[LayerEntitySnapshot, Any]] = []
    for block in doc.Blocks:
        is_layout = bool(block.IsLayout)
        block_name = str(block.Name)
        block_xref = bool(getattr(block, "IsXRef", False))
        if is_layout:
            space = DrawingSpace.MODEL if block_name.casefold() == "*model_space" else DrawingSpace.PAPER
        else:
            space = DrawingSpace.MODEL
        for entity in block:
            layer = str(entity.Layer)
            entity_block_name = block_name if not is_layout else None
            if str(entity.ObjectName).casefold() == "acdbblockreference":
                entity_block_name = str(getattr(entity, "EffectiveName", getattr(entity, "Name", ""))) or None
            result.append(
                (
                    LayerEntitySnapshot(
                        handle=str(entity.Handle),
                        layer=layer,
                        color_index=int(entity.Color),
                        linetype=str(entity.Linetype),
                        visible=bool(entity.Visible),
                        space=space,
                        block_owner_handle=None if is_layout else str(block.Handle),
                        block_name=entity_block_name,
                        nested=not is_layout,
                        is_xref="|" in layer or block_xref,
                    ),
                    entity,
                )
            )
    result.sort(key=lambda item: item[0].handle.casefold())
    return tuple(result)


def _inventory(doc: Any) -> tuple[tuple[LayerSnapshot, ...], tuple[LayerEntitySnapshot, ...], dict[str, Any]]:
    layers = _layers(doc)
    entity_pairs = _entities(doc)
    entities = tuple(item for item, _entity in entity_pairs)
    objects = {item.handle.casefold(): entity for item, entity in entity_pairs}
    return layers, entities, objects


def _payload(
    alias: str,
    request: Any,
    layers: tuple[LayerSnapshot, ...],
    entities: tuple[LayerEntitySnapshot, ...],
) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "request": request.model_dump(mode="json"),
        "expected_layers": [item.model_dump(mode="json") for item in layers],
        "expected_entities": [item.model_dump(mode="json") for item in entities],
    }


def _preview(request: Any, alias: str, planner: Callable[..., Any]) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    layers, entities, _objects = _inventory(doc)
    plan = planner(request, layers, entities)
    payload = _payload(alias, request, layers, entities)
    count = len(getattr(plan, "changes", getattr(plan, "entity_changes", ())))
    return {
        **payload,
        "change_count": count,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(count or getattr(plan, "prerequisite_changes", ())),
    }


def preview_live_esf(request: EntityVisibilityRequest) -> dict[str, Any]:
    return _preview(request, "ESF", lambda req, _layers, entities: plan_entity_visibility(req, entities, alias="ESF"))


def preview_live_eso(request: EntityVisibilityRequest) -> dict[str, Any]:
    return _preview(request, "ESO", lambda req, _layers, entities: plan_entity_visibility(req, entities, alias="ESO"))


def preview_live_ew(request: SetCurrentLayerRequest) -> dict[str, Any]:
    return _preview(request, "EW", plan_set_current_layer)


def preview_live_lam(request: LayerMergeRequest) -> dict[str, Any]:
    return _preview(request, "LAM", plan_layer_merge)


def preview_live_lc(request: ChangeLayerRequest) -> dict[str, Any]:
    return _preview(request, "LC", plan_change_layer)


def preview_live_lcc(request: ColorToLayerRequest) -> dict[str, Any]:
    return _preview(request, "LCC", plan_color_to_layer)


def _validate(
    alias: str,
    request: Any,
    expected_layers: tuple[LayerSnapshot, ...],
    expected_entities: tuple[LayerEntitySnapshot, ...],
    approval_fingerprint: str,
) -> tuple[Any, tuple[LayerSnapshot, ...], tuple[LayerEntitySnapshot, ...], dict[str, Any]]:
    payload = _payload(alias, request, expected_layers, expected_entities)
    if approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact layer request")
    doc = _drawing(request.document_id)
    layers, entities, objects = _inventory(doc)
    if layers != expected_layers or entities != expected_entities:
        raise ValueError("layer/entity inventory no longer matches the approved plan")
    return doc, layers, entities, objects


def _locked_layers(layers: tuple[LayerSnapshot, ...]) -> set[str]:
    return {item.name.casefold() for item in layers if item.is_locked}


def execute_live_visibility(
    request: LiveVisibilityExecuteRequest,
    *,
    allowed_alias: LiveVisibilityCommand,
) -> LiveLayerBatch9Result:
    if request.command_alias is not allowed_alias:
        raise ValueError(f"this tool only executes {allowed_alias}")
    doc, layers, entities, objects = _validate(
        request.command_alias,
        request.request,
        request.expected_layers,
        request.expected_entities,
        request.approval_fingerprint,
    )
    plan = plan_entity_visibility(request.request, entities, alias=request.command_alias.value)
    by_handle = {item.handle.casefold(): item for item in entities}
    locked = _locked_layers(layers)
    unsafe = [
        change.handle for change in plan.changes if by_handle[change.handle.casefold()].layer.casefold() in locked
    ]
    if unsafe:
        raise ValueError(f"visibility target is on a locked layer: {unsafe}")
    changed = tuple(change.handle for change in plan.changes)
    if changed:
        doc.StartUndoMark()
        try:
            for change in plan.changes:
                objects[change.handle.casefold()].Visible = change.replacement_visible
        finally:
            doc.EndUndoMark()
    for change in plan.changes:
        if bool(objects[change.handle.casefold()].Visible) != change.replacement_visible:
            raise RuntimeError(f"{request.command_alias} visibility postcondition failed: {change.handle}")
    return LiveLayerBatch9Result(
        document_name=str(doc.Name),
        command_alias=request.command_alias,
        changed_handles=changed,
        undo_mark_opened=bool(changed),
        undo_mark_closed=bool(changed),
        postcondition_verified=True,
    )


def execute_live_esf(request: LiveVisibilityExecuteRequest) -> LiveLayerBatch9Result:
    return execute_live_visibility(request, allowed_alias=LiveVisibilityCommand.ESF)


def execute_live_eso(request: LiveVisibilityExecuteRequest) -> LiveLayerBatch9Result:
    return execute_live_visibility(request, allowed_alias=LiveVisibilityCommand.ESO)


def execute_live_ew(request: LiveEwExecuteRequest) -> LiveLayerBatch9Result:
    doc, layers, entities, _objects = _validate(
        "EW", request.request, request.expected_layers, request.expected_entities, request.approval_fingerprint
    )
    plan = plan_set_current_layer(request.request, layers, entities)
    target = doc.Layers.Item(plan.replacement_current_layer)
    doc.StartUndoMark()
    try:
        if target.Lock and request.request.unlock_policy == "unlock":
            target.Lock = False
        for change in plan.prerequisite_changes:
            layer = doc.Layers.Item(change.layer)
            layer.LayerOn = change.replacement_on
            layer.Freeze = change.replacement_frozen
        doc.ActiveLayer = target
    finally:
        doc.EndUndoMark()
    if str(doc.ActiveLayer.Name).casefold() != plan.replacement_current_layer.casefold():
        raise RuntimeError("EW current-layer postcondition failed")
    return LiveLayerBatch9Result(
        document_name=str(doc.Name),
        command_alias="EW",
        changed_layers=(plan.replacement_current_layer,),
        current_layer=str(doc.ActiveLayer.Name),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def _apply_entity_changes(doc: Any, plan: Any, objects: dict[str, Any]) -> tuple[str, ...]:
    changed: list[str] = []
    for change in plan.changes if hasattr(plan, "changes") else plan.entity_changes:
        entity = objects[change.handle.casefold()]
        entity.Layer = change.replacement_layer
        entity.Color = change.replacement_color_index
        entity.Linetype = change.replacement_linetype
        changed.append(change.handle)
    return tuple(changed)


def execute_live_lam(request: LiveLamExecuteRequest) -> LiveLayerBatch9Result:
    doc, layers, entities, objects = _validate(
        "LAM", request.request, request.expected_layers, request.expected_entities, request.approval_fingerprint
    )
    plan = plan_layer_merge(request.request, layers, entities)
    doc.StartUndoMark()
    try:
        changed = _apply_entity_changes(doc, plan, objects)
        for name in plan.remove_layers:
            doc.Layers.Item(name).Delete()
    finally:
        doc.EndUndoMark()
    remaining = {item.name.casefold() for item in _layers(doc)}
    for change in plan.entity_changes:
        entity = objects[change.handle.casefold()]
        if str(entity.Layer) != change.replacement_layer or int(entity.Color) != change.replacement_color_index:
            raise RuntimeError(f"LAM entity postcondition failed: {change.handle}")
    if any(name.casefold() in remaining for name in plan.remove_layers):
        raise RuntimeError("LAM source-layer removal postcondition failed")
    return LiveLayerBatch9Result(
        document_name=str(doc.Name),
        command_alias="LAM",
        changed_handles=changed,
        removed_layers=plan.remove_layers,
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def _execute_change_layer(
    alias: str,
    request: Any,
    expected_layers: tuple[LayerSnapshot, ...],
    expected_entities: tuple[LayerEntitySnapshot, ...],
    approval_fingerprint: str,
    planner: Callable[..., Any],
) -> LiveLayerBatch9Result:
    doc, layers, entities, objects = _validate(alias, request, expected_layers, expected_entities, approval_fingerprint)
    plan = planner(request, layers, entities)
    doc.StartUndoMark()
    try:
        if plan.create_layer is not None:
            doc.Linetypes.Item(plan.create_layer.linetype)
            layer = doc.Layers.Add(plan.create_layer.name)
            layer.Color = plan.create_layer.color_index
            layer.Linetype = plan.create_layer.linetype
        changed = _apply_entity_changes(doc, plan, objects)
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        entity = objects[change.handle.casefold()]
        if (
            str(entity.Layer) != change.replacement_layer
            or int(entity.Color) != change.replacement_color_index
            or str(entity.Linetype) != change.replacement_linetype
        ):
            raise RuntimeError(f"{alias} entity postcondition failed: {change.handle}")
    changed_layers = (plan.create_layer.name,) if plan.create_layer is not None else ()
    return LiveLayerBatch9Result(
        document_name=str(doc.Name),
        command_alias=alias,
        changed_handles=changed,
        changed_layers=changed_layers,
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def execute_live_lc(request: LiveLcExecuteRequest) -> LiveLayerBatch9Result:
    return _execute_change_layer(
        "LC",
        request.request,
        request.expected_layers,
        request.expected_entities,
        request.approval_fingerprint,
        plan_change_layer,
    )


def execute_live_lcc(request: LiveLccExecuteRequest) -> LiveLayerBatch9Result:
    return _execute_change_layer(
        "LCC",
        request.request,
        request.expected_layers,
        request.expected_entities,
        request.approval_fingerprint,
        plan_color_to_layer,
    )


def register_live_layer_batch9b_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 9B layer operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 9B layer operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_esf", preview_live_esf, preview),
        ("xicad_execute_live_esf", execute_live_esf, execute),
        ("xicad_preview_live_eso", preview_live_eso, preview),
        ("xicad_execute_live_eso", execute_live_eso, execute),
        ("xicad_preview_live_ew", preview_live_ew, preview),
        ("xicad_execute_live_ew", execute_live_ew, execute),
        ("xicad_preview_live_lam", preview_live_lam, preview),
        ("xicad_execute_live_lam", execute_live_lam, execute),
        ("xicad_preview_live_lc", preview_live_lc, preview),
        ("xicad_execute_live_lc", execute_live_lc, execute),
        ("xicad_preview_live_lcc", preview_live_lcc, preview),
        ("xicad_execute_live_lcc", execute_live_lcc, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
