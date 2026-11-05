"""Evidence-bounded dialog-free planners for xiCAD area batch 24A."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


class EvidenceLevel(StrEnum):
    DCL_CONFIG_EXPLICIT_POLICY = "shortcut_plus_dcl_config_explicit_policy_not_legacy_equivalent"
    CONFIG_EXPLICIT_GEOMETRY = "shortcut_plus_opaque_config_explicit_geometry_not_legacy_equivalent"
    SHORTCUT_EXPLICIT_SNAPSHOT = "shortcut_only_explicit_snapshot_not_legacy_equivalent"


class ContractRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    document_id: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"dry_run", "approval"})
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def validate_approval(self) -> ContractRequest:
        if not self.dry_run and (not self.approval.approved or self.approval.fingerprint != self.fingerprint()):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch24APlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    semantic_evidence: str
    semantic_gaps: tuple[str, ...]
    evidence_level: EvidenceLevel
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class GraphicKind(StrEnum):
    LINE = "LINE"
    POLYLINE = "POLYLINE"
    TEXT = "TEXT"


class ExactGraphic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    kind: GraphicKind
    points: tuple[Point3D, ...] = Field(min_length=1)
    layer: str = Field(min_length=1)
    text: str | None = None
    text_height: float | None = Field(default=None, gt=0)
    closed: bool = False

    @model_validator(mode="after")
    def validate_graphic(self) -> ExactGraphic:
        if self.kind is GraphicKind.LINE and len(self.points) != 2:
            raise ValueError("LINE graphics require exactly two points")
        if self.kind is GraphicKind.POLYLINE and len(self.points) < 2:
            raise ValueError("POLYLINE graphics require at least two points")
        if self.kind is not GraphicKind.TEXT and len(set(self.points)) < 2:
            raise ValueError("linear graphics require at least two distinct points")
        if self.kind is GraphicKind.TEXT and (len(self.points) != 1 or self.text is None or self.text_height is None):
            raise ValueError("TEXT graphics require one insertion point, text, and text_height")
        if self.kind is not GraphicKind.TEXT and (self.text is not None or self.text_height is not None):
            raise ValueError("non-text graphics cannot carry text properties")
        return self


class NorthReviewMode(StrEnum):
    PLAN = "plan"
    SECTION = "section"


class NorthHeightStandard(StrEnum):
    NINE_METERS = "9m"
    TEN_METERS = "10m"


class NorthReviewRequest(ContractRequest):
    mode: NorthReviewMode
    height_standard: NorthHeightStandard
    limit_distance_m: float = Field(gt=0)
    result_layer: str = Field(min_length=1)
    plan_spacing_m: float | None = Field(default=None, gt=0)
    section_north_angle_degrees: float | None = Field(default=None, ge=0, lt=360)
    section_symbol_scale: float | None = Field(default=None, gt=0)
    exact_review_graphics: tuple[ExactGraphic, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_mode_inputs(self) -> NorthReviewRequest:
        if self.mode is NorthReviewMode.PLAN:
            if self.plan_spacing_m is None:
                raise ValueError("CDN plan mode requires plan_spacing_m")
            if self.section_north_angle_degrees is not None or self.section_symbol_scale is not None:
                raise ValueError("CDN plan mode cannot carry section-only settings")
        else:
            if self.section_north_angle_degrees is None or self.section_symbol_scale is None:
                raise ValueError("CDN section mode requires north angle and symbol scale")
            if self.plan_spacing_m is not None:
                raise ValueError("CDN section mode cannot carry plan-only spacing")
        if any(item.layer != self.result_layer for item in self.exact_review_graphics):
            raise ValueError("CDN exact graphics must use result_layer")
        return self


class NorthReviewPlan(Batch24APlan):
    mode: NorthReviewMode
    height_standard: NorthHeightStandard
    limit_distance_m: float
    plan_spacing_m: float | None
    section_north_angle_degrees: float | None
    section_symbol_scale: float | None
    creates: tuple[ExactGraphic, ...]


def plan_check_dist_north(request: NorthReviewRequest) -> NorthReviewPlan:
    return NorthReviewPlan(
        command_alias="CDN",
        legacy_symbol="xiCheckDistNorth",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut plus xi0517 DCL and /xiCheckDistNorth config",
        semantic_gaps=(
            "compiled north-daylight calculation unavailable",
            "building/terrain discovery and compliance decision unavailable",
            "exact graphics must be supplied by a reviewed upstream calculator",
        ),
        evidence_level=EvidenceLevel.DCL_CONFIG_EXPLICIT_POLICY,
        mode=request.mode,
        height_standard=request.height_standard,
        limit_distance_m=request.limit_distance_m,
        plan_spacing_m=request.plan_spacing_m,
        section_north_angle_degrees=request.section_north_angle_degrees,
        section_symbol_scale=request.section_symbol_scale,
        creates=request.exact_review_graphics,
    )


class AreaFieldTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    source_handle: str = Field(min_length=1)
    verified_area: float = Field(gt=0)
    exact_field_expression: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    prefix: str = ""
    suffix: str = ""


class DynamicAreaRequest(ContractRequest):
    targets: tuple[AreaFieldTarget, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_targets(self) -> DynamicAreaRequest:
        _unique(tuple(item.source_handle for item in self.targets), "DAR")
        return self


class AreaFieldCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    verified_area: float
    field_expression: str
    display_template: str
    insertion_point: Point3D
    layer: str
    text_height: float


class DynamicAreaPlan(Batch24APlan):
    creates: tuple[AreaFieldCreate, ...]


def plan_dynamic_area(request: DynamicAreaRequest) -> DynamicAreaPlan:
    return DynamicAreaPlan(
        command_alias="DAR",
        legacy_symbol="xiDyArea",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut: insert live area text",
        semantic_gaps=(
            "accepted source entity types unavailable",
            "legacy FIELD expression and number format unavailable",
            "caller must provide a CAD-specific exact field expression",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXPLICIT_SNAPSHOT,
        creates=tuple(
            AreaFieldCreate(
                source_handle=item.source_handle,
                verified_area=item.verified_area,
                field_expression=item.exact_field_expression,
                display_template=item.prefix + "{FIELD}" + item.suffix,
                insertion_point=item.insertion_point,
                layer=item.layer,
                text_height=item.text_height,
            )
            for item in request.targets
        ),
    )


class EnergyElevationRequest(ContractRequest):
    standard_reference: str = Field(min_length=1)
    source_evidence_handles: tuple[str, ...] = Field(min_length=1)
    exact_elevation_graphics: tuple[ExactGraphic, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence(self) -> EnergyElevationRequest:
        _unique(self.source_evidence_handles, "DEE")
        return self


class EnergyElevationPlan(Batch24APlan):
    standard_reference: str
    source_evidence_handles: tuple[str, ...]
    creates: tuple[ExactGraphic, ...]


def plan_draw_energy_elevation(request: EnergyElevationRequest) -> EnergyElevationPlan:
    return EnergyElevationPlan(
        command_alias="DEE",
        legacy_symbol="xiDrawEnergyElev",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut plus opaque /xiDrawEnergyElev persisted settings",
        semantic_gaps=(
            "energy-grade standard interpretation unavailable",
            "compiled elevation geometry construction unavailable",
            "opaque config field meanings unavailable",
        ),
        evidence_level=EvidenceLevel.CONFIG_EXPLICIT_GEOMETRY,
        standard_reference=request.standard_reference,
        source_evidence_handles=request.source_evidence_handles,
        creates=request.exact_elevation_graphics,
    )


class PolylineLengthSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    polyline_handle: str = Field(min_length=1)
    measured_length: float = Field(ge=0)


class DistanceMemoryRequest(ContractRequest):
    polyline: PolylineLengthSnapshot
    memory_slot: str = Field(min_length=1)
    unit_multiplier: float = Field(default=1, gt=0)
    decimal_places: int = Field(default=6, ge=0, le=12)


class DistanceMemoryPlan(Batch24APlan):
    polyline_handle: str
    memory_slot: str
    numeric_value: float
    serialized_value: str


def plan_distance_memory(request: DistanceMemoryRequest) -> DistanceMemoryPlan:
    value = Decimal(str(request.polyline.measured_length)) * Decimal(str(request.unit_multiplier))
    serialized = format(value.quantize(Decimal(1).scaleb(-request.decimal_places), rounding=ROUND_HALF_UP), "f")
    return DistanceMemoryPlan(
        command_alias="DM",
        legacy_symbol="xiDistMemory",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut: store polyline length in memory",
        semantic_gaps=(
            "legacy memory location and serialization unavailable",
            "polyline measurement is an adapter-supplied snapshot",
            "unit conversion and precision are explicit replacement policy",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXPLICIT_SNAPSHOT,
        polyline_handle=request.polyline.polyline_handle,
        memory_slot=request.memory_slot,
        numeric_value=float(value),
        serialized_value=serialized,
    )


class FieldRelationSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    field_owner_handle: str = Field(min_length=1)
    exact_field_expression: str = Field(min_length=1)
    related_object_handles: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_related(self) -> FieldRelationSnapshot:
        _unique(self.related_object_handles, "FFO related")
        return self


class FindFieldObjectsRequest(ContractRequest):
    fields: tuple[FieldRelationSnapshot, ...] = Field(min_length=1)
    existing_object_handles: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_fields(self) -> FindFieldObjectsRequest:
        _unique(tuple(item.field_owner_handle for item in self.fields), "FFO owner")
        _unique(self.existing_object_handles, "FFO existing")
        return self


class FieldRelationFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    field_owner_handle: str
    exact_field_expression: str
    found_handles: tuple[str, ...]
    missing_handles: tuple[str, ...]


class FindFieldObjectsPlan(Batch24APlan):
    findings: tuple[FieldRelationFinding, ...]
    highlight_handles: tuple[str, ...]


def plan_find_field_objects(request: FindFieldObjectsRequest) -> FindFieldObjectsPlan:
    existing = {handle.casefold() for handle in request.existing_object_handles}
    findings = tuple(
        FieldRelationFinding(
            field_owner_handle=item.field_owner_handle,
            exact_field_expression=item.exact_field_expression,
            found_handles=tuple(handle for handle in item.related_object_handles if handle.casefold() in existing),
            missing_handles=tuple(
                handle for handle in item.related_object_handles if handle.casefold() not in existing
            ),
        )
        for item in request.fields
    )
    highlights = _casefold_unique(handle for item in findings for handle in item.found_handles)
    return FindFieldObjectsPlan(
        command_alias="FFO",
        legacy_symbol="xiFindFieldObj",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut: display objects related to fields",
        semantic_gaps=(
            "FIELD-code parsing and object-ID resolution unavailable",
            "highlight style/lifetime unavailable",
            "relations are explicit adapter-supplied snapshots",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXPLICIT_SNAPSHOT,
        findings=findings,
        highlight_handles=highlights,
    )


class RoundingPolicy(StrEnum):
    NEAREST = "nearest"
    FLOOR = "floor"
    CEILING = "ceiling"


class TextAnchor(StrEnum):
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    MIDDLE_CENTER = "middle_center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class RectangleSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    source_handle: str = Field(min_length=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class RectangleAreaLabelRequest(ContractRequest):
    rectangles: tuple[RectangleSnapshot, ...] = Field(min_length=1, max_length=1)
    dimension_multiplier: float = Field(default=1, gt=0)
    decimal_places: int = Field(default=2, ge=0, le=12)
    rounding: RoundingPolicy = RoundingPolicy.NEAREST
    dimension_unit_text: str = ""
    show_result: bool = True
    show_brackets: bool = False
    expression_separator: str = " x "
    result_separator: str = " = "
    lower_text: str | None = None
    insertion_point: Point3D
    anchor: TextAnchor
    layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_rectangles(self) -> RectangleAreaLabelRequest:
        _unique(tuple(item.source_handle for item in self.rectangles), "HV")
        return self


class RectangleAreaLabel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    converted_width: str
    converted_height: str
    converted_area: str
    text: str


class RectangleAreaLabelPlan(Batch24APlan):
    insertion_point: Point3D
    anchor: TextAnchor
    layer: str
    text_height: float
    labels: tuple[RectangleAreaLabel, ...]


def plan_rectangle_area_label(request: RectangleAreaLabelRequest) -> RectangleAreaLabelPlan:
    labels = []
    for rectangle in request.rectangles:
        width = Decimal(str(rectangle.width)) * Decimal(str(request.dimension_multiplier))
        height = Decimal(str(rectangle.height)) * Decimal(str(request.dimension_multiplier))
        rendered_width = _quantize(width, request.decimal_places, request.rounding)
        rendered_height = _quantize(height, request.decimal_places, request.rounding)
        rendered_area = _quantize(width * height, request.decimal_places, request.rounding)
        expression = (
            rendered_width
            + request.dimension_unit_text
            + request.expression_separator
            + rendered_height
            + request.dimension_unit_text
        )
        if request.show_result:
            expression += request.result_separator + rendered_area + request.dimension_unit_text + "²"
        if request.show_brackets:
            expression = "(" + expression + ")"
        if request.lower_text is not None:
            expression += "\n" + request.lower_text
        labels.append(
            RectangleAreaLabel(
                source_handle=rectangle.source_handle,
                converted_width=rendered_width,
                converted_height=rendered_height,
                converted_area=rendered_area,
                text=expression,
            )
        )
    return RectangleAreaLabelPlan(
        command_alias="HV",
        legacy_symbol="xiHVAREA",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut plus xi0243 DCL and /xiHVArea,/xiHVAREA config records",
        semantic_gaps=(
            "rectangle recognition and width/height orientation unavailable",
            "legacy rounding popup values and unit conversions unavailable",
            "conversion multiplier and rendering policy are explicit",
        ),
        evidence_level=EvidenceLevel.DCL_CONFIG_EXPLICIT_POLICY,
        insertion_point=request.insertion_point,
        anchor=request.anchor,
        layer=request.layer,
        text_height=request.text_height,
        labels=tuple(labels),
    )


def _quantize(value: Decimal, places: int, policy: RoundingPolicy) -> str:
    mode = {
        RoundingPolicy.NEAREST: ROUND_HALF_UP,
        RoundingPolicy.FLOOR: ROUND_FLOOR,
        RoundingPolicy.CEILING: ROUND_CEILING,
    }[policy]
    return format(value.quantize(Decimal(1).scaleb(-places), rounding=mode), "f")


def _unique(handles: tuple[str, ...], alias: str) -> None:
    folded = [handle.casefold() for handle in handles]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{alias} handles must be unique")


def _casefold_unique(handles: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for handle in handles:
        folded = handle.casefold()
        if folded not in seen:
            seen.add(folded)
            result.append(handle)
    return tuple(result)


def register_headless_core_batch24a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 24A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_cdn", plan_check_dist_north),
        ("xicad_plan_dar", plan_dynamic_area),
        ("xicad_plan_dee", plan_draw_energy_elevation),
        ("xicad_plan_dm", plan_distance_memory),
        ("xicad_plan_ffo", plan_find_field_objects),
        ("xicad_plan_hv", plan_rectangle_area_label),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
