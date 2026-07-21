from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import dist
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch11 import DimensionSnapshot


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval")


def _unique(values: Sequence[str], name: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{name} must be unique")


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


class Batch12Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class LinearOrientation(StrEnum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    ALIGNED = "aligned"


class DimensionChainMode(StrEnum):
    CHAIN = "chain"
    BASELINE = "baseline"


class DimensionCreateSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str | None = None
    first_point: Point3D
    second_point: Point3D
    dimension_line_point: Point3D
    orientation: LinearOrientation
    style: str


# DPL
class PolylineDimensionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    vertices: tuple[Point3D, ...] = Field(min_length=2)
    closed: bool = False
    locked_layer: bool = False
    is_xref: bool = False


class PolylineVertexPolicy(StrEnum):
    CONSECUTIVE_SEGMENTS = "consecutive_segments"
    HORIZONTAL_AND_VERTICAL_ONLY = "horizontal_and_vertical_only"
    EXPLICIT_PAIRS = "explicit_pairs"


class PolylineDimensionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handle: str = Field(min_length=1)
    vertex_policy: PolylineVertexPolicy
    explicit_pairs: tuple[tuple[int, int], ...] = ()
    orientation: LinearOrientation
    dimension_line_point: Point3D
    style: str = Field(min_length=1)
    include_closing_segment: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> PolylineDimensionRequest:
        if self.vertex_policy is PolylineVertexPolicy.EXPLICIT_PAIRS and not self.explicit_pairs:
            raise ValueError("DPL explicit_pairs policy requires pairs")
        _approval(self.dry_run, self.approval, "DPL")
        return self


class PolylineDimensionPlan(Batch12Plan):
    command_alias: str = "DPL"
    legacy_symbol: str = "xiDimPL"
    creates: tuple[DimensionCreateSpec, ...]


def plan_polyline_dimensions(request: PolylineDimensionRequest, polylines: Sequence[PolylineDimensionSnapshot]) -> PolylineDimensionPlan:
    source = next((polyline for polyline in polylines if polyline.handle.casefold() == request.source_handle.casefold()), None)
    if source is None or source.is_xref or source.locked_layer:
        raise ValueError("DPL source polyline is unavailable")
    count = len(source.vertices)
    if request.vertex_policy is PolylineVertexPolicy.EXPLICIT_PAIRS:
        pairs = request.explicit_pairs
        if any(a < 0 or b < 0 or a >= count or b >= count or a == b for a, b in pairs):
            raise ValueError("DPL explicit pair index is invalid")
    else:
        pairs = tuple((index, index + 1) for index in range(count - 1))
        if source.closed and request.include_closing_segment:
            pairs += ((count - 1, 0),)
        if request.vertex_policy is PolylineVertexPolicy.HORIZONTAL_AND_VERTICAL_ONLY:
            pairs = tuple((a, b) for a, b in pairs if source.vertices[a].x == source.vertices[b].x or source.vertices[a].y == source.vertices[b].y)
    creates = tuple(DimensionCreateSpec(source_handle=source.handle, first_point=source.vertices[a],
        second_point=source.vertices[b], dimension_line_point=request.dimension_line_point,
        orientation=request.orientation, style=request.style) for a, b in pairs)
    return PolylineDimensionPlan(document_id=request.document_id, creates=creates, dry_run=request.dry_run)


# DQ
class QuickDimensionSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    points: tuple[Point3D, ...] = Field(min_length=2)
    locked_layer: bool = False
    is_xref: bool = False


class QuickDimensionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=1)
    chain_mode: DimensionChainMode
    orientation: LinearOrientation
    dimension_line_point: Point3D
    style: str = Field(min_length=1)
    deduplicate_points: bool = True
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> QuickDimensionRequest:
        _unique(self.source_handles, "source_handles")
        _approval(self.dry_run, self.approval, "DQ")
        return self


class QuickDimensionPlan(Batch12Plan):
    command_alias: str = "DQ"
    legacy_symbol: str = "xiQuickDim"
    creates: tuple[DimensionCreateSpec, ...]


def plan_quick_dimensions(request: QuickDimensionRequest, sources: Sequence[QuickDimensionSource]) -> QuickDimensionPlan:
    by_handle = {source.handle.casefold(): source for source in sources}
    points = []
    for handle in request.source_handles:
        source = by_handle.get(handle.casefold())
        if source is None or source.is_xref or source.locked_layer:
            raise ValueError(f"DQ source unavailable: {handle}")
        points.extend(source.points)
    if request.deduplicate_points:
        points = list(dict.fromkeys((point.x, point.y, point.z) for point in points))
        points = [Point3D(x=x, y=y, z=z) for x, y, z in points]
    if len(points) < 2:
        raise ValueError("DQ requires at least two distinct points")
    if request.orientation is LinearOrientation.HORIZONTAL:
        points.sort(key=lambda point: (point.x, point.y, point.z))
    elif request.orientation is LinearOrientation.VERTICAL:
        points.sort(key=lambda point: (point.y, point.x, point.z))
    pairs = ((points[0], point) for point in points[1:]) if request.chain_mode is DimensionChainMode.BASELINE else zip(points, points[1:], strict=False)
    creates = tuple(DimensionCreateSpec(first_point=a, second_point=b,
        dimension_line_point=request.dimension_line_point, orientation=request.orientation, style=request.style) for a, b in pairs)
    return QuickDimensionPlan(document_id=request.document_id, creates=creates, dry_run=request.dry_run)


# DSC -- static description does not identify current-style versus object scope.
class DimensionScaleScope(StrEnum):
    CURRENT_STYLE = "current_style"
    SELECTED_DIMENSIONS = "selected_dimensions"


class DimensionScaleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    scope: DimensionScaleScope
    scale: float = Field(gt=0)
    target_handles: tuple[str, ...] = ()
    current_style: str | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionScaleRequest:
        if self.scope is DimensionScaleScope.CURRENT_STYLE and (not self.current_style or self.target_handles):
            raise ValueError("DSC current_style scope requires only current_style")
        if self.scope is DimensionScaleScope.SELECTED_DIMENSIONS and not self.target_handles:
            raise ValueError("DSC selected scope requires target_handles")
        _approval(self.dry_run, self.approval, "DSC")
        return self


class DimensionScaleChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_scale: float
    replacement_scale: float


class DimensionScalePlan(Batch12Plan):
    command_alias: str = "DSC"
    legacy_symbol: str = "xiDimScale"
    style_scale_change: tuple[str, float] | None
    entity_changes: tuple[DimensionScaleChange, ...]


def plan_dimension_scale(request: DimensionScaleRequest, dimensions: Sequence[DimensionSnapshot]) -> DimensionScalePlan:
    if request.scope is DimensionScaleScope.CURRENT_STYLE:
        return DimensionScalePlan(document_id=request.document_id, style_scale_change=(request.current_style, request.scale),
                                  entity_changes=(), dry_run=request.dry_run)
    selected = _dimensions(request.target_handles, dimensions)
    return DimensionScalePlan(document_id=request.document_id, style_scale_change=None,
        entity_changes=tuple(DimensionScaleChange(handle=d.handle, expected_scale=d.dimscale,
                                                   replacement_scale=request.scale) for d in selected), dry_run=request.dry_run)


# DSE
class DimensionStyleSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    dimscale: float = Field(gt=0)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    arrow_size: float = Field(gt=0)
    extension_offset: float = Field(ge=0)
    baseline_spacing: float = Field(gt=0)
    decimal_places: int = Field(ge=0, le=12)
    suffix: str = ""
    is_xref: bool = False


class DimensionStylePatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dimscale: float | None = Field(default=None, gt=0)
    text_style: str | None = None
    text_height: float | None = Field(default=None, gt=0)
    arrow_size: float | None = Field(default=None, gt=0)
    extension_offset: float | None = Field(default=None, ge=0)
    baseline_spacing: float | None = Field(default=None, gt=0)
    decimal_places: int | None = Field(default=None, ge=0, le=12)
    suffix: str | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> DimensionStylePatch:
        if all(value is None for value in (self.dimscale, self.text_style, self.text_height, self.arrow_size,
                                            self.extension_offset, self.baseline_spacing, self.decimal_places, self.suffix)):
            raise ValueError("DSE patch must change at least one property")
        return self


class DimensionStyleEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_style: str = Field(min_length=1)
    patch: DimensionStylePatch
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionStyleEditRequest:
        _approval(self.dry_run, self.approval, "DSE")
        return self


class DimensionStyleEditPlan(Batch12Plan):
    command_alias: str = "DSE"
    legacy_symbol: str = "xiDimStyleEdit"
    expected_style: DimensionStyleSnapshot
    patch: DimensionStylePatch


def plan_dimension_style_edit(request: DimensionStyleEditRequest, styles: Sequence[DimensionStyleSnapshot]) -> DimensionStyleEditPlan:
    style = next((style for style in styles if style.name.casefold() == request.target_style.casefold()), None)
    if style is None or style.is_xref:
        raise ValueError("DSE target style is unavailable")
    return DimensionStyleEditPlan(document_id=request.document_id, expected_style=style, patch=request.patch,
                                  dry_run=request.dry_run)


# DSM -- recovered DCL.
class DimensionStyleMergeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_styles: tuple[str, ...] = Field(min_length=1)
    target_style: str = Field(min_length=1)
    include_nested: bool
    remove_source_styles: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionStyleMergeRequest:
        _unique(self.source_styles, "source_styles")
        if self.target_style.casefold() in {style.casefold() for style in self.source_styles}:
            raise ValueError("DSM target style cannot be a source")
        _approval(self.dry_run, self.approval, "DSM")
        return self


class DimensionStyleAssignment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_style: str
    replacement_style: str


class DimensionStyleMergePlan(Batch12Plan):
    command_alias: str = "DSM"
    legacy_symbol: str = "xiDimStyleMerge"
    changes: tuple[DimensionStyleAssignment, ...]
    remove_styles: tuple[str, ...]


def plan_dimension_style_merge(request: DimensionStyleMergeRequest, styles: Sequence[DimensionStyleSnapshot], dimensions: Sequence[DimensionSnapshot], nested_handles: tuple[str, ...] = ()) -> DimensionStyleMergePlan:
    available = {style.name.casefold(): style for style in styles if not style.is_xref}
    if request.target_style.casefold() not in available or any(style.casefold() not in available for style in request.source_styles):
        raise ValueError("DSM style is unavailable")
    nested = {handle.casefold() for handle in nested_handles}
    sources = {style.casefold() for style in request.source_styles}
    if any((d.is_xref or d.locked_layer) and d.style.casefold() in sources for d in dimensions):
        raise ValueError("DSM affected dimension is xref-dependent or locked")
    changes = tuple(DimensionStyleAssignment(handle=d.handle, expected_style=d.style, replacement_style=request.target_style)
                    for d in dimensions if d.style.casefold() in sources and (request.include_nested or d.handle.casefold() not in nested))
    if request.remove_source_styles and any(d.style.casefold() in sources and d.handle.casefold() in nested for d in dimensions) and not request.include_nested:
        raise ValueError("DSM cannot remove styles while excluded nested dimensions remain")
    return DimensionStyleMergePlan(document_id=request.document_id, changes=changes,
        remove_styles=request.source_styles if request.remove_source_styles else (), dry_run=request.dry_run)


# DTM
class DimensionTextMoveDirection(StrEnum):
    BELOW = "below"
    SIDE = "side"


class TextCollisionGroup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handles: tuple[str, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_handles(self) -> TextCollisionGroup:
        _unique(self.handles, "collision handles")
        return self


class DimensionTextMoveRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    collision_groups: tuple[TextCollisionGroup, ...] = Field(min_length=1)
    direction: DimensionTextMoveDirection
    offset_factor: float = Field(gt=0)
    unit_direction: Point3D
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionTextMoveRequest:
        length = dist((0, 0, 0), (self.unit_direction.x, self.unit_direction.y, self.unit_direction.z))
        if abs(length - 1) > 1e-6:
            raise ValueError("DTM unit_direction must be normalized")
        _approval(self.dry_run, self.approval, "DTM")
        return self


class DimensionTextPositionChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_position: Point3D
    replacement_position: Point3D


class DimensionTextMovePlan(Batch12Plan):
    command_alias: str = "DTM"
    legacy_symbol: str = "xiDimTextMove"
    direction: DimensionTextMoveDirection
    changes: tuple[DimensionTextPositionChange, ...]


def plan_dimension_text_move(request: DimensionTextMoveRequest, dimensions: Sequence[DimensionSnapshot]) -> DimensionTextMovePlan:
    by_handle = {d.handle.casefold(): d for d in dimensions}
    changes = []
    seen = set()
    for group in request.collision_groups:
        for index, handle in enumerate(group.handles):
            if handle.casefold() in seen:
                raise ValueError("DTM handle appears in multiple collision groups")
            seen.add(handle.casefold())
            d = by_handle.get(handle.casefold())
            if d is None or d.is_xref or d.locked_layer:
                raise ValueError(f"DTM dimension unavailable: {handle}")
            distance_value = index * request.offset_factor * d.dimscale
            point = Point3D(x=d.text_position.x + request.unit_direction.x * distance_value,
                            y=d.text_position.y + request.unit_direction.y * distance_value,
                            z=d.text_position.z + request.unit_direction.z * distance_value)
            changes.append(DimensionTextPositionChange(handle=d.handle, expected_position=d.text_position,
                                                       replacement_position=point))
    return DimensionTextMovePlan(document_id=request.document_id, direction=request.direction,
                                 changes=tuple(changes), dry_run=request.dry_run)


# DTO
class SupplementalTextPlacement(StrEnum):
    PREFIX = "prefix"
    SUFFIX = "suffix"
    ABOVE = "above"
    BELOW = "below"


class DimensionSupplementRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    text: str = Field(min_length=1)
    placement: SupplementalTextPlacement
    measurement_token: str = "<>"
    separator: str = " "
    preserve_existing_override: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionSupplementRequest:
        _approval(self.dry_run, self.approval, "DTO")
        return self


class DimensionOverrideChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_override: str
    replacement_override: str


class DimensionSupplementPlan(Batch12Plan):
    command_alias: str = "DTO"
    legacy_symbol: str = "xiDimTxOverRide"
    changes: tuple[DimensionOverrideChange, ...]


def plan_dimension_supplement(request: DimensionSupplementRequest, dimensions: Sequence[DimensionSnapshot]) -> DimensionSupplementPlan:
    selected = _dimensions(request.target_handles, dimensions)
    changes = []
    for d in selected:
        base = d.text_override if request.preserve_existing_override and d.text_override else request.measurement_token
        if request.placement is SupplementalTextPlacement.PREFIX:
            replacement = request.text + request.separator + base
        elif request.placement is SupplementalTextPlacement.SUFFIX:
            replacement = base + request.separator + request.text
        elif request.placement is SupplementalTextPlacement.ABOVE:
            replacement = request.text + "\\X" + base
        else:
            replacement = base + "\\X" + request.text
        changes.append(DimensionOverrideChange(handle=d.handle, expected_override=d.text_override,
                                               replacement_override=replacement))
    return DimensionSupplementPlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


# DU
class DimensionUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    target_style: str = Field(min_length=1)
    preserve_text_override: bool = True
    preserve_text_position: bool = True
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionUpdateRequest:
        _approval(self.dry_run, self.approval, "DU")
        return self


class DimensionUpdatePlan(Batch12Plan):
    command_alias: str = "DU"
    legacy_symbol: str = "xiDimUpdate"
    changes: tuple[DimensionStyleAssignment, ...]
    preserve_text_override: bool
    preserve_text_position: bool


def plan_dimension_update(request: DimensionUpdateRequest, styles: Sequence[DimensionStyleSnapshot], dimensions: Sequence[DimensionSnapshot]) -> DimensionUpdatePlan:
    if not any(style.name.casefold() == request.target_style.casefold() and not style.is_xref for style in styles):
        raise ValueError("DU target style is unavailable")
    selected = _dimensions(request.target_handles, dimensions)
    return DimensionUpdatePlan(document_id=request.document_id,
        changes=tuple(DimensionStyleAssignment(handle=d.handle, expected_style=d.style,
                                               replacement_style=request.target_style) for d in selected),
        preserve_text_override=request.preserve_text_override, preserve_text_position=request.preserve_text_position,
        dry_run=request.dry_run)


# ED -- recovered DCL four scale modes.
class EditScaleMode(StrEnum):
    FIXED = "fixed"
    MULTIPLIER = "multiplier"
    MATCH_OBJECT = "match_object"
    DSC_VALUE = "dsc_value"


class EditDimensionScaleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: EditScaleMode
    fixed_scale: float | None = Field(default=None, gt=0)
    multiplier: float | None = Field(default=None, gt=0)
    match_handle: str | None = None
    dsc_value: float | None = Field(default=None, gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> EditDimensionScaleRequest:
        selected = {EditScaleMode.FIXED: self.fixed_scale, EditScaleMode.MULTIPLIER: self.multiplier,
                    EditScaleMode.MATCH_OBJECT: self.match_handle, EditScaleMode.DSC_VALUE: self.dsc_value}[self.mode]
        if selected is None:
            raise ValueError("ED selected mode requires its value")
        _approval(self.dry_run, self.approval, "ED")
        return self


class EditDimensionScalePlan(Batch12Plan):
    command_alias: str = "ED"
    legacy_symbol: str = "xiEditDimScale"
    changes: tuple[DimensionScaleChange, ...]


def plan_edit_dimension_scale(request: EditDimensionScaleRequest, dimensions: Sequence[DimensionSnapshot]) -> EditDimensionScalePlan:
    selected = _dimensions(request.target_handles, dimensions)
    match = None
    if request.mode is EditScaleMode.MATCH_OBJECT:
        match = _dimensions((request.match_handle,), dimensions)[0]
    changes = []
    for d in selected:
        replacement = request.fixed_scale if request.mode is EditScaleMode.FIXED else (
            d.dimscale * request.multiplier if request.mode is EditScaleMode.MULTIPLIER else
            match.dimscale if request.mode is EditScaleMode.MATCH_OBJECT else request.dsc_value)
        changes.append(DimensionScaleChange(handle=d.handle, expected_scale=d.dimscale, replacement_scale=replacement))
    return EditDimensionScalePlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


# IL -- intersection computation is supplied as normalized evidence.
class IntersectionLengthRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    first_intersection: Point3D
    second_intersection: Point3D


class IntersectionOutput(StrEnum):
    DIMENSION = "dimension"
    TEXT = "text"
    RETURN_ONLY = "return_only"


class IntersectionLengthRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    records: tuple[IntersectionLengthRecord, ...] = Field(min_length=1)
    output: IntersectionOutput
    dimension_line_point: Point3D | None = None
    insertion_points: tuple[Point3D, ...] = ()
    style: str | None = None
    decimal_places: int = Field(default=2, ge=0, le=12)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> IntersectionLengthRequest:
        if self.output is IntersectionOutput.DIMENSION and (self.dimension_line_point is None or not self.style):
            raise ValueError("IL dimension output requires line point and style")
        if self.output is IntersectionOutput.TEXT and len(self.insertion_points) != len(self.records):
            raise ValueError("IL text output requires one insertion point per record")
        if self.output is not IntersectionOutput.RETURN_ONLY:
            _approval(self.dry_run, self.approval, "IL")
        return self


class IntersectionLengthResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    length: float = Field(ge=0)
    rendered: str


class IntersectionLengthPlan(Batch12Plan):
    command_alias: str = "IL"
    legacy_symbol: str = "xiIntLen"
    results: tuple[IntersectionLengthResult, ...]
    dimensions: tuple[DimensionCreateSpec, ...]
    text_points: tuple[Point3D, ...]


def plan_intersection_length(request: IntersectionLengthRequest) -> IntersectionLengthPlan:
    results, creates = [], []
    for record in request.records:
        length = dist((record.first_intersection.x, record.first_intersection.y, record.first_intersection.z),
                      (record.second_intersection.x, record.second_intersection.y, record.second_intersection.z))
        results.append(IntersectionLengthResult(source_handle=record.source_handle, length=length,
                                                rendered=f"{length:.{request.decimal_places}f}"))
        if request.output is IntersectionOutput.DIMENSION:
            creates.append(DimensionCreateSpec(source_handle=record.source_handle,
                first_point=record.first_intersection, second_point=record.second_intersection,
                dimension_line_point=request.dimension_line_point, orientation=LinearOrientation.ALIGNED,
                style=request.style))
    return IntersectionLengthPlan(document_id=request.document_id, results=tuple(results), dimensions=tuple(creates),
        text_points=request.insertion_points if request.output is IntersectionOutput.TEXT else (), dry_run=request.dry_run)


# LDA/LSE
class LeaderKind(StrEnum):
    LEADER = "leader"
    MLEADER = "mleader"


class LeaderSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    kind: LeaderKind
    style: str = Field(min_length=1)
    start_point: Point3D
    end_point: Point3D
    locked_layer: bool = False
    is_xref: bool = False


class LeaderAlignAxis(StrEnum):
    X = "x"
    Y = "y"
    EXPLICIT_LINE = "explicit_line"


class LeaderAlignRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    axis: LeaderAlignAxis
    coordinate: float | None = None
    line_start: Point3D | None = None
    line_end: Point3D | None = None
    endpoint: str = Field(default="end", pattern="^(start|end)$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LeaderAlignRequest:
        _unique(self.target_handles, "target_handles")
        if self.axis in {LeaderAlignAxis.X, LeaderAlignAxis.Y} and self.coordinate is None:
            raise ValueError("LDA axis alignment requires coordinate")
        if self.axis is LeaderAlignAxis.EXPLICIT_LINE and (self.line_start is None or self.line_end is None):
            raise ValueError("LDA line alignment requires line points")
        _approval(self.dry_run, self.approval, "LDA")
        return self


class LeaderEndpointChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_point: Point3D
    replacement_point: Point3D


class LeaderAlignPlan(Batch12Plan):
    command_alias: str = "LDA"
    legacy_symbol: str = "xiLeaderAlign"
    changes: tuple[LeaderEndpointChange, ...]


def plan_leader_align(request: LeaderAlignRequest, leaders: Sequence[LeaderSnapshot]) -> LeaderAlignPlan:
    by_handle = {leader.handle.casefold(): leader for leader in leaders}
    changes = []
    for handle in request.target_handles:
        leader = by_handle.get(handle.casefold())
        if leader is None or leader.is_xref or leader.locked_layer:
            raise ValueError(f"LDA leader unavailable: {handle}")
        point = leader.start_point if request.endpoint == "start" else leader.end_point
        if request.axis is LeaderAlignAxis.X:
            replacement = Point3D(x=request.coordinate, y=point.y, z=point.z)
        elif request.axis is LeaderAlignAxis.Y:
            replacement = Point3D(x=point.x, y=request.coordinate, z=point.z)
        else:
            dx, dy = request.line_end.x - request.line_start.x, request.line_end.y - request.line_start.y
            denominator = dx * dx + dy * dy
            if denominator == 0:
                raise ValueError("LDA alignment line must be non-zero")
            t = ((point.x - request.line_start.x) * dx + (point.y - request.line_start.y) * dy) / denominator
            replacement = Point3D(x=request.line_start.x + t * dx, y=request.line_start.y + t * dy, z=point.z)
        changes.append(LeaderEndpointChange(handle=leader.handle, expected_point=point, replacement_point=replacement))
    return LeaderAlignPlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


class LeaderArrowKind(StrEnum):
    CIRCLE = "circle"
    ARROW = "arrow"
    WAVE = "wave"


class LeaderTextPosition(StrEnum):
    SIDE = "side"
    TOP = "top"


class LeaderStylePatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    scale: float = Field(gt=0)
    arrow_kind: LeaderArrowKind
    text_position: LeaderTextPosition
    text_style: str = Field(min_length=1)
    arrow_size: float = Field(gt=0)
    text_gap: float = Field(ge=0)
    text_size: float = Field(gt=0)
    dogleg_length: float = Field(ge=0)
    text_color_index: int = Field(ge=1, le=255)
    leader_color_index: int = Field(ge=1, le=255)


class LeaderStyleAction(StrEnum):
    APPLY_EXISTING = "apply_existing"
    SAVE_NEW = "save_new"
    RENAME = "rename"


class LeaderStyleEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = ()
    leader_kind: LeaderKind
    action: LeaderStyleAction
    source_style: str | None = None
    target_style: str = Field(min_length=1)
    patch: LeaderStylePatch | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LeaderStyleEditRequest:
        _unique(self.target_handles, "target_handles")
        if self.action is LeaderStyleAction.APPLY_EXISTING and (not self.source_style or not self.target_handles):
            raise ValueError("LSE apply_existing requires source style and targets")
        if self.action is LeaderStyleAction.SAVE_NEW and self.patch is None:
            raise ValueError("LSE save_new requires complete patch")
        if self.action is LeaderStyleAction.RENAME and not self.source_style:
            raise ValueError("LSE rename requires source_style")
        _approval(self.dry_run, self.approval, "LSE")
        return self


class LeaderStyleAssignment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_style: str
    replacement_style: str


class LeaderStyleEditPlan(Batch12Plan):
    command_alias: str = "LSE"
    legacy_symbol: str = "xiLeaderStyleEdit"
    assignments: tuple[LeaderStyleAssignment, ...]
    action: LeaderStyleAction
    source_style: str | None
    target_style: str
    patch: LeaderStylePatch | None


def plan_leader_style_edit(request: LeaderStyleEditRequest, leaders: Sequence[LeaderSnapshot]) -> LeaderStyleEditPlan:
    by_handle = {leader.handle.casefold(): leader for leader in leaders}
    assignments = []
    for handle in request.target_handles:
        leader = by_handle.get(handle.casefold())
        if leader is None or leader.is_xref or leader.locked_layer or leader.kind is not request.leader_kind:
            raise ValueError(f"LSE leader unavailable or wrong kind: {handle}")
        assignments.append(LeaderStyleAssignment(handle=leader.handle, expected_style=leader.style,
                                                  replacement_style=request.target_style))
    return LeaderStyleEditPlan(document_id=request.document_id, assignments=tuple(assignments), action=request.action,
        source_style=request.source_style, target_style=request.target_style, patch=request.patch, dry_run=request.dry_run)


def register_headless_core_batch12_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(title="xiCAD Headless Core Batch 12 Planner", readOnlyHint=True,
                                destructiveHint=False, idempotentHint=True, openWorldHint=False)

    @mcp.tool(name="xicad_plan_dpl", annotations=read_only)
    def mcp_plan_dpl(request: PolylineDimensionRequest, polylines: tuple[PolylineDimensionSnapshot, ...]) -> PolylineDimensionPlan:
        return plan_polyline_dimensions(request, polylines)

    @mcp.tool(name="xicad_plan_dq", annotations=read_only)
    def mcp_plan_dq(request: QuickDimensionRequest, sources: tuple[QuickDimensionSource, ...]) -> QuickDimensionPlan:
        return plan_quick_dimensions(request, sources)

    @mcp.tool(name="xicad_plan_dsc", annotations=read_only)
    def mcp_plan_dsc(request: DimensionScaleRequest, dimensions: tuple[DimensionSnapshot, ...]) -> DimensionScalePlan:
        return plan_dimension_scale(request, dimensions)

    @mcp.tool(name="xicad_plan_dse", annotations=read_only)
    def mcp_plan_dse(request: DimensionStyleEditRequest, styles: tuple[DimensionStyleSnapshot, ...]) -> DimensionStyleEditPlan:
        return plan_dimension_style_edit(request, styles)

    @mcp.tool(name="xicad_plan_dsm", annotations=read_only)
    def mcp_plan_dsm(request: DimensionStyleMergeRequest, styles: tuple[DimensionStyleSnapshot, ...], dimensions: tuple[DimensionSnapshot, ...], nested_handles: tuple[str, ...] = ()) -> DimensionStyleMergePlan:
        return plan_dimension_style_merge(request, styles, dimensions, nested_handles)

    @mcp.tool(name="xicad_plan_dtm", annotations=read_only)
    def mcp_plan_dtm(request: DimensionTextMoveRequest, dimensions: tuple[DimensionSnapshot, ...]) -> DimensionTextMovePlan:
        return plan_dimension_text_move(request, dimensions)

    @mcp.tool(name="xicad_plan_dto", annotations=read_only)
    def mcp_plan_dto(request: DimensionSupplementRequest, dimensions: tuple[DimensionSnapshot, ...]) -> DimensionSupplementPlan:
        return plan_dimension_supplement(request, dimensions)

    @mcp.tool(name="xicad_plan_du", annotations=read_only)
    def mcp_plan_du(request: DimensionUpdateRequest, styles: tuple[DimensionStyleSnapshot, ...], dimensions: tuple[DimensionSnapshot, ...]) -> DimensionUpdatePlan:
        return plan_dimension_update(request, styles, dimensions)

    @mcp.tool(name="xicad_plan_ed", annotations=read_only)
    def mcp_plan_ed(request: EditDimensionScaleRequest, dimensions: tuple[DimensionSnapshot, ...]) -> EditDimensionScalePlan:
        return plan_edit_dimension_scale(request, dimensions)

    @mcp.tool(name="xicad_plan_il", annotations=read_only)
    def mcp_plan_il(request: IntersectionLengthRequest) -> IntersectionLengthPlan:
        return plan_intersection_length(request)

    @mcp.tool(name="xicad_plan_lda", annotations=read_only)
    def mcp_plan_lda(request: LeaderAlignRequest, leaders: tuple[LeaderSnapshot, ...]) -> LeaderAlignPlan:
        return plan_leader_align(request, leaders)

    @mcp.tool(name="xicad_plan_lse", annotations=read_only)
    def mcp_plan_lse(request: LeaderStyleEditRequest, leaders: tuple[LeaderSnapshot, ...]) -> LeaderStyleEditPlan:
        return plan_leader_style_edit(request, leaders)
