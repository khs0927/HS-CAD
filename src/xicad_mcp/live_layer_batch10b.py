from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch9 import LayerEntitySnapshot, LayerSnapshot
from .headless_core_batch10 import (
    ActivateLayersRequest,
    ColorLayerStateRequest,
    LayerListDestination,
    LayerListPlan,
    LayerListRequest,
    LayerPropertyRequest,
    LayerSetRequest,
    plan_activate_layers,
    plan_color_layer_state,
    plan_layer_list,
    plan_layer_property,
    plan_layer_protection,
)
from .live_layer_batch9b import _drawing, _inventory, _layers, _payload, _validate


class LiveLkExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: LayerSetRequest
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveColorStateExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    command_alias: str = Field(pattern="^(LLC|LOC)$")
    request: ColorLayerStateRequest
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveLosExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ActivateLayersRequest
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveLpExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: LayerPropertyRequest
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveLayerBatch10Result(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...] = ()
    changed_layers: tuple[str, ...] = ()
    removed_layers: tuple[str, ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


class LiveLayerListResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    plan: LayerListPlan
    production_usable: bool = True


def _preview(request: Any, alias: str, planner: Any) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    layers, entities, _objects = _inventory(doc)
    plan = planner(request, layers, entities)
    payload = _payload(alias, request, layers, entities)
    changes = getattr(plan, "changes", ())
    if not changes:
        changes = (*getattr(plan, "layer_changes", ()), *getattr(plan, "entity_changes", ()))
    return {
        **payload,
        "change_count": len(changes),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": bool(changes),
    }


def _fingerprint(payload: dict[str, Any]) -> str:
    import hashlib
    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def preview_live_lk(request: LayerSetRequest) -> dict[str, Any]:
    return _preview(
        request,
        "LK",
        lambda req, layers, entities: plan_layer_protection(req, layers, entities, alias="LK"),
    )


def _preview_color_state(request: ColorLayerStateRequest, alias: str) -> dict[str, Any]:
    if request.include_xref_layers:
        raise ValueError("live color layer-state tools do not mutate xref-dependent layers")
    return _preview(
        request,
        alias,
        lambda req, layers, entities: plan_color_layer_state(req, layers, entities, alias=alias),
    )


def preview_live_llc(request: ColorLayerStateRequest) -> dict[str, Any]:
    return _preview_color_state(request, "LLC")


def preview_live_loc(request: ColorLayerStateRequest) -> dict[str, Any]:
    return _preview_color_state(request, "LOC")


def preview_live_los(request: ActivateLayersRequest) -> dict[str, Any]:
    if request.include_xref_layers:
        raise ValueError("live LOS does not mutate xref-dependent layers")
    return _preview(request, "LOS", lambda req, layers, _entities: plan_activate_layers(req, layers))


def preview_live_lp(request: LayerPropertyRequest) -> dict[str, Any]:
    if request.patch is not None and request.patch.viewport_frozen is not None:
        raise ValueError("live LP viewport_frozen requires an explicit viewport contract")
    return _preview(request, "LP", plan_layer_property)


def read_live_lst(request: LayerListRequest) -> LiveLayerListResult:
    if request.destination is not LayerListDestination.RETURN_ONLY:
        raise ValueError("live LST currently supports return_only; drawing output lacks explicit style and sizing")
    doc = _drawing(request.document_id)
    plan = plan_layer_list(request, _layers(doc))
    return LiveLayerListResult(document_name=str(doc.Name), plan=plan)


def execute_live_lk(request: LiveLkExecuteRequest) -> LiveLayerBatch10Result:
    doc, layers, entities, _objects = _validate(
        "LK", request.request, request.expected_layers, request.expected_entities, request.approval_fingerprint
    )
    plan = plan_layer_protection(request.request, layers, entities, alias="LK")
    changed = tuple(item.layer for item in plan.changes)
    if changed:
        doc.StartUndoMark()
        try:
            for change in plan.changes:
                layer = doc.Layers.Item(change.layer)
                layer.Freeze = change.replacement_frozen
                layer.Lock = change.replacement_locked
        finally:
            doc.EndUndoMark()
    for change in plan.changes:
        layer = doc.Layers.Item(change.layer)
        if bool(layer.Freeze) != change.replacement_frozen or bool(layer.Lock) != change.replacement_locked:
            raise RuntimeError(f"LK layer postcondition failed: {change.layer}")
    return LiveLayerBatch10Result(
        document_name=str(doc.Name),
        command_alias="LK",
        changed_layers=changed,
        undo_mark_opened=bool(changed),
        undo_mark_closed=bool(changed),
        postcondition_verified=True,
    )


def _execute_color_state(
    request: LiveColorStateExecuteRequest,
    *,
    allowed_alias: str,
) -> LiveLayerBatch10Result:
    if request.command_alias != allowed_alias:
        raise ValueError(f"this tool only executes {allowed_alias}")
    if request.request.include_xref_layers:
        raise ValueError("live color layer-state tools do not mutate xref-dependent layers")
    doc, layers, entities, _objects = _validate(
        allowed_alias,
        request.request,
        request.expected_layers,
        request.expected_entities,
        request.approval_fingerprint,
    )
    plan = plan_color_layer_state(request.request, layers, entities, alias=allowed_alias)
    changed = tuple(item.layer for item in plan.changes)
    if changed:
        doc.StartUndoMark()
        try:
            for change in plan.changes:
                doc.Layers.Item(change.layer).LayerOn = change.replacement_on
        finally:
            doc.EndUndoMark()
    for change in plan.changes:
        if bool(doc.Layers.Item(change.layer).LayerOn) != change.replacement_on:
            raise RuntimeError(f"{allowed_alias} layer postcondition failed: {change.layer}")
    return LiveLayerBatch10Result(
        document_name=str(doc.Name),
        command_alias=allowed_alias,
        changed_layers=changed,
        undo_mark_opened=bool(changed),
        undo_mark_closed=bool(changed),
        postcondition_verified=True,
    )


def execute_live_llc(request: LiveColorStateExecuteRequest) -> LiveLayerBatch10Result:
    return _execute_color_state(request, allowed_alias="LLC")


def execute_live_loc(request: LiveColorStateExecuteRequest) -> LiveLayerBatch10Result:
    return _execute_color_state(request, allowed_alias="LOC")


def execute_live_los(request: LiveLosExecuteRequest) -> LiveLayerBatch10Result:
    if request.request.include_xref_layers:
        raise ValueError("live LOS does not mutate xref-dependent layers")
    doc, layers, _entities, _objects = _validate(
        "LOS", request.request, request.expected_layers, request.expected_entities, request.approval_fingerprint
    )
    plan = plan_activate_layers(request.request, layers)
    changed = tuple(item.layer for item in plan.changes)
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            layer = doc.Layers.Item(change.layer)
            layer.Freeze = change.replacement_frozen
            layer.LayerOn = change.replacement_on
            layer.Lock = change.replacement_locked
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        layer = doc.Layers.Item(change.layer)
        actual = (bool(layer.LayerOn), bool(layer.Freeze), bool(layer.Lock))
        expected = (change.replacement_on, change.replacement_frozen, change.replacement_locked)
        if actual != expected:
            raise RuntimeError(f"LOS layer postcondition failed: {change.layer}")
    return LiveLayerBatch10Result(
        document_name=str(doc.Name),
        command_alias="LOS",
        changed_layers=changed,
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_layer_batch10b_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 10B layer operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 10B layer operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    read_only = ToolAnnotations(
        title="Read live xiCAD layer list",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_lk", preview_live_lk, preview),
        ("xicad_execute_live_lk", execute_live_lk, execute),
        ("xicad_preview_live_llc", preview_live_llc, preview),
        ("xicad_execute_live_llc", execute_live_llc, execute),
        ("xicad_preview_live_loc", preview_live_loc, preview),
        ("xicad_execute_live_loc", execute_live_loc, execute),
        ("xicad_preview_live_los", preview_live_los, preview),
        ("xicad_execute_live_los", execute_live_los, execute),
        ("xicad_preview_live_lp", preview_live_lp, preview),
        ("xicad_execute_live_lp", execute_live_lp, execute),
        ("xicad_read_live_lst", read_live_lst, read_only),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)


def _apply_patch(doc: Any, layer: Any, patch: Any) -> None:
    if patch.linetype is not None:
        doc.Linetypes.Item(patch.linetype)
        layer.Linetype = patch.linetype
    if patch.color_index is not None:
        layer.Color = patch.color_index
    if patch.plottable is not None:
        layer.Plottable = patch.plottable
    if patch.is_frozen is not None:
        layer.Freeze = patch.is_frozen
    if patch.is_on is not None:
        layer.LayerOn = patch.is_on
    if patch.is_locked is not None:
        layer.Lock = patch.is_locked


def _verify_patch(layer: Any, patch: Any) -> bool:
    checks = (
        patch.linetype is None or str(layer.Linetype) == patch.linetype,
        patch.color_index is None or int(layer.Color) == patch.color_index,
        patch.plottable is None or bool(layer.Plottable) == patch.plottable,
        patch.is_frozen is None or bool(layer.Freeze) == patch.is_frozen,
        patch.is_on is None or bool(layer.LayerOn) == patch.is_on,
        patch.is_locked is None or bool(layer.Lock) == patch.is_locked,
    )
    return all(checks)


def execute_live_lp(request: LiveLpExecuteRequest) -> LiveLayerBatch10Result:
    if request.request.patch is not None and request.request.patch.viewport_frozen is not None:
        raise ValueError("live LP viewport_frozen requires an explicit viewport contract")
    doc, layers, entities, objects = _validate(
        "LP", request.request, request.expected_layers, request.expected_entities, request.approval_fingerprint
    )
    plan = plan_layer_property(request.request, layers, entities)
    layer_map = {item.name.casefold(): item for item in layers}
    if plan.entity_changes and any(
        layer_map[item.layer.casefold()].is_locked
        for item in entities
        if item.layer.casefold() in {name.casefold() for name in request.request.target_layers}
    ):
        raise ValueError("LP cannot mutate entities on a locked layer")
    changed_handles = tuple(item.handle for item in plan.entity_changes)
    changed_layers = tuple(item.layer for item in plan.layer_changes)
    doc.StartUndoMark()
    try:
        for change in plan.layer_changes:
            _apply_patch(doc, doc.Layers.Item(change.layer), change.patch)
        for change in plan.entity_changes:
            entity = objects[change.handle.casefold()]
            entity.Color = change.replacement_color_index
            entity.Linetype = change.replacement_linetype
        if plan.merge_target_layer:
            targets = {name.casefold() for name in request.request.target_layers}
            for snapshot in entities:
                if snapshot.layer.casefold() in targets and (request.request.include_nested or not snapshot.nested):
                    objects[snapshot.handle.casefold()].Layer = plan.merge_target_layer
        for name in plan.purge_source_layers:
            doc.Layers.Item(name).Delete()
    finally:
        doc.EndUndoMark()
    for change in plan.entity_changes:
        entity = objects[change.handle.casefold()]
        if int(entity.Color) != change.replacement_color_index or str(entity.Linetype) != change.replacement_linetype:
            raise RuntimeError(f"LP entity postcondition failed: {change.handle}")
    for change in plan.layer_changes:
        if not _verify_patch(doc.Layers.Item(change.layer), change.patch):
            raise RuntimeError(f"LP layer patch postcondition failed: {change.layer}")
    if plan.merge_target_layer:
        targets = {name.casefold() for name in request.request.target_layers}
        for snapshot in entities:
            if snapshot.layer.casefold() in targets and (request.request.include_nested or not snapshot.nested):
                if str(objects[snapshot.handle.casefold()].Layer) != plan.merge_target_layer:
                    raise RuntimeError(f"LP merge postcondition failed: {snapshot.handle}")
    after_layers = {item.name.casefold() for item in _layers(doc)}
    if any(name.casefold() in after_layers for name in plan.purge_source_layers):
        raise RuntimeError("LP purge postcondition failed")
    return LiveLayerBatch10Result(
        document_name=str(doc.Name),
        command_alias="LP",
        changed_handles=changed_handles,
        changed_layers=changed_layers,
        removed_layers=plan.purge_source_layers,
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )
