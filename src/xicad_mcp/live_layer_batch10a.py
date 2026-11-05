from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, DrawingSpace
from .headless_core_batch9 import (
    EntityPropertyPolicy,
    LayerEntitySnapshot,
    LayerSnapshot,
    TargetLayerSpec,
)
from .headless_core_batch10 import (
    ChangeLayerOnlyRequest,
    ColorLayerBatchMethod,
    ColorLayerCarrier,
    ColorLayerMapping,
    ColorLayerObjectSnapshot,
    ColorToLayerBatchRequest,
    LayerSetRequest,
    ObjectKind,
    SimilarityPolicy,
    SimilarLayerObjectSnapshot,
    SimilarObjectsLayerRequest,
    plan_change_layer_only,
    plan_color_to_layer_batch,
    plan_layer_protection,
    plan_similar_objects_layer,
)
from .live_layer_batch9a import ZWCADLiveLayer9aAdapter


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _models(items: tuple[BaseModel, ...]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)


class LiveLcdPreviewRequest(_Request):
    method: ColorLayerBatchMethod
    mappings: tuple[ColorLayerMapping, ...] = ()
    generated_layer_prefix: str = "COLOR_"
    text_override: TargetLayerSpec | None = None
    dimension_override: TargetLayerSpec | None = None
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)


class LiveLcdExecuteRequest(LiveLcdPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[ColorLayerObjectSnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveLcoPreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    target_layer: str = Field(min_length=1)


class LiveLcoExecuteRequest(LiveLcoPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveLcsPreviewRequest(_Request):
    reference_handle: str = Field(min_length=1)
    similarity_policy: SimilarityPolicy
    target_layer: str = Field(min_length=1)
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    property_policy: EntityPropertyPolicy


class LiveLcsExecuteRequest(LiveLcsPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[SimilarLayerObjectSnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveLayerSetPreviewRequest(_Request):
    selected_entity_handles: tuple[str, ...] = Field(min_length=1)
    xref_layer_policy: str = Field(default="skip", pattern=r"^(skip|error)$")


class LiveLayerSetExecuteRequest(LiveLayerSetPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveLayer10aResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_layers: tuple[str, ...] = ()
    changed_layers: tuple[str, ...] = ()
    changed_handles: tuple[str, ...] = ()
    postcondition_verified: bool


class ZWCADLiveLayer10aAdapter(ZWCADLiveLayer9aAdapter):
    @staticmethod
    def _carrier(object_name: str) -> ColorLayerCarrier:
        name = object_name.casefold()
        if any(token in name for token in ("text", "attribute")):
            return ColorLayerCarrier.TEXT
        if "dimension" in name or "leader" in name:
            return ColorLayerCarrier.DIMENSION_OR_LEADER
        return ColorLayerCarrier.GENERAL

    @staticmethod
    def _kind(object_name: str) -> ObjectKind:
        name = object_name.casefold()
        if name == "acdbline":
            return ObjectKind.LINE
        if "polyline" in name:
            return ObjectKind.POLYLINE
        if name == "acdbtext":
            return ObjectKind.TEXT
        if name == "acdbmtext":
            return ObjectKind.MTEXT
        if "blockreference" in name:
            return ObjectKind.BLOCK_REFERENCE
        if "hatch" in name:
            return ObjectKind.HATCH
        if "dimension" in name:
            return ObjectKind.DIMENSION
        return ObjectKind.OTHER

    def color_inventory(self) -> tuple[ColorLayerObjectSnapshot, ...]:
        base = self.inventory()
        objects = self.entity_objects()
        return tuple(
            ColorLayerObjectSnapshot(
                **item.model_dump(), carrier=self._carrier(str(objects[item.handle.casefold()].ObjectName))
            )
            for item in base
        )

    def similar_inventory(self) -> tuple[SimilarLayerObjectSnapshot, ...]:
        base = self.inventory()
        objects = self.entity_objects()
        result = []
        for item in base:
            obj = objects[item.handle.casefold()]
            block_name = item.block_name
            if "blockreference" in str(obj.ObjectName).casefold():
                try:
                    block_name = str(obj.EffectiveName)
                except Exception:
                    block_name = str(obj.Name)
            result.append(
                SimilarLayerObjectSnapshot(
                    **item.model_dump(), block_name=block_name, object_kind=self._kind(str(obj.ObjectName))
                )
            )
        return tuple(result)


def _approval(execute: bool, fingerprint: str | None = None) -> Approval:
    return Approval(approved=execute, fingerprint=fingerprint)


def _same(actual: tuple[BaseModel, ...], expected: tuple[BaseModel, ...], alias: str) -> None:
    if _models(actual) != _models(expected):
        raise ValueError(f"{alias} inventory no longer matches the approved snapshot")


def _payload(
    request: BaseModel, layers: tuple[LayerSnapshot, ...], entities: tuple[BaseModel, ...], plan: BaseModel
) -> dict[str, Any]:
    body = {
        **request.model_dump(mode="json"),
        "expected_layers": _models(layers),
        "expected_entities": _models(entities),
    }
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def _protect_changes(changes: tuple[Any, ...]) -> None:
    protected = [
        change.handle
        for change in changes
        if change.expected_layer.casefold() in {"0", "defpoints"}
        or change.replacement_layer.casefold() in {"0", "defpoints"}
        or "|" in change.expected_layer
        or "|" in change.replacement_layer
    ]
    if protected:
        raise ValueError(f"system-layer entities are protected: {protected}")


def _lcd_core(
    request: LiveLcdPreviewRequest, execute: bool, fingerprint: str | None = None
) -> ColorToLayerBatchRequest:
    return ColorToLayerBatchRequest(
        document_id=request.document_name,
        method=request.method,
        mappings=request.mappings,
        generated_layer_prefix=request.generated_layer_prefix,
        text_override=request.text_override,
        dimension_override=request.dimension_override,
        include_nested=False,
        spaces=request.spaces,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_lcd(request: LiveLcdPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveLayer10aAdapter(request.document_name)
    layers = adapter.layers()
    entities = adapter.color_inventory()
    plan = plan_color_to_layer_batch(_lcd_core(request, False), layers, entities)
    _protect_changes(plan.changes)
    return _payload(request, layers, entities, plan)


def execute_live_lcd(request: LiveLcdExecuteRequest) -> LiveLayer10aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact LCD request")
    adapter = ZWCADLiveLayer10aAdapter(request.document_name)
    layers = adapter.layers()
    entities = adapter.color_inventory()
    _same(layers, request.expected_layers, "LCD")
    _same(entities, request.expected_entities, "LCD")
    plan = plan_color_to_layer_batch(_lcd_core(request, True, request.approval_fingerprint), layers, entities)
    _protect_changes(plan.changes)
    doc = adapter.connect()
    objects = adapter.entity_objects()
    doc.StartUndoMark()
    try:
        for spec in plan.create_layers:
            layer = doc.Layers.Add(spec.name)
            layer.Color = spec.color_index
            layer.Linetype = spec.linetype
        for change in plan.changes:
            entity = objects[change.handle.casefold()]
            entity.Layer = change.replacement_layer
            entity.Color = change.replacement_color_index
            entity.Linetype = change.replacement_linetype
    finally:
        doc.EndUndoMark()
    after_layers = {x.name.casefold(): x for x in adapter.layers()}
    after = adapter.entity_objects()
    verified = all(
        spec.name.casefold() in after_layers
        and after_layers[spec.name.casefold()].color_index == spec.color_index
        and after_layers[spec.name.casefold()].linetype.casefold() == spec.linetype.casefold()
        for spec in plan.create_layers
    ) and all(
        str(after[c.handle.casefold()].Layer) == c.replacement_layer
        and int(after[c.handle.casefold()].Color) == c.replacement_color_index
        and str(after[c.handle.casefold()].Linetype).casefold() == c.replacement_linetype.casefold()
        for c in plan.changes
    )
    if not verified:
        raise RuntimeError("LCD postcondition failed")
    return LiveLayer10aResult(
        document_name=str(doc.Name),
        command_alias="LCD",
        created_layers=tuple(x.name for x in plan.create_layers),
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )


def _lco_core(request: LiveLcoPreviewRequest, execute: bool, fingerprint: str | None = None) -> ChangeLayerOnlyRequest:
    return ChangeLayerOnlyRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        target_layer=request.target_layer,
        include_nested=False,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_lco(request: LiveLcoPreviewRequest) -> dict[str, Any]:
    if request.target_layer.casefold() in {"0", "defpoints"} or "|" in request.target_layer:
        raise ValueError("protected target layer")
    adapter = ZWCADLiveLayer10aAdapter(request.document_name)
    layers, entities = adapter.layers(), adapter.inventory()
    plan = plan_change_layer_only(_lco_core(request, False), layers, entities)
    _protect_changes(plan.changes)
    return _payload(request, layers, entities, plan)


def _execute_entity_changes(
    request: Any,
    alias: str,
    entities_reader: Callable[[Any], tuple[BaseModel, ...]],
    planner: Callable[[Any, tuple[LayerSnapshot, ...], tuple[BaseModel, ...]], Any],
    core: Callable[..., Any],
) -> LiveLayer10aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError(f"approval fingerprint does not match the exact {alias} request")
    adapter = ZWCADLiveLayer10aAdapter(request.document_name)
    layers = adapter.layers()
    entities = entities_reader(adapter)
    _same(layers, request.expected_layers, alias)
    _same(entities, request.expected_entities, alias)
    plan = planner(core(request, True, request.approval_fingerprint), layers, entities)
    _protect_changes(plan.changes)
    objects = adapter.entity_objects()
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            entity = objects[change.handle.casefold()]
            entity.Layer = change.replacement_layer
            entity.Color = change.replacement_color_index
            entity.Linetype = change.replacement_linetype
    finally:
        doc.EndUndoMark()
    after = adapter.entity_objects()
    if not all(
        str(after[c.handle.casefold()].Layer) == c.replacement_layer
        and int(after[c.handle.casefold()].Color) == c.replacement_color_index
        and str(after[c.handle.casefold()].Linetype).casefold() == c.replacement_linetype.casefold()
        for c in plan.changes
    ):
        raise RuntimeError(f"{alias} postcondition failed")
    return LiveLayer10aResult(
        document_name=str(doc.Name),
        command_alias=alias,
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )


def execute_live_lco(request: LiveLcoExecuteRequest) -> LiveLayer10aResult:
    return _execute_entity_changes(request, "LCO", lambda a: a.inventory(), plan_change_layer_only, _lco_core)


def _lcs_core(
    request: LiveLcsPreviewRequest, execute: bool, fingerprint: str | None = None
) -> SimilarObjectsLayerRequest:
    return SimilarObjectsLayerRequest(
        document_id=request.document_name,
        reference_handle=request.reference_handle,
        similarity_policy=request.similarity_policy,
        target_layer=request.target_layer,
        spaces=request.spaces,
        include_nested=False,
        property_policy=request.property_policy,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_lcs(request: LiveLcsPreviewRequest) -> dict[str, Any]:
    if request.target_layer.casefold() in {"0", "defpoints"} or "|" in request.target_layer:
        raise ValueError("protected target layer")
    adapter = ZWCADLiveLayer10aAdapter(request.document_name)
    layers, entities = adapter.layers(), adapter.similar_inventory()
    plan = plan_similar_objects_layer(_lcs_core(request, False), layers, entities)
    _protect_changes(plan.changes)
    return _payload(request, layers, entities, plan)


def execute_live_lcs(request: LiveLcsExecuteRequest) -> LiveLayer10aResult:
    return _execute_entity_changes(
        request, "LCS", lambda a: a.similar_inventory(), plan_similar_objects_layer, _lcs_core
    )


def _set_core(request: LiveLayerSetPreviewRequest, execute: bool, fingerprint: str | None = None) -> LayerSetRequest:
    return LayerSetRequest(
        document_id=request.document_name,
        selected_entity_handles=request.selected_entity_handles,
        xref_layer_policy=request.xref_layer_policy,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def _protection_plan(
    request: LiveLayerSetPreviewRequest,
    alias: str,
    layers: tuple[LayerSnapshot, ...],
    entities: tuple[LayerEntitySnapshot, ...],
    execute: bool = False,
    fingerprint: str | None = None,
) -> Any:
    plan = plan_layer_protection(_set_core(request, execute, fingerprint), layers, entities, alias=alias)
    changes = tuple(c for c in plan.changes if c.layer.casefold() not in {"0", "defpoints"} and "|" not in c.layer)
    return plan.model_copy(update={"changes": changes})


def _preview_protection(request: LiveLayerSetPreviewRequest, alias: str) -> dict[str, Any]:
    adapter = ZWCADLiveLayer10aAdapter(request.document_name)
    layers, entities = adapter.layers(), adapter.inventory()
    return _payload(request, layers, entities, _protection_plan(request, alias, layers, entities))


def preview_live_lf(request: LiveLayerSetPreviewRequest) -> dict[str, Any]:
    return _preview_protection(request, "LF")


def preview_live_lff(request: LiveLayerSetPreviewRequest) -> dict[str, Any]:
    return _preview_protection(request, "LFF")


def preview_live_lfk(request: LiveLayerSetPreviewRequest) -> dict[str, Any]:
    return _preview_protection(request, "LFK")


def _execute_protection(request: LiveLayerSetExecuteRequest, alias: str) -> LiveLayer10aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError(f"approval fingerprint does not match the exact {alias} request")
    adapter = ZWCADLiveLayer10aAdapter(request.document_name)
    layers, entities = adapter.layers(), adapter.inventory()
    _same(layers, request.expected_layers, alias)
    _same(entities, request.expected_entities, alias)
    plan = _protection_plan(request, alias, layers, entities, True, request.approval_fingerprint)
    records = adapter.layer_objects()
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            layer = records[change.layer.casefold()]
            layer.Freeze = change.replacement_frozen
            layer.Lock = change.replacement_locked
    finally:
        doc.EndUndoMark()
    after = {x.name.casefold(): x for x in adapter.layers()}
    if not all(
        after[c.layer.casefold()].is_frozen == c.replacement_frozen
        and after[c.layer.casefold()].is_locked == c.replacement_locked
        for c in plan.changes
    ):
        raise RuntimeError(f"{alias} postcondition failed")
    return LiveLayer10aResult(
        document_name=str(doc.Name),
        command_alias=alias,
        changed_layers=tuple(c.layer for c in plan.changes),
        postcondition_verified=True,
    )


def execute_live_lf(request: LiveLayerSetExecuteRequest) -> LiveLayer10aResult:
    return _execute_protection(request, "LF")


def execute_live_lff(request: LiveLayerSetExecuteRequest) -> LiveLayer10aResult:
    return _execute_protection(request, "LFF")


def execute_live_lfk(request: LiveLayerSetExecuteRequest) -> LiveLayer10aResult:
    return _execute_protection(request, "LFK")


def register_live_layer_batch10a_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 10A layer operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 10A layer operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_lcd", preview_live_lcd, preview),
        ("xicad_execute_live_lcd", execute_live_lcd, execute),
        ("xicad_preview_live_lco", preview_live_lco, preview),
        ("xicad_execute_live_lco", execute_live_lco, execute),
        ("xicad_preview_live_lcs", preview_live_lcs, preview),
        ("xicad_execute_live_lcs", execute_live_lcs, execute),
        ("xicad_preview_live_lf", preview_live_lf, preview),
        ("xicad_execute_live_lf", execute_live_lf, execute),
        ("xicad_preview_live_lff", preview_live_lff, preview),
        ("xicad_execute_live_lff", execute_live_lff, execute),
        ("xicad_preview_live_lfk", preview_live_lfk, preview),
        ("xicad_execute_live_lfk", execute_live_lfk, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
