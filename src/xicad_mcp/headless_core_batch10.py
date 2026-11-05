from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, DrawingSpace, Point3D
from .headless_core_batch9 import (
    ChangeLayerPlan,
    ChangeLayerRequest,
    EntityLayerChange,
    EntityPropertyPolicy,
    LayerEntitySnapshot,
    LayerSnapshot,
    LayerStateChange,
    TargetLayerMode,
    TargetLayerSpec,
    plan_change_layer,
)


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval")


def _unique(values: Sequence[str], name: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{name} must be unique")


def _layers(layers: Sequence[LayerSnapshot]) -> dict[str, LayerSnapshot]:
    result = {layer.name.casefold(): layer for layer in layers}
    if len(result) != len(layers):
        raise ValueError("layer names must be unique")
    return result


def _entities(entities: Sequence[LayerEntitySnapshot]) -> dict[str, LayerEntitySnapshot]:
    result = {entity.handle.casefold(): entity for entity in entities}
    if len(result) != len(entities):
        raise ValueError("entity handles must be unique")
    return result


class Batch10Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


# LCD -- recovered DCL has three mapping methods and text/dimension overrides.
class ColorLayerCarrier(StrEnum):
    GENERAL = "general"
    TEXT = "text"
    DIMENSION_OR_LEADER = "dimension_or_leader"


class ColorLayerObjectSnapshot(LayerEntitySnapshot):
    carrier: ColorLayerCarrier = ColorLayerCarrier.GENERAL


class ColorLayerMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_color_index: int = Field(ge=0, le=256)
    target_layer: TargetLayerSpec


class ColorLayerBatchMethod(StrEnum):
    COLOR_NUMBER_LAYER_CREATION = "color_number_layer_creation"
    INDIVIDUAL_MAPPING = "individual_mapping"
    NORMALIZED_LIST_MAPPING = "normalized_list_mapping"


class ColorToLayerBatchRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    method: ColorLayerBatchMethod
    mappings: tuple[ColorLayerMapping, ...] = ()
    generated_layer_prefix: str = "COLOR_"
    text_override: TargetLayerSpec | None = None
    dimension_override: TargetLayerSpec | None = None
    include_nested: bool = False
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ColorToLayerBatchRequest:
        if self.method is not ColorLayerBatchMethod.COLOR_NUMBER_LAYER_CREATION and not self.mappings:
            raise ValueError("LCD mapping method requires normalized mappings")
        if self.mappings:
            colors = [mapping.source_color_index for mapping in self.mappings]
            if len(colors) != len(set(colors)):
                raise ValueError("LCD source colors must be unique")
        _approval(self.dry_run, self.approval, "LCD")
        return self


class ColorToLayerBatchPlan(Batch10Plan):
    command_alias: str = "LCD"
    legacy_symbol: str = "xiColor2Layer2"
    create_layers: tuple[LayerSnapshot, ...]
    changes: tuple[EntityLayerChange, ...]


def plan_color_to_layer_batch(request: ColorToLayerBatchRequest, layers: Sequence[LayerSnapshot], entities: Sequence[ColorLayerObjectSnapshot]) -> ColorToLayerBatchPlan:
    existing = _layers(layers)
    mapping_by_color = {mapping.source_color_index: mapping.target_layer for mapping in request.mappings}
    generated_specs: dict[int, TargetLayerSpec] = {}
    if request.method is ColorLayerBatchMethod.COLOR_NUMBER_LAYER_CREATION:
        for entity in entities:
            if entity.color_index not in {0, 256}:
                generated_specs.setdefault(entity.color_index, TargetLayerSpec(
                    mode=TargetLayerMode.CREATE, name=f"{request.generated_layer_prefix}{entity.color_index}",
                    color_index=entity.color_index, linetype="Continuous"))
        mapping_by_color.update(generated_specs)
    creates: dict[str, LayerSnapshot] = {}
    changes = []
    for entity in entities:
        if entity.space not in request.spaces or entity.is_xref or (entity.nested and not request.include_nested):
            continue
        spec = request.text_override if entity.carrier is ColorLayerCarrier.TEXT and request.text_override else (
            request.dimension_override if entity.carrier is ColorLayerCarrier.DIMENSION_OR_LEADER and request.dimension_override
            else mapping_by_color.get(entity.color_index))
        if spec is None:
            continue
        source_layer = existing.get(entity.layer.casefold())
        if source_layer is not None and source_layer.is_locked:
            raise ValueError(f"LCD matching entity is on a locked layer: {entity.handle}")
        found = existing.get(spec.name.casefold())
        if spec.mode is TargetLayerMode.EXISTING:
            if found is None or found.is_locked or found.is_xref:
                raise ValueError(f"LCD target layer unavailable: {spec.name}")
            target = found
        else:
            if found is not None:
                raise ValueError(f"LCD create target already exists: {spec.name}")
            target = LayerSnapshot(name=spec.name, color_index=spec.color_index, linetype=spec.linetype)
            creates[target.name.casefold()] = target
        changes.append(EntityLayerChange(handle=entity.handle, expected_layer=entity.layer,
            replacement_layer=target.name, replacement_color_index=256, replacement_linetype="ByLayer"))
    return ColorToLayerBatchPlan(document_id=request.document_id, create_layers=tuple(creates.values()),
                                 changes=tuple(changes), dry_run=request.dry_run)


# LCO -- layer only; entity color and linetype must be preserved.
class ChangeLayerOnlyRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    target_layer: str = Field(min_length=1)
    include_nested: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ChangeLayerOnlyRequest:
        _approval(self.dry_run, self.approval, "LCO")
        return self


def plan_change_layer_only(request: ChangeLayerOnlyRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot]) -> ChangeLayerPlan:
    normalized = ChangeLayerRequest(document_id=request.document_id, target_handles=request.target_handles,
        target_layer=TargetLayerSpec(mode=TargetLayerMode.EXISTING, name=request.target_layer),
        color_policy=EntityPropertyPolicy.PRESERVE, linetype_policy=EntityPropertyPolicy.PRESERVE,
        include_nested=request.include_nested, dry_run=request.dry_run, approval=request.approval)
    plan = plan_change_layer(normalized, layers, entities)
    return plan.model_copy(update={"command_alias": "LCO", "legacy_symbol": "xiChangeLayerOnly"})


# LCS -- "same objects" requires an explicit similarity policy.
class ObjectKind(StrEnum):
    LINE = "line"
    POLYLINE = "polyline"
    TEXT = "text"
    MTEXT = "mtext"
    BLOCK_REFERENCE = "block_reference"
    HATCH = "hatch"
    DIMENSION = "dimension"
    OTHER = "other"


class SimilarLayerObjectSnapshot(LayerEntitySnapshot):
    object_kind: ObjectKind


class SimilarityPolicy(StrEnum):
    OBJECT_KIND = "object_kind"
    BLOCK_NAME = "block_name"
    OBJECT_KIND_AND_LAYER = "object_kind_and_layer"


class SimilarObjectsLayerRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    reference_handle: str = Field(min_length=1)
    similarity_policy: SimilarityPolicy
    target_layer: str = Field(min_length=1)
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    include_nested: bool = False
    property_policy: EntityPropertyPolicy
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SimilarObjectsLayerRequest:
        _approval(self.dry_run, self.approval, "LCS")
        return self


class SimilarObjectsLayerPlan(Batch10Plan):
    command_alias: str = "LCS"
    legacy_symbol: str = "xiLayerChaneSelectObject"
    reference_handle: str
    matched_handles: tuple[str, ...]
    changes: tuple[EntityLayerChange, ...]


def plan_similar_objects_layer(request: SimilarObjectsLayerRequest, layers: Sequence[LayerSnapshot], entities: Sequence[SimilarLayerObjectSnapshot]) -> SimilarObjectsLayerPlan:
    layer_map = _layers(layers)
    target = layer_map.get(request.target_layer.casefold())
    by_handle = _entities(entities)
    reference = by_handle.get(request.reference_handle.casefold())
    if target is None or target.is_locked or target.is_xref or reference is None:
        raise ValueError("LCS reference or target layer is unavailable")
    if request.similarity_policy is SimilarityPolicy.BLOCK_NAME and not reference.block_name:
        raise ValueError("LCS block_name policy requires a block reference name")
    matched = []
    for entity in entities:
        if entity.space not in request.spaces or entity.is_xref or (entity.nested and not request.include_nested):
            continue
        same = entity.object_kind is reference.object_kind
        if request.similarity_policy is SimilarityPolicy.BLOCK_NAME:
            same = bool(entity.block_name and entity.block_name.casefold() == reference.block_name.casefold())
        elif request.similarity_policy is SimilarityPolicy.OBJECT_KIND_AND_LAYER:
            same = same and entity.layer.casefold() == reference.layer.casefold()
        if same:
            source_layer = layer_map.get(entity.layer.casefold())
            if source_layer is not None and source_layer.is_locked:
                raise ValueError(f"LCS matched entity is on a locked layer: {entity.handle}")
            matched.append(entity)
    changes = tuple(EntityLayerChange(handle=e.handle, expected_layer=e.layer, replacement_layer=target.name,
        replacement_color_index=e.color_index if request.property_policy is EntityPropertyPolicy.PRESERVE else 256,
        replacement_linetype=e.linetype if request.property_policy is EntityPropertyPolicy.PRESERVE else "ByLayer")
        for e in matched)
    return SimilarObjectsLayerPlan(document_id=request.document_id, reference_handle=reference.handle,
        matched_handles=tuple(e.handle for e in matched), changes=changes, dry_run=request.dry_run)


# LF/LFF/LFK/LK -- selected entity layers determine protected/target sets.
class LayerSetRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    selected_entity_handles: tuple[str, ...] = Field(min_length=1)
    xref_layer_policy: str = Field(default="skip", pattern="^(skip|error)$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LayerSetRequest:
        _unique(self.selected_entity_handles, "selected_entity_handles")
        _approval(self.dry_run, self.approval, "LF/LFF/LFK/LK")
        return self


class LayerProtectionChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    layer: str
    expected_frozen: bool
    replacement_frozen: bool
    expected_locked: bool
    replacement_locked: bool


class LayerProtectionPlan(Batch10Plan):
    changes: tuple[LayerProtectionChange, ...]


def plan_layer_protection(request: LayerSetRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot], *, alias: str) -> LayerProtectionPlan:
    if alias not in {"LF", "LFF", "LFK", "LK"}:
        raise ValueError("alias must be LF, LFF, LFK or LK")
    by_handle = _entities(entities)
    selected_layers = set()
    for handle in request.selected_entity_handles:
        entity = by_handle.get(handle.casefold())
        if entity is None:
            raise ValueError(f"entity not found: {handle}")
        selected_layers.add(entity.layer.casefold())
    changes = []
    for layer in layers:
        is_selected = layer.name.casefold() in selected_layers
        if layer.is_xref:
            if request.xref_layer_policy == "error":
                raise ValueError(f"xref layer in scope: {layer.name}")
            continue
        freeze = (is_selected if alias == "LF" else not is_selected) if alias in {"LF", "LFF"} else layer.is_frozen
        lock = (not is_selected if alias == "LFK" else is_selected) if alias in {"LFK", "LK"} else layer.is_locked
        if alias == "LFF" and layer.is_current:
            freeze = False
        if freeze and layer.is_current:
            raise ValueError(f"cannot freeze current layer: {layer.name}")
        if freeze != layer.is_frozen or lock != layer.is_locked:
            changes.append(LayerProtectionChange(layer=layer.name, expected_frozen=layer.is_frozen,
                replacement_frozen=freeze, expected_locked=layer.is_locked, replacement_locked=lock))
    symbols = {"LF": "xiSelFreeze", "LFF": "xiSelLayerFreeze", "LFK": "xiSelLayerLock", "LK": "xiSelLock"}
    return LayerProtectionPlan(command_alias=alias, legacy_symbol=symbols[alias], document_id=request.document_id,
                               changes=tuple(changes), dry_run=request.dry_run)


# LLC/LOC -- "selected color" source is explicit: layer color or selected entity color.
class ColorSource(StrEnum):
    LAYER_COLOR = "layer_color"
    ENTITY_COLOR = "entity_color"


class ColorLayerStateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    color_indices: tuple[int, ...] = Field(min_length=1)
    color_source: ColorSource
    current_layer_policy: str = Field(default="keep_on", pattern="^(keep_on|error)$")
    include_xref_layers: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ColorLayerStateRequest:
        if len(set(self.color_indices)) != len(self.color_indices) or any(c < 1 or c > 255 for c in self.color_indices):
            raise ValueError("color_indices must be unique ACI values")
        _approval(self.dry_run, self.approval, "LLC/LOC")
        return self


class ColorLayerStatePlan(Batch10Plan):
    matched_layers: tuple[str, ...]
    changes: tuple[LayerStateChange, ...]


def plan_color_layer_state(request: ColorLayerStateRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot], *, alias: str) -> ColorLayerStatePlan:
    if alias not in {"LLC", "LOC"}:
        raise ValueError("alias must be LLC or LOC")
    colors = set(request.color_indices)
    matched = {layer.name.casefold() for layer in layers if layer.color_index in colors}
    if request.color_source is ColorSource.ENTITY_COLOR:
        entity_layers = {e.layer.casefold() for e in entities if e.color_index in colors}
        matched = entity_layers
    changes = []
    for layer in layers:
        if layer.is_xref and not request.include_xref_layers:
            continue
        is_match = layer.name.casefold() in matched
        desired = not is_match if alias == "LLC" else is_match
        if layer.is_current and not desired:
            if request.current_layer_policy == "error":
                raise ValueError("color operation would turn off current layer")
            desired = True
        if layer.is_on != desired:
            changes.append(LayerStateChange(layer=layer.name, expected_on=layer.is_on, replacement_on=desired,
                expected_frozen=layer.is_frozen, replacement_frozen=layer.is_frozen))
    symbols = {"LLC": "xiLayerOffColor", "LOC": "xiLayerOnColor"}
    return ColorLayerStatePlan(command_alias=alias, legacy_symbol=symbols[alias], document_id=request.document_id,
        matched_layers=tuple(layer.name for layer in layers if layer.name.casefold() in matched),
        changes=tuple(changes), dry_run=request.dry_run)


# LOS -- recovered DCL independently selects off/frozen/locked states to activate.
class ActivateLayersRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_layers: tuple[str, ...] = Field(min_length=1)
    turn_on: bool
    thaw: bool
    unlock: bool
    include_xref_layers: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ActivateLayersRequest:
        _unique(self.target_layers, "target_layers")
        if not any((self.turn_on, self.thaw, self.unlock)):
            raise ValueError("LOS must activate at least one layer property")
        _approval(self.dry_run, self.approval, "LOS")
        return self


class ActivateLayerChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    layer: str
    expected_on: bool
    replacement_on: bool
    expected_frozen: bool
    replacement_frozen: bool
    expected_locked: bool
    replacement_locked: bool


class ActivateLayersPlan(Batch10Plan):
    command_alias: str = "LOS"
    legacy_symbol: str = "xiLayerOnSelect"
    changes: tuple[ActivateLayerChange, ...]


def plan_activate_layers(request: ActivateLayersRequest, layers: Sequence[LayerSnapshot]) -> ActivateLayersPlan:
    by_name = _layers(layers)
    changes = []
    for name in request.target_layers:
        layer = by_name.get(name.casefold())
        if layer is None or (layer.is_xref and not request.include_xref_layers):
            raise ValueError(f"LOS layer unavailable: {name}")
        changes.append(ActivateLayerChange(layer=layer.name, expected_on=layer.is_on,
            replacement_on=True if request.turn_on else layer.is_on, expected_frozen=layer.is_frozen,
            replacement_frozen=False if request.thaw else layer.is_frozen, expected_locked=layer.is_locked,
            replacement_locked=False if request.unlock else layer.is_locked))
    return ActivateLayersPlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


# LP -- recovered DCL options are normalized into explicit patches and entity-property modes.
class LayerPropertyPatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    is_on: bool | None = None
    is_frozen: bool | None = None
    is_locked: bool | None = None
    plottable: bool | None = None
    viewport_frozen: bool | None = None
    color_index: int | None = Field(default=None, ge=1, le=255)
    linetype: str | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> LayerPropertyPatch:
        if all(value is None for value in (self.is_on, self.is_frozen, self.is_locked, self.plottable,
                                            self.viewport_frozen, self.color_index, self.linetype)):
            raise ValueError("LP layer patch must change at least one property")
        return self


class LayerPropertyMode(StrEnum):
    LAYER_ONLY = "layer_only"
    TO_BY_LAYER = "to_by_layer"
    FROM_BY_LAYER = "from_by_layer"


class LayerPropertyRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_layers: tuple[str, ...] = Field(min_length=1)
    patch: LayerPropertyPatch | None = None
    mode: LayerPropertyMode
    include_nested: bool = False
    change_entity_color: bool = False
    change_entity_linetype: bool = False
    byblock_color_index: int | None = Field(default=None, ge=1, le=255)
    merge_target_layer: str | None = None
    purge_after_merge: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LayerPropertyRequest:
        _unique(self.target_layers, "target_layers")
        if self.mode is LayerPropertyMode.LAYER_ONLY and self.patch is None:
            raise ValueError("LP layer_only mode requires patch")
        if self.mode is not LayerPropertyMode.LAYER_ONLY and not (self.change_entity_color or self.change_entity_linetype):
            raise ValueError("LP entity-property mode requires a selected property")
        if self.purge_after_merge and not self.merge_target_layer:
            raise ValueError("LP purge_after_merge requires merge_target_layer")
        _approval(self.dry_run, self.approval, "LP")
        return self


class LayerPropertyChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    layer: str
    patch: LayerPropertyPatch


class EntityPropertyChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    replacement_color_index: int
    replacement_linetype: str


class LayerPropertyPlan(Batch10Plan):
    command_alias: str = "LP"
    legacy_symbol: str = "xiLayerProperty"
    layer_changes: tuple[LayerPropertyChange, ...]
    entity_changes: tuple[EntityPropertyChange, ...]
    merge_target_layer: str | None
    purge_source_layers: tuple[str, ...]


def plan_layer_property(request: LayerPropertyRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot]) -> LayerPropertyPlan:
    by_name = _layers(layers)
    targets = {name.casefold() for name in request.target_layers}
    target_snapshots = []
    for name in request.target_layers:
        layer = by_name.get(name.casefold())
        if layer is None or layer.is_xref:
            raise ValueError(f"LP layer unavailable: {name}")
        if request.patch and layer.is_current and (
            request.patch.is_frozen is True or request.patch.is_on is False
        ):
            raise ValueError("LP cannot turn off or freeze current layer")
        if request.purge_after_merge and (
            layer.is_current or layer.name.casefold() in {"0", "defpoints"}
        ):
            raise ValueError("LP cannot purge current or protected layers")
        target_snapshots.append(layer)
    layer_changes = tuple(LayerPropertyChange(layer=layer.name, patch=request.patch)
                          for layer in target_snapshots) if request.patch else ()
    entity_changes = []
    for entity in entities:
        if entity.layer.casefold() not in targets or entity.is_xref or (entity.nested and not request.include_nested):
            continue
        layer = by_name[entity.layer.casefold()]
        color, linetype = entity.color_index, entity.linetype
        if request.mode is LayerPropertyMode.TO_BY_LAYER:
            color = 256 if request.change_entity_color else color
            linetype = "ByLayer" if request.change_entity_linetype else linetype
        elif request.mode is LayerPropertyMode.FROM_BY_LAYER:
            if request.change_entity_color and color == 256:
                color = layer.color_index
            if request.change_entity_linetype and linetype.casefold() == "bylayer":
                linetype = layer.linetype
            if color == 0 and request.byblock_color_index is not None:
                color = request.byblock_color_index
        entity_changes.append(EntityPropertyChange(handle=entity.handle, replacement_color_index=color,
                                                    replacement_linetype=linetype))
    if request.merge_target_layer:
        merge = by_name.get(request.merge_target_layer.casefold())
        if merge is None or merge.is_xref or merge.is_locked or merge.name.casefold() in targets:
            raise ValueError("LP merge target is unavailable or is also a source")
    if request.purge_after_merge and any(
        entity.layer.casefold() in targets and entity.nested and not request.include_nested
        for entity in entities
    ):
        raise ValueError("LP cannot purge while excluded nested entities remain")
    purge = request.target_layers if request.purge_after_merge else ()
    return LayerPropertyPlan(document_id=request.document_id, layer_changes=layer_changes,
        entity_changes=tuple(entity_changes), merge_target_layer=request.merge_target_layer,
        purge_source_layers=purge, dry_run=request.dry_run)


# LST -- return-only is CAD-free; text/table destinations remain explicit plans.
class LayerListDestination(StrEnum):
    RETURN_ONLY = "return_only"
    TEXT = "text"
    TABLE = "table"


class LayerListSort(StrEnum):
    NAME = "name"
    COLOR_THEN_NAME = "color_then_name"
    ORIGINAL = "original"


class LayerListRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    destination: LayerListDestination
    sort: LayerListSort = LayerListSort.NAME
    include_xref_layers: bool = False
    include_properties: bool = True
    insertion_point: Point3D | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LayerListRequest:
        if self.destination is not LayerListDestination.RETURN_ONLY and self.insertion_point is None:
            raise ValueError("LST drawing destination requires insertion_point")
        if self.destination is not LayerListDestination.RETURN_ONLY:
            _approval(self.dry_run, self.approval, "LST")
        return self


class LayerListRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    color_index: int
    linetype: str
    is_on: bool
    is_frozen: bool
    is_locked: bool


class LayerListPlan(Batch10Plan):
    command_alias: str = "LST"
    legacy_symbol: str = "xiLayerList"
    destination: LayerListDestination
    rows: tuple[LayerListRow, ...]
    rendered_lines: tuple[str, ...]
    insertion_point: Point3D | None


def plan_layer_list(request: LayerListRequest, layers: Sequence[LayerSnapshot]) -> LayerListPlan:
    selected = [layer for layer in layers if request.include_xref_layers or not layer.is_xref]
    if request.sort is LayerListSort.NAME:
        selected.sort(key=lambda layer: layer.name.casefold())
    elif request.sort is LayerListSort.COLOR_THEN_NAME:
        selected.sort(key=lambda layer: (layer.color_index, layer.name.casefold()))
    rows = tuple(LayerListRow(name=layer.name, color_index=layer.color_index, linetype=layer.linetype,
        is_on=layer.is_on, is_frozen=layer.is_frozen, is_locked=layer.is_locked) for layer in selected)
    rendered = tuple((f"{row.name}\t{row.color_index}\t{row.linetype}\t"
                      f"{'on' if row.is_on else 'off'}\t{'frozen' if row.is_frozen else 'thawed'}\t"
                      f"{'locked' if row.is_locked else 'unlocked'}") if request.include_properties else row.name
                     for row in rows)
    return LayerListPlan(document_id=request.document_id, destination=request.destination, rows=rows,
                         rendered_lines=rendered, insertion_point=request.insertion_point, dry_run=request.dry_run)


def register_headless_core_batch10_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(title="xiCAD Headless Core Batch 10 Planner", readOnlyHint=True,
                                destructiveHint=False, idempotentHint=True, openWorldHint=False)

    @mcp.tool(name="xicad_plan_lcd", annotations=read_only)
    def mcp_plan_lcd(request: ColorToLayerBatchRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[ColorLayerObjectSnapshot, ...]) -> ColorToLayerBatchPlan:
        return plan_color_to_layer_batch(request, layers, entities)

    @mcp.tool(name="xicad_plan_lco", annotations=read_only)
    def mcp_plan_lco(request: ChangeLayerOnlyRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> ChangeLayerPlan:
        return plan_change_layer_only(request, layers, entities)

    @mcp.tool(name="xicad_plan_lcs", annotations=read_only)
    def mcp_plan_lcs(request: SimilarObjectsLayerRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[SimilarLayerObjectSnapshot, ...]) -> SimilarObjectsLayerPlan:
        return plan_similar_objects_layer(request, layers, entities)

    @mcp.tool(name="xicad_plan_lf", annotations=read_only)
    def mcp_plan_lf(request: LayerSetRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> LayerProtectionPlan:
        return plan_layer_protection(request, layers, entities, alias="LF")

    @mcp.tool(name="xicad_plan_lff", annotations=read_only)
    def mcp_plan_lff(request: LayerSetRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> LayerProtectionPlan:
        return plan_layer_protection(request, layers, entities, alias="LFF")

    @mcp.tool(name="xicad_plan_lfk", annotations=read_only)
    def mcp_plan_lfk(request: LayerSetRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> LayerProtectionPlan:
        return plan_layer_protection(request, layers, entities, alias="LFK")

    @mcp.tool(name="xicad_plan_lk", annotations=read_only)
    def mcp_plan_lk(request: LayerSetRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> LayerProtectionPlan:
        return plan_layer_protection(request, layers, entities, alias="LK")

    @mcp.tool(name="xicad_plan_llc", annotations=read_only)
    def mcp_plan_llc(request: ColorLayerStateRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> ColorLayerStatePlan:
        return plan_color_layer_state(request, layers, entities, alias="LLC")

    @mcp.tool(name="xicad_plan_loc", annotations=read_only)
    def mcp_plan_loc(request: ColorLayerStateRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> ColorLayerStatePlan:
        return plan_color_layer_state(request, layers, entities, alias="LOC")

    @mcp.tool(name="xicad_plan_los", annotations=read_only)
    def mcp_plan_los(request: ActivateLayersRequest, layers: tuple[LayerSnapshot, ...]) -> ActivateLayersPlan:
        return plan_activate_layers(request, layers)

    @mcp.tool(name="xicad_plan_lp", annotations=read_only)
    def mcp_plan_lp(request: LayerPropertyRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> LayerPropertyPlan:
        return plan_layer_property(request, layers, entities)

    @mcp.tool(name="xicad_plan_lst", annotations=read_only)
    def mcp_plan_lst(request: LayerListRequest, layers: tuple[LayerSnapshot, ...]) -> LayerListPlan:
        return plan_layer_list(request, layers)
