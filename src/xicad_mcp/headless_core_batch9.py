from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, DrawingSpace


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval")


def _unique(values: Sequence[str], name: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{name} must be unique")


class LayerSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    color_index: int = Field(ge=1, le=255)
    linetype: str = Field(min_length=1)
    is_on: bool = True
    is_frozen: bool = False
    is_locked: bool = False
    is_xref: bool = False
    is_current: bool = False


class LayerEntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    color_index: int = Field(ge=0, le=256)
    linetype: str = Field(min_length=1)
    visible: bool = True
    space: DrawingSpace = DrawingSpace.MODEL
    block_owner_handle: str | None = None
    block_name: str | None = None
    nested: bool = False
    is_xref: bool = False


class Batch9Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def _layer_map(layers: Sequence[LayerSnapshot]) -> dict[str, LayerSnapshot]:
    result = {layer.name.casefold(): layer for layer in layers}
    if len(result) != len(layers):
        raise ValueError("layer names must be unique")
    return result


def _entity_map(entities: Sequence[LayerEntitySnapshot]) -> dict[str, LayerEntitySnapshot]:
    result = {entity.handle.casefold(): entity for entity in entities}
    if len(result) != len(entities):
        raise ValueError("entity handles must be unique")
    return result


# 1/2/3 -- shortcut descriptions define selected-layer off/isolate/all-on.
class SelectedLayerRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    selected_entity_handles: tuple[str, ...] = Field(min_length=1)
    current_layer_policy: str = Field(default="error", pattern="^(error|keep_on)$")
    xref_layer_policy: str = Field(default="skip", pattern="^(error|skip)$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SelectedLayerRequest:
        _unique(self.selected_entity_handles, "selected_entity_handles")
        _approval(self.dry_run, self.approval, "1/2")
        return self


class AllLayersOnRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    thaw_frozen: bool = False
    include_xref_layers: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> AllLayersOnRequest:
        _approval(self.dry_run, self.approval, "3")
        return self


class LayerStateChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    layer: str
    expected_on: bool
    replacement_on: bool
    expected_frozen: bool
    replacement_frozen: bool


class LayerStatePlan(Batch9Plan):
    changes: tuple[LayerStateChange, ...]


def _selected_layer_names(handles: Sequence[str], entities: Sequence[LayerEntitySnapshot]) -> set[str]:
    by_handle = _entity_map(entities)
    result = set()
    for handle in handles:
        entity = by_handle.get(handle.casefold())
        if entity is None:
            raise ValueError(f"entity not found: {handle}")
        result.add(entity.layer.casefold())
    return result


def plan_selected_layers_off(request: SelectedLayerRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot]) -> LayerStatePlan:
    selected = _selected_layer_names(request.selected_entity_handles, entities)
    changes = []
    for layer in layers:
        if layer.name.casefold() not in selected:
            continue
        if layer.is_current:
            if request.current_layer_policy == "error":
                raise ValueError(f"cannot turn off current layer: {layer.name}")
            continue
        if layer.is_xref:
            if request.xref_layer_policy == "error":
                raise ValueError(f"xref layer selected: {layer.name}")
            continue
        if layer.is_on:
            changes.append(LayerStateChange(layer=layer.name, expected_on=True, replacement_on=False,
                                            expected_frozen=layer.is_frozen, replacement_frozen=layer.is_frozen))
    return LayerStatePlan(command_alias="1", legacy_symbol="xiSelOff", document_id=request.document_id,
                          changes=tuple(changes), dry_run=request.dry_run)


def plan_selected_layers_isolate(request: SelectedLayerRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot]) -> LayerStatePlan:
    selected = _selected_layer_names(request.selected_entity_handles, entities)
    changes = []
    for layer in layers:
        desired = layer.name.casefold() in selected or layer.is_current
        if layer.is_xref and request.xref_layer_policy == "skip":
            continue
        if layer.is_xref and request.xref_layer_policy == "error":
            raise ValueError(f"xref layer in isolate scope: {layer.name}")
        if layer.is_on != desired:
            changes.append(LayerStateChange(layer=layer.name, expected_on=layer.is_on, replacement_on=desired,
                                            expected_frozen=layer.is_frozen, replacement_frozen=layer.is_frozen))
    return LayerStatePlan(command_alias="2", legacy_symbol="xiSelLayerOn", document_id=request.document_id,
                          changes=tuple(changes), dry_run=request.dry_run)


def plan_all_layers_on(request: AllLayersOnRequest, layers: Sequence[LayerSnapshot]) -> LayerStatePlan:
    changes = []
    for layer in layers:
        if layer.is_xref and not request.include_xref_layers:
            continue
        replacement_frozen = False if request.thaw_frozen else layer.is_frozen
        if not layer.is_on or replacement_frozen != layer.is_frozen:
            changes.append(LayerStateChange(layer=layer.name, expected_on=layer.is_on, replacement_on=True,
                                            expected_frozen=layer.is_frozen, replacement_frozen=replacement_frozen))
    return LayerStatePlan(command_alias="3", legacy_symbol="xiLayeron", document_id=request.document_id,
                          changes=tuple(changes), dry_run=request.dry_run)


# DOL -- draw order is supplied explicitly because "layer order" direction is ambiguous.
class DrawOrderDirection(StrEnum):
    FIRST_LAYER_TO_FRONT = "first_layer_to_front"
    FIRST_LAYER_TO_BACK = "first_layer_to_back"


class DrawOrderByLayerRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    ordered_layers: tuple[str, ...] = Field(min_length=1)
    direction: DrawOrderDirection
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    include_nested: bool = False
    unlisted_layer_policy: str = Field(default="preserve", pattern="^(preserve|error)$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DrawOrderByLayerRequest:
        _unique(self.ordered_layers, "ordered_layers")
        _approval(self.dry_run, self.approval, "DOL")
        return self


class DrawOrderPlan(Batch9Plan):
    command_alias: str = "DOL"
    legacy_symbol: str = "xiDraworderByLayer"
    ordered_handles: tuple[str, ...]
    direction: DrawOrderDirection


def plan_draw_order_by_layer(request: DrawOrderByLayerRequest, entities: Sequence[LayerEntitySnapshot]) -> DrawOrderPlan:
    rank = {name.casefold(): index for index, name in enumerate(request.ordered_layers)}
    candidates, unlisted = [], []
    for entity in entities:
        if entity.space not in request.spaces or (entity.nested and not request.include_nested):
            continue
        if entity.layer.casefold() not in rank:
            unlisted.append(entity.handle)
        else:
            candidates.append(entity)
    if unlisted and request.unlisted_layer_policy == "error":
        raise ValueError("DOL encountered entities on unlisted layers")
    candidates.sort(key=lambda entity: rank[entity.layer.casefold()])
    return DrawOrderPlan(document_id=request.document_id, ordered_handles=tuple(e.handle for e in candidates),
                         direction=request.direction, dry_run=request.dry_run)


# ELY -- destructive deletion requires exact layers and expected handles.
class EraseLayerRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_layers: tuple[str, ...] = Field(min_length=1)
    expected_entity_handles: tuple[str, ...] = Field(min_length=1)
    include_nested: bool = False
    erase_layer_records: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> EraseLayerRequest:
        _unique(self.target_layers, "target_layers")
        _unique(self.expected_entity_handles, "expected_entity_handles")
        if any(name.casefold() in {"0", "defpoints"} or "|" in name for name in self.target_layers):
            raise ValueError("ELY cannot target protected or xref-dependent layers")
        _approval(self.dry_run, self.approval, "ELY")
        return self


class EraseLayerPlan(Batch9Plan):
    command_alias: str = "ELY"
    legacy_symbol: str = "xiEraseLayer"
    erase_handles: tuple[str, ...]
    erase_layer_records: tuple[str, ...]


def plan_erase_layer(request: EraseLayerRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot]) -> EraseLayerPlan:
    layer_map = _layer_map(layers)
    targets = {name.casefold() for name in request.target_layers}
    for name in request.target_layers:
        layer = layer_map.get(name.casefold())
        if layer is None or layer.is_current or layer.is_xref or layer.is_locked:
            raise ValueError(f"ELY layer is not safely erasable: {name}")
    actual = tuple(e.handle for e in entities if e.layer.casefold() in targets and (request.include_nested or not e.nested))
    if request.erase_layer_records and any(
        e.layer.casefold() in targets and e.nested and not request.include_nested for e in entities
    ):
        raise ValueError("ELY cannot remove layer records while excluded nested entities remain")
    if {h.casefold() for h in actual} != {h.casefold() for h in request.expected_entity_handles}:
        raise ValueError("ELY expected handles do not match layer contents")
    return EraseLayerPlan(document_id=request.document_id, erase_handles=actual,
                          erase_layer_records=request.target_layers if request.erase_layer_records else (),
                          dry_run=request.dry_run)


# EOO/ESF/ESO -- entity visibility, distinct from layer on/off.
class EntityVisibilityRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    selected_handles: tuple[str, ...] = ()
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    include_same_block_name: bool = False
    include_nested: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> EntityVisibilityRequest:
        _unique(self.selected_handles, "selected_handles")
        _approval(self.dry_run, self.approval, "EOO/ESF/ESO")
        return self


class EntityVisibilityChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_visible: bool
    replacement_visible: bool


class EntityVisibilityPlan(Batch9Plan):
    changes: tuple[EntityVisibilityChange, ...]


def plan_entity_visibility(request: EntityVisibilityRequest, entities: Sequence[LayerEntitySnapshot], *, alias: str) -> EntityVisibilityPlan:
    if alias not in {"EOO", "ESF", "ESO"}:
        raise ValueError("alias must be EOO, ESF or ESO")
    selected = {handle.casefold() for handle in request.selected_handles}
    by_handle = _entity_map(entities)
    missing = selected - set(by_handle)
    if missing:
        raise ValueError(f"entity not found: {sorted(missing)[0]}")
    selected_block_names = {by_handle[h].block_name.casefold() for h in selected if by_handle[h].block_name}
    changes = []
    for entity in entities:
        if entity.space not in request.spaces or entity.is_xref or (entity.nested and not request.include_nested):
            continue
        is_selected = entity.handle.casefold() in selected
        if request.include_same_block_name and entity.block_name:
            is_selected = is_selected or entity.block_name.casefold() in selected_block_names
        desired = True if alias == "EOO" else (not is_selected if alias == "ESF" else is_selected)
        if entity.visible != desired:
            changes.append(EntityVisibilityChange(handle=entity.handle, expected_visible=entity.visible,
                                                  replacement_visible=desired))
    symbols = {"EOO": "xiEntOffOn", "ESF": "xiEntSelOff", "ESO": "xiEntSelOn"}
    return EntityVisibilityPlan(command_alias=alias, legacy_symbol=symbols[alias], document_id=request.document_id,
                                changes=tuple(changes), dry_run=request.dry_run)


# EW -- choose an entity's layer as the current layer.
class SetCurrentLayerRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_entity_handle: str = Field(min_length=1)
    unlock_policy: str = Field(default="error", pattern="^(error|unlock)$")
    thaw_policy: str = Field(default="error", pattern="^(error|thaw)$")
    turn_on: bool = True
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SetCurrentLayerRequest:
        _approval(self.dry_run, self.approval, "EW")
        return self


class CurrentLayerPlan(Batch9Plan):
    command_alias: str = "EW"
    legacy_symbol: str = "xiSetCLayer"
    expected_current_layer: str
    replacement_current_layer: str
    prerequisite_changes: tuple[LayerStateChange, ...]


def plan_set_current_layer(request: SetCurrentLayerRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot]) -> CurrentLayerPlan:
    entity = _entity_map(entities).get(request.source_entity_handle.casefold())
    if entity is None:
        raise ValueError(f"entity not found: {request.source_entity_handle}")
    layer_map = _layer_map(layers)
    target = layer_map.get(entity.layer.casefold())
    current_layers = [layer for layer in layers if layer.is_current]
    if target is None or len(current_layers) != 1 or target.is_xref:
        raise ValueError("EW requires existing non-xref target and exactly one current layer")
    current = current_layers[0]
    if target.is_locked and request.unlock_policy == "error":
        raise ValueError("EW target layer is locked")
    if target.is_frozen and request.thaw_policy == "error":
        raise ValueError("EW target layer is frozen")
    prerequisites = ()
    if (request.turn_on and not target.is_on) or (target.is_frozen and request.thaw_policy == "thaw"):
        prerequisites = (LayerStateChange(layer=target.name, expected_on=target.is_on,
            replacement_on=True if request.turn_on else target.is_on, expected_frozen=target.is_frozen,
            replacement_frozen=False if request.thaw_policy == "thaw" else target.is_frozen),)
    return CurrentLayerPlan(document_id=request.document_id, expected_current_layer=current.name,
                            replacement_current_layer=target.name, prerequisite_changes=prerequisites,
                            dry_run=request.dry_run)


# LAM -- recovered DCL policies are explicit.
class LayerMergeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_layers: tuple[str, ...] = Field(min_length=1)
    target_layer: str = Field(min_length=1)
    include_nested: bool
    preserve_entity_color: bool
    preserve_entity_linetype: bool
    remove_source_layers: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LayerMergeRequest:
        _unique(self.source_layers, "source_layers")
        if self.target_layer.casefold() in {name.casefold() for name in self.source_layers}:
            raise ValueError("LAM target layer cannot be a source layer")
        if any(name.casefold() in {"0", "defpoints"} or "|" in name for name in self.source_layers):
            raise ValueError("LAM cannot remove protected or xref-dependent source layers")
        _approval(self.dry_run, self.approval, "LAM")
        return self


class EntityLayerChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_layer: str
    replacement_layer: str
    replacement_color_index: int
    replacement_linetype: str


class LayerMergePlan(Batch9Plan):
    command_alias: str = "LAM"
    legacy_symbol: str = "xiLayerMerge"
    entity_changes: tuple[EntityLayerChange, ...]
    remove_layers: tuple[str, ...]


def plan_layer_merge(request: LayerMergeRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot]) -> LayerMergePlan:
    layer_map = _layer_map(layers)
    target = layer_map.get(request.target_layer.casefold())
    if target is None or target.is_xref or target.is_locked:
        raise ValueError("LAM target layer is unavailable")
    sources = {name.casefold() for name in request.source_layers}
    for name in request.source_layers:
        source = layer_map.get(name.casefold())
        if source is None or source.is_current or source.is_xref or source.is_locked:
            raise ValueError(f"LAM source layer cannot be merged: {name}")
    changes = tuple(EntityLayerChange(handle=e.handle, expected_layer=e.layer, replacement_layer=target.name,
        replacement_color_index=e.color_index if request.preserve_entity_color else 256,
        replacement_linetype=e.linetype if request.preserve_entity_linetype else "ByLayer")
        for e in entities if e.layer.casefold() in sources and (request.include_nested or not e.nested))
    if request.remove_source_layers and any(
        e.layer.casefold() in sources and e.nested and not request.include_nested for e in entities
    ):
        raise ValueError("LAM cannot remove source layers while excluded nested entities remain")
    return LayerMergePlan(document_id=request.document_id, entity_changes=changes,
                          remove_layers=request.source_layers if request.remove_source_layers else (),
                          dry_run=request.dry_run)


# LC/LCC -- target layer may be existing or created; property reset is explicit.
class TargetLayerMode(StrEnum):
    EXISTING = "existing"
    CREATE = "create"


class EntityPropertyPolicy(StrEnum):
    PRESERVE = "preserve"
    BY_LAYER = "by_layer"


class TargetLayerSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    mode: TargetLayerMode
    name: str = Field(min_length=1)
    color_index: int | None = Field(default=None, ge=1, le=255)
    linetype: str | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> TargetLayerSpec:
        if self.mode is TargetLayerMode.CREATE and (self.color_index is None or not self.linetype):
            raise ValueError("new layer requires color_index and linetype")
        return self


class ChangeLayerRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    target_layer: TargetLayerSpec
    color_policy: EntityPropertyPolicy
    linetype_policy: EntityPropertyPolicy
    include_nested: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ChangeLayerRequest:
        _unique(self.target_handles, "target_handles")
        _approval(self.dry_run, self.approval, "LC")
        return self


class ColorToLayerRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_color_indices: tuple[int, ...] = Field(min_length=1)
    target_layer: TargetLayerSpec
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    include_nested: bool = False
    byblock_color_policy: str = Field(default="skip", pattern="^(skip|include)$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ColorToLayerRequest:
        if len(set(self.source_color_indices)) != len(self.source_color_indices):
            raise ValueError("source_color_indices must be unique")
        if any(value < 0 or value > 256 for value in self.source_color_indices):
            raise ValueError("source color index is out of range")
        _approval(self.dry_run, self.approval, "LCC")
        return self


class ChangeLayerPlan(Batch9Plan):
    create_layer: LayerSnapshot | None
    changes: tuple[EntityLayerChange, ...]


def _resolve_target(spec: TargetLayerSpec, layers: Sequence[LayerSnapshot]) -> tuple[LayerSnapshot, LayerSnapshot | None]:
    existing = _layer_map(layers).get(spec.name.casefold())
    if spec.mode is TargetLayerMode.EXISTING:
        if existing is None or existing.is_xref or existing.is_locked:
            raise ValueError("target layer is unavailable")
        return existing, None
    if existing is not None:
        raise ValueError("new target layer already exists")
    created = LayerSnapshot(name=spec.name, color_index=spec.color_index, linetype=spec.linetype)
    return created, created


def plan_change_layer(request: ChangeLayerRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot]) -> ChangeLayerPlan:
    target, created = _resolve_target(request.target_layer, layers)
    layer_map = _layer_map(layers)
    by_handle = _entity_map(entities)
    changes = []
    for handle in request.target_handles:
        entity = by_handle.get(handle.casefold())
        source_layer = layer_map.get(entity.layer.casefold()) if entity is not None else None
        if entity is None or entity.is_xref or (entity.nested and not request.include_nested):
            raise ValueError(f"LC entity cannot be changed: {handle}")
        if source_layer is not None and source_layer.is_locked:
            raise ValueError(f"LC entity is on a locked layer: {handle}")
        changes.append(EntityLayerChange(handle=entity.handle, expected_layer=entity.layer, replacement_layer=target.name,
            replacement_color_index=entity.color_index if request.color_policy is EntityPropertyPolicy.PRESERVE else 256,
            replacement_linetype=entity.linetype if request.linetype_policy is EntityPropertyPolicy.PRESERVE else "ByLayer"))
    return ChangeLayerPlan(command_alias="LC", legacy_symbol="xiChangeLayer", document_id=request.document_id,
                           create_layer=created, changes=tuple(changes), dry_run=request.dry_run)


def plan_color_to_layer(request: ColorToLayerRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot]) -> ChangeLayerPlan:
    target, created = _resolve_target(request.target_layer, layers)
    layer_map = _layer_map(layers)
    colors = set(request.source_color_indices)
    changes = []
    for entity in entities:
        if entity.space not in request.spaces or entity.is_xref or (entity.nested and not request.include_nested):
            continue
        if entity.color_index == 0 and request.byblock_color_policy == "skip":
            continue
        if entity.color_index in colors:
            source_layer = layer_map.get(entity.layer.casefold())
            if source_layer is not None and source_layer.is_locked:
                raise ValueError(f"LCC matching entity is on a locked layer: {entity.handle}")
            changes.append(EntityLayerChange(handle=entity.handle, expected_layer=entity.layer,
                replacement_layer=target.name, replacement_color_index=256, replacement_linetype=entity.linetype))
    return ChangeLayerPlan(command_alias="LCC", legacy_symbol="xiColor2Layer", document_id=request.document_id,
                           create_layer=created, changes=tuple(changes), dry_run=request.dry_run)


def register_headless_core_batch9_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(title="xiCAD Headless Core Batch 9 Planner", readOnlyHint=True,
                                destructiveHint=False, idempotentHint=True, openWorldHint=False)

    @mcp.tool(name="xicad_plan_1", annotations=read_only)
    def mcp_plan_1(request: SelectedLayerRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> LayerStatePlan:
        return plan_selected_layers_off(request, layers, entities)

    @mcp.tool(name="xicad_plan_2", annotations=read_only)
    def mcp_plan_2(request: SelectedLayerRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> LayerStatePlan:
        return plan_selected_layers_isolate(request, layers, entities)

    @mcp.tool(name="xicad_plan_3", annotations=read_only)
    def mcp_plan_3(request: AllLayersOnRequest, layers: tuple[LayerSnapshot, ...]) -> LayerStatePlan:
        return plan_all_layers_on(request, layers)

    @mcp.tool(name="xicad_plan_dol", annotations=read_only)
    def mcp_plan_dol(request: DrawOrderByLayerRequest, entities: tuple[LayerEntitySnapshot, ...]) -> DrawOrderPlan:
        return plan_draw_order_by_layer(request, entities)

    @mcp.tool(name="xicad_plan_ely", annotations=read_only)
    def mcp_plan_ely(request: EraseLayerRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> EraseLayerPlan:
        return plan_erase_layer(request, layers, entities)

    @mcp.tool(name="xicad_plan_eoo", annotations=read_only)
    def mcp_plan_eoo(request: EntityVisibilityRequest, entities: tuple[LayerEntitySnapshot, ...]) -> EntityVisibilityPlan:
        return plan_entity_visibility(request, entities, alias="EOO")

    @mcp.tool(name="xicad_plan_esf", annotations=read_only)
    def mcp_plan_esf(request: EntityVisibilityRequest, entities: tuple[LayerEntitySnapshot, ...]) -> EntityVisibilityPlan:
        return plan_entity_visibility(request, entities, alias="ESF")

    @mcp.tool(name="xicad_plan_eso", annotations=read_only)
    def mcp_plan_eso(request: EntityVisibilityRequest, entities: tuple[LayerEntitySnapshot, ...]) -> EntityVisibilityPlan:
        return plan_entity_visibility(request, entities, alias="ESO")

    @mcp.tool(name="xicad_plan_ew", annotations=read_only)
    def mcp_plan_ew(request: SetCurrentLayerRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> CurrentLayerPlan:
        return plan_set_current_layer(request, layers, entities)

    @mcp.tool(name="xicad_plan_lam", annotations=read_only)
    def mcp_plan_lam(request: LayerMergeRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> LayerMergePlan:
        return plan_layer_merge(request, layers, entities)

    @mcp.tool(name="xicad_plan_lc", annotations=read_only)
    def mcp_plan_lc(request: ChangeLayerRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> ChangeLayerPlan:
        return plan_change_layer(request, layers, entities)

    @mcp.tool(name="xicad_plan_lcc", annotations=read_only)
    def mcp_plan_lcc(request: ColorToLayerRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> ChangeLayerPlan:
        return plan_color_to_layer(request, layers, entities)
