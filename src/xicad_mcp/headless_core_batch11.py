from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch9 import LayerEntitySnapshot, LayerSnapshot, LayerStateChange


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval")


def _unique(values: Sequence[str], name: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{name} must be unique")


def _layer_map(layers: Sequence[LayerSnapshot]) -> dict[str, LayerSnapshot]:
    result = {layer.name.casefold(): layer for layer in layers}
    if len(result) != len(layers):
        raise ValueError("layer names must be unique")
    return result


class Batch11Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


# LT/LTG/LU/LUK
class AllLayerStateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    include_xref_layers: bool = False
    current_layer_policy: str = Field(default="keep_on", pattern="^(keep_on|error)$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> AllLayerStateRequest:
        _approval(self.dry_run, self.approval, "LT/LTG/LUK")
        return self


class SelectedLayerUnlockRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    selected_entity_handles: tuple[str, ...] = Field(min_length=1)
    xref_layer_policy: str = Field(default="skip", pattern="^(skip|error)$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SelectedLayerUnlockRequest:
        _unique(self.selected_entity_handles, "selected_entity_handles")
        _approval(self.dry_run, self.approval, "LU")
        return self


class LayerLockChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    layer: str
    expected_locked: bool
    replacement_locked: bool


class LayerStatePlan(Batch11Plan):
    on_freeze_changes: tuple[LayerStateChange, ...] = ()
    lock_changes: tuple[LayerLockChange, ...] = ()


def plan_all_layers_thaw(request: AllLayerStateRequest, layers: Sequence[LayerSnapshot]) -> LayerStatePlan:
    changes = tuple(LayerStateChange(layer=layer.name, expected_on=layer.is_on, replacement_on=layer.is_on,
        expected_frozen=True, replacement_frozen=False) for layer in layers
        if layer.is_frozen and (request.include_xref_layers or not layer.is_xref))
    return LayerStatePlan(command_alias="LT", legacy_symbol="xiLayerThaw", document_id=request.document_id,
                          on_freeze_changes=changes, dry_run=request.dry_run)


def plan_toggle_layer_on_off(request: AllLayerStateRequest, layers: Sequence[LayerSnapshot]) -> LayerStatePlan:
    changes = []
    for layer in layers:
        if layer.is_xref and not request.include_xref_layers:
            continue
        desired = not layer.is_on
        if layer.is_current and not desired:
            if request.current_layer_policy == "error":
                raise ValueError("LTG would turn off current layer")
            desired = True
        if desired != layer.is_on:
            changes.append(LayerStateChange(layer=layer.name, expected_on=layer.is_on, replacement_on=desired,
                expected_frozen=layer.is_frozen, replacement_frozen=layer.is_frozen))
    return LayerStatePlan(command_alias="LTG", legacy_symbol="xiLayerOnOffToggle", document_id=request.document_id,
                          on_freeze_changes=tuple(changes), dry_run=request.dry_run)


def plan_selected_layers_unlock(request: SelectedLayerUnlockRequest, layers: Sequence[LayerSnapshot], entities: Sequence[LayerEntitySnapshot]) -> LayerStatePlan:
    by_handle = {entity.handle.casefold(): entity for entity in entities}
    selected = set()
    for handle in request.selected_entity_handles:
        entity = by_handle.get(handle.casefold())
        if entity is None:
            raise ValueError(f"entity not found: {handle}")
        selected.add(entity.layer.casefold())
    changes = []
    for layer in layers:
        if layer.name.casefold() not in selected:
            continue
        if layer.is_xref:
            if request.xref_layer_policy == "error":
                raise ValueError(f"xref layer selected: {layer.name}")
            continue
        if layer.is_locked:
            changes.append(LayerLockChange(layer=layer.name, expected_locked=True, replacement_locked=False))
    return LayerStatePlan(command_alias="LU", legacy_symbol="xiSelUnLock", document_id=request.document_id,
                          lock_changes=tuple(changes), dry_run=request.dry_run)


def plan_all_layers_unlock(request: AllLayerStateRequest, layers: Sequence[LayerSnapshot]) -> LayerStatePlan:
    changes = tuple(LayerLockChange(layer=layer.name, expected_locked=True, replacement_locked=False)
                    for layer in layers if layer.is_locked and (request.include_xref_layers or not layer.is_xref))
    return LayerStatePlan(command_alias="LUK", legacy_symbol="xiLayerUnlock", document_id=request.document_id,
                          lock_changes=changes, dry_run=request.dry_run)


# Dimension snapshots normalize CAD geometry and scale values before planning.
class DimensionKind(StrEnum):
    ALIGNED = "aligned"
    ROTATED = "rotated"
    ANGULAR = "angular"
    ARC_LENGTH = "arc_length"
    RADIAL = "radial"
    DIAMETER = "diameter"
    ORDINATE = "ordinate"


class DimensionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    kind: DimensionKind
    layer: str = Field(min_length=1)
    style: str = Field(min_length=1)
    measurement: float
    text_override: str = ""
    text_position: Point3D
    default_text_position: Point3D
    dimension_line_point: Point3D
    first_extension_origin: Point3D
    second_extension_origin: Point3D
    first_extension_suppressed: bool = False
    second_extension_suppressed: bool = False
    first_extension_length: float = Field(ge=0)
    second_extension_length: float = Field(ge=0)
    dimscale: float = Field(gt=0)
    ltscale: float = Field(gt=0)
    object_scale: float = Field(gt=0)
    locked_layer: bool = False
    is_xref: bool = False


def _dimensions(handles: Sequence[str], dimensions: Sequence[DimensionSnapshot]) -> tuple[DimensionSnapshot, ...]:
    _unique(handles, "target_handles")
    by_handle = {dimension.handle.casefold(): dimension for dimension in dimensions}
    if len(by_handle) != len(dimensions):
        raise ValueError("dimension handles must be unique")
    result = []
    for handle in handles:
        dimension = by_handle.get(handle.casefold())
        if dimension is None:
            raise ValueError(f"dimension not found: {handle}")
        if dimension.is_xref or dimension.locked_layer:
            raise ValueError(f"dimension cannot be mutated: {handle}")
        result.append(dimension)
    return tuple(result)


# CDE
class DimensionTextMode(StrEnum):
    SET_OVERRIDE = "set_override"
    PREFIX_MEASUREMENT = "prefix_measurement"
    SUFFIX_MEASUREMENT = "suffix_measurement"
    RESET_TO_MEASUREMENT = "reset_to_measurement"


class DimensionTextEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: DimensionTextMode
    text: str = ""
    measurement_token: str = "<>"
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionTextEditRequest:
        if self.mode is not DimensionTextMode.RESET_TO_MEASUREMENT and not self.text:
            raise ValueError("CDE selected mode requires text")
        _approval(self.dry_run, self.approval, "CDE")
        return self


class DimensionTextChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_override: str
    replacement_override: str


class DimensionTextPlan(Batch11Plan):
    command_alias: str = "CDE"
    legacy_symbol: str = "xiDedit"
    changes: tuple[DimensionTextChange, ...]


def plan_dimension_text_edit(request: DimensionTextEditRequest, dimensions: Sequence[DimensionSnapshot]) -> DimensionTextPlan:
    selected = _dimensions(request.target_handles, dimensions)
    changes = []
    for dimension in selected:
        replacement = ""
        if request.mode is DimensionTextMode.SET_OVERRIDE:
            replacement = request.text
        elif request.mode is DimensionTextMode.PREFIX_MEASUREMENT:
            replacement = request.text + request.measurement_token
        elif request.mode is DimensionTextMode.SUFFIX_MEASUREMENT:
            replacement = request.measurement_token + request.text
        changes.append(DimensionTextChange(handle=dimension.handle, expected_override=dimension.text_override,
                                           replacement_override=replacement))
    return DimensionTextPlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


# DCV
class LinearDimensionKind(StrEnum):
    ALIGNED = "aligned"
    ROTATED = "rotated"


class DimensionSourceDisposition(StrEnum):
    REPLACE = "replace"
    PRESERVE = "preserve"


class DimensionConvertRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    target_kind: LinearDimensionKind
    rotation_degrees: float | None = None
    source_disposition: DimensionSourceDisposition
    preserve_text_override: bool
    preserve_style: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionConvertRequest:
        if self.target_kind is LinearDimensionKind.ROTATED and self.rotation_degrees is None:
            raise ValueError("DCV rotated target requires rotation_degrees")
        if self.target_kind is LinearDimensionKind.ALIGNED and self.rotation_degrees is not None:
            raise ValueError("DCV aligned target does not accept rotation_degrees")
        if self.rotation_degrees is not None and not isfinite(self.rotation_degrees):
            raise ValueError("rotation_degrees must be finite")
        _approval(self.dry_run, self.approval, "DCV")
        return self


class LinearDimensionCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    target_kind: LinearDimensionKind
    first_extension_origin: Point3D
    second_extension_origin: Point3D
    dimension_line_point: Point3D
    rotation_degrees: float | None
    style: str | None
    text_override: str
    erase_source: bool


class DimensionConvertPlan(Batch11Plan):
    command_alias: str = "DCV"
    legacy_symbol: str = "xiDimConvert"
    creates: tuple[LinearDimensionCreate, ...]


def plan_dimension_convert(request: DimensionConvertRequest, dimensions: Sequence[DimensionSnapshot]) -> DimensionConvertPlan:
    selected = _dimensions(request.target_handles, dimensions)
    creates = tuple(LinearDimensionCreate(source_handle=d.handle, target_kind=request.target_kind,
        first_extension_origin=d.first_extension_origin, second_extension_origin=d.second_extension_origin,
        dimension_line_point=d.dimension_line_point, rotation_degrees=request.rotation_degrees,
        style=d.style if request.preserve_style else None, text_override=d.text_override if request.preserve_text_override else "",
        erase_source=request.source_disposition is DimensionSourceDisposition.REPLACE) for d in selected)
    return DimensionConvertPlan(document_id=request.document_id, creates=creates, dry_run=request.dry_run)


# DDT
class ExtensionLineTarget(StrEnum):
    FIRST = "first"
    SECOND = "second"
    BOTH = "both"


class SuppressionOperation(StrEnum):
    HIDE = "hide"
    SHOW = "show"
    TOGGLE = "toggle"


class DimensionExtensionToggleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    target: ExtensionLineTarget
    operation: SuppressionOperation
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionExtensionToggleRequest:
        _approval(self.dry_run, self.approval, "DDT")
        return self


class ExtensionSuppressionChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_first: bool
    replacement_first: bool
    expected_second: bool
    replacement_second: bool


class ExtensionSuppressionPlan(Batch11Plan):
    command_alias: str = "DDT"
    legacy_symbol: str = "xiDimDTogle"
    changes: tuple[ExtensionSuppressionChange, ...]


def plan_dimension_extension_toggle(request: DimensionExtensionToggleRequest, dimensions: Sequence[DimensionSnapshot]) -> ExtensionSuppressionPlan:
    selected = _dimensions(request.target_handles, dimensions)
    changes = []
    for d in selected:
        first, second = d.first_extension_suppressed, d.second_extension_suppressed
        value = True if request.operation is SuppressionOperation.HIDE else False
        new_first = (not first if request.operation is SuppressionOperation.TOGGLE else value) if request.target in {ExtensionLineTarget.FIRST, ExtensionLineTarget.BOTH} else first
        new_second = (not second if request.operation is SuppressionOperation.TOGGLE else value) if request.target in {ExtensionLineTarget.SECOND, ExtensionLineTarget.BOTH} else second
        changes.append(ExtensionSuppressionChange(handle=d.handle, expected_first=first, replacement_first=new_first,
                                                  expected_second=second, replacement_second=new_second))
    return ExtensionSuppressionPlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


# DE -- recovered DCL gap source and repeat policy.
class ContinueGapSource(StrEnum):
    STYLE_SETTING = "style_setting"
    SCREEN_DISTANCE = "screen_distance"
    EXPLICIT_DIM_SCALE_FACTOR = "explicit_dim_scale_factor"


class ContinueDimensionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handle: str = Field(min_length=1)
    continuation_points: tuple[Point3D, ...] = Field(min_length=1)
    gap_source: ContinueGapSource
    style_gap_value: float | None = Field(default=None, gt=0)
    screen_distance: float | None = Field(default=None, gt=0)
    explicit_gap_factor: float | None = Field(default=None, gt=0)
    repeat_after_input: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ContinueDimensionRequest:
        required = {ContinueGapSource.STYLE_SETTING: self.style_gap_value,
                    ContinueGapSource.SCREEN_DISTANCE: self.screen_distance,
                    ContinueGapSource.EXPLICIT_DIM_SCALE_FACTOR: self.explicit_gap_factor}[self.gap_source]
        if required is None:
            raise ValueError("DE selected gap source requires its value")
        _approval(self.dry_run, self.approval, "DE")
        return self


class ContinuedDimensionCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    previous_handle: str
    first_extension_origin: Point3D
    second_extension_origin: Point3D
    dimension_line_point: Point3D
    gap: float = Field(gt=0)


class ContinueDimensionPlan(Batch11Plan):
    command_alias: str = "DE"
    legacy_symbol: str = "xiConDim"
    creates: tuple[ContinuedDimensionCreate, ...]
    repeat_after_input: bool


def plan_continue_dimension(request: ContinueDimensionRequest, dimensions: Sequence[DimensionSnapshot]) -> ContinueDimensionPlan:
    source = _dimensions((request.source_handle,), dimensions)[0]
    if source.kind not in {DimensionKind.ALIGNED, DimensionKind.ROTATED}:
        raise ValueError("DE source must be a linear dimension")
    gap = request.style_gap_value if request.gap_source is ContinueGapSource.STYLE_SETTING else (
        request.screen_distance if request.gap_source is ContinueGapSource.SCREEN_DISTANCE else request.explicit_gap_factor * source.dimscale)
    previous_origin = source.second_extension_origin
    creates = []
    previous_handle = source.handle
    for index, point in enumerate(request.continuation_points):
        creates.append(ContinuedDimensionCreate(previous_handle=previous_handle, first_extension_origin=previous_origin,
            second_extension_origin=point, dimension_line_point=source.dimension_line_point, gap=gap))
        previous_origin = point
        previous_handle = f"$planned:{index}"
    return ContinueDimensionPlan(document_id=request.document_id, creates=tuple(creates),
                                 repeat_after_input=request.repeat_after_input, dry_run=request.dry_run)


# DG
class DimensionScaleBasis(StrEnum):
    LINE_SCALE = "line_scale"
    DIMENSION_SCALE = "dimension_scale"
    OBJECT_SCALE = "object_scale"


class BaselineSide(StrEnum):
    OUTSIDE = "outside"
    INSIDE = "inside"


class DimensionGapRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    ordered_handles: tuple[str, ...] = Field(min_length=2)
    gap_factor: float = Field(gt=0)
    scale_basis: DimensionScaleBasis
    baseline_side: BaselineSide
    unit_offset_direction: Point3D
    repeat_after_input: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionGapRequest:
        _unique(self.ordered_handles, "ordered_handles")
        length = (self.unit_offset_direction.x**2 + self.unit_offset_direction.y**2 + self.unit_offset_direction.z**2) ** 0.5
        if abs(length - 1) > 1e-6:
            raise ValueError("DG unit_offset_direction must be normalized")
        _approval(self.dry_run, self.approval, "DG")
        return self


class DimensionLineMove(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_point: Point3D
    replacement_point: Point3D


class DimensionGapPlan(Batch11Plan):
    command_alias: str = "DG"
    legacy_symbol: str = "xiDimGap"
    moves: tuple[DimensionLineMove, ...]
    repeat_after_input: bool


def plan_dimension_gap(request: DimensionGapRequest, dimensions: Sequence[DimensionSnapshot]) -> DimensionGapPlan:
    selected = _dimensions(request.ordered_handles, dimensions)
    baseline = selected[0] if request.baseline_side is BaselineSide.INSIDE else selected[-1]
    moves = []
    for index, dimension in enumerate(selected):
        scale = {DimensionScaleBasis.LINE_SCALE: dimension.ltscale,
                 DimensionScaleBasis.DIMENSION_SCALE: dimension.dimscale,
                 DimensionScaleBasis.OBJECT_SCALE: dimension.object_scale}[request.scale_basis]
        distance = abs(index - selected.index(baseline)) * request.gap_factor * scale
        point = Point3D(x=baseline.dimension_line_point.x + request.unit_offset_direction.x * distance,
                        y=baseline.dimension_line_point.y + request.unit_offset_direction.y * distance,
                        z=baseline.dimension_line_point.z + request.unit_offset_direction.z * distance)
        moves.append(DimensionLineMove(handle=dimension.handle, expected_point=dimension.dimension_line_point,
                                       replacement_point=point))
    return DimensionGapPlan(document_id=request.document_id, moves=tuple(moves),
                            repeat_after_input=request.repeat_after_input, dry_run=request.dry_run)


# DH
class DimensionTextHomeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    reset_text_override: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionTextHomeRequest:
        _approval(self.dry_run, self.approval, "DH")
        return self


class DimensionTextHomeChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_position: Point3D
    replacement_position: Point3D
    expected_override: str
    replacement_override: str


class DimensionTextHomePlan(Batch11Plan):
    command_alias: str = "DH"
    legacy_symbol: str = "xiDimTextHome"
    changes: tuple[DimensionTextHomeChange, ...]


def plan_dimension_text_home(request: DimensionTextHomeRequest, dimensions: Sequence[DimensionSnapshot]) -> DimensionTextHomePlan:
    selected = _dimensions(request.target_handles, dimensions)
    changes = tuple(DimensionTextHomeChange(handle=d.handle, expected_position=d.text_position,
        replacement_position=d.default_text_position, expected_override=d.text_override,
        replacement_override="" if request.reset_text_override else d.text_override) for d in selected)
    return DimensionTextHomePlan(document_id=request.document_id, changes=changes, dry_run=request.dry_run)


# DLA / DLL
class ExtensionArrangeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    target: ExtensionLineTarget
    first_alignment_point: Point3D | None = None
    second_alignment_point: Point3D | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ExtensionArrangeRequest:
        if self.target in {ExtensionLineTarget.FIRST, ExtensionLineTarget.BOTH} and self.first_alignment_point is None:
            raise ValueError("DLA first extension alignment point is required")
        if self.target in {ExtensionLineTarget.SECOND, ExtensionLineTarget.BOTH} and self.second_alignment_point is None:
            raise ValueError("DLA second extension alignment point is required")
        _approval(self.dry_run, self.approval, "DLA")
        return self


class ExtensionOriginChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_first: Point3D
    replacement_first: Point3D
    expected_second: Point3D
    replacement_second: Point3D


class ExtensionArrangePlan(Batch11Plan):
    command_alias: str = "DLA"
    legacy_symbol: str = "xiDimsExLineArrange"
    changes: tuple[ExtensionOriginChange, ...]


def plan_extension_arrange(request: ExtensionArrangeRequest, dimensions: Sequence[DimensionSnapshot]) -> ExtensionArrangePlan:
    selected = _dimensions(request.target_handles, dimensions)
    changes = tuple(ExtensionOriginChange(handle=d.handle, expected_first=d.first_extension_origin,
        replacement_first=request.first_alignment_point if request.target in {ExtensionLineTarget.FIRST, ExtensionLineTarget.BOTH} else d.first_extension_origin,
        expected_second=d.second_extension_origin,
        replacement_second=request.second_alignment_point if request.target in {ExtensionLineTarget.SECOND, ExtensionLineTarget.BOTH} else d.second_extension_origin) for d in selected)
    return ExtensionArrangePlan(document_id=request.document_id, changes=changes, dry_run=request.dry_run)


class ExtensionLengthRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    target: ExtensionLineTarget
    length_factor: float = Field(gt=0)
    scale_basis: DimensionScaleBasis
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ExtensionLengthRequest:
        _approval(self.dry_run, self.approval, "DLL")
        return self


class ExtensionLengthChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_first: float
    replacement_first: float
    expected_second: float
    replacement_second: float


class ExtensionLengthPlan(Batch11Plan):
    command_alias: str = "DLL"
    legacy_symbol: str = "xiDimsExLineLength"
    changes: tuple[ExtensionLengthChange, ...]


def plan_extension_length(request: ExtensionLengthRequest, dimensions: Sequence[DimensionSnapshot]) -> ExtensionLengthPlan:
    selected = _dimensions(request.target_handles, dimensions)
    changes = []
    for d in selected:
        scale = {DimensionScaleBasis.LINE_SCALE: d.ltscale, DimensionScaleBasis.DIMENSION_SCALE: d.dimscale,
                 DimensionScaleBasis.OBJECT_SCALE: d.object_scale}[request.scale_basis]
        length = request.length_factor * scale
        changes.append(ExtensionLengthChange(handle=d.handle, expected_first=d.first_extension_length,
            replacement_first=length if request.target in {ExtensionLineTarget.FIRST, ExtensionLineTarget.BOTH} else d.first_extension_length,
            expected_second=d.second_extension_length,
            replacement_second=length if request.target in {ExtensionLineTarget.SECOND, ExtensionLineTarget.BOTH} else d.second_extension_length))
    return ExtensionLengthPlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


def register_headless_core_batch11_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(title="xiCAD Headless Core Batch 11 Planner", readOnlyHint=True,
                                destructiveHint=False, idempotentHint=True, openWorldHint=False)

    @mcp.tool(name="xicad_plan_lt", annotations=read_only)
    def mcp_plan_lt(request: AllLayerStateRequest, layers: tuple[LayerSnapshot, ...]) -> LayerStatePlan:
        return plan_all_layers_thaw(request, layers)

    @mcp.tool(name="xicad_plan_ltg", annotations=read_only)
    def mcp_plan_ltg(request: AllLayerStateRequest, layers: tuple[LayerSnapshot, ...]) -> LayerStatePlan:
        return plan_toggle_layer_on_off(request, layers)

    @mcp.tool(name="xicad_plan_lu", annotations=read_only)
    def mcp_plan_lu(request: SelectedLayerUnlockRequest, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...]) -> LayerStatePlan:
        return plan_selected_layers_unlock(request, layers, entities)

    @mcp.tool(name="xicad_plan_luk", annotations=read_only)
    def mcp_plan_luk(request: AllLayerStateRequest, layers: tuple[LayerSnapshot, ...]) -> LayerStatePlan:
        return plan_all_layers_unlock(request, layers)

    @mcp.tool(name="xicad_plan_cde", annotations=read_only)
    def mcp_plan_cde(request: DimensionTextEditRequest, dimensions: tuple[DimensionSnapshot, ...]) -> DimensionTextPlan:
        return plan_dimension_text_edit(request, dimensions)

    @mcp.tool(name="xicad_plan_dcv", annotations=read_only)
    def mcp_plan_dcv(request: DimensionConvertRequest, dimensions: tuple[DimensionSnapshot, ...]) -> DimensionConvertPlan:
        return plan_dimension_convert(request, dimensions)

    @mcp.tool(name="xicad_plan_ddt", annotations=read_only)
    def mcp_plan_ddt(request: DimensionExtensionToggleRequest, dimensions: tuple[DimensionSnapshot, ...]) -> ExtensionSuppressionPlan:
        return plan_dimension_extension_toggle(request, dimensions)

    @mcp.tool(name="xicad_plan_de", annotations=read_only)
    def mcp_plan_de(request: ContinueDimensionRequest, dimensions: tuple[DimensionSnapshot, ...]) -> ContinueDimensionPlan:
        return plan_continue_dimension(request, dimensions)

    @mcp.tool(name="xicad_plan_dg", annotations=read_only)
    def mcp_plan_dg(request: DimensionGapRequest, dimensions: tuple[DimensionSnapshot, ...]) -> DimensionGapPlan:
        return plan_dimension_gap(request, dimensions)

    @mcp.tool(name="xicad_plan_dh", annotations=read_only)
    def mcp_plan_dh(request: DimensionTextHomeRequest, dimensions: tuple[DimensionSnapshot, ...]) -> DimensionTextHomePlan:
        return plan_dimension_text_home(request, dimensions)

    @mcp.tool(name="xicad_plan_dla", annotations=read_only)
    def mcp_plan_dla(request: ExtensionArrangeRequest, dimensions: tuple[DimensionSnapshot, ...]) -> ExtensionArrangePlan:
        return plan_extension_arrange(request, dimensions)

    @mcp.tool(name="xicad_plan_dll", annotations=read_only)
    def mcp_plan_dll(request: ExtensionLengthRequest, dimensions: tuple[DimensionSnapshot, ...]) -> ExtensionLengthPlan:
        return plan_extension_length(request, dimensions)
