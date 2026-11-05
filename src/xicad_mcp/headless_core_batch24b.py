"""Evidence-bounded dialog-free planners for xiCAD batch 24B."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


class EvidenceLevel(StrEnum):
    DCL_CONFIG_AND_SHORTCUT_RECOVERED = "dcl_config_and_shortcut_recovered"
    DCL_AND_SHORTCUT_RECOVERED = "dcl_and_shortcut_recovered"
    SHORTCUT_ONLY_EXPLICIT_RESULT = "shortcut_only_explicit_result_not_legacy_equivalent"


class ContractRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"dry_run", "approval"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    @model_validator(mode="after")
    def validate_approval(self) -> ContractRequest:
        if not self.dry_run and (not self.approval.approved or self.approval.fingerprint != self.fingerprint()):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch24bPlan(BaseModel):
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


class AnnotationMode(StrEnum):
    REPLACE_TEXT = "Exist_rdo"
    CREATE_TEXT = "Point_rdo"


class TriangleSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_id: str = Field(min_length=1)
    horizontal_length: float = Field(gt=0)
    vertical_length: float = Field(gt=0)
    geometry_revision: str = Field(min_length=1)


class ProposedTriangleAnnotation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    formula_text: str = Field(min_length=1)
    result_text: str = Field(min_length=1)
    reported_area: float = Field(gt=0)
    text_height: float = Field(gt=0)
    layer: str = Field(min_length=1)
    insertion_point: Point3D | None = None
    replace_text_handle: str | None = None


class HwAreaRequest(ContractRequest):
    triangle: TriangleSnapshot
    annotation_mode: AnnotationMode
    exact_annotation: ProposedTriangleAnnotation
    area_tolerance: float = Field(default=1e-6, gt=0)

    @model_validator(mode="after")
    def validate_annotation(self) -> HwAreaRequest:
        expected = self.triangle.horizontal_length * self.triangle.vertical_length / 2
        if not math.isclose(self.exact_annotation.reported_area, expected, abs_tol=self.area_tolerance, rel_tol=0):
            raise ValueError("HW reported area must equal horizontal_length * vertical_length / 2")
        if self.annotation_mode is AnnotationMode.REPLACE_TEXT:
            if self.exact_annotation.replace_text_handle is None or self.exact_annotation.insertion_point is not None:
                raise ValueError("HW Exist_rdo requires only a replacement text handle")
        elif self.exact_annotation.insertion_point is None or self.exact_annotation.replace_text_handle is not None:
            raise ValueError("HW Point_rdo requires only an insertion point")
        return self


class HwAreaPlan(Batch24bPlan):
    triangle: TriangleSnapshot
    computed_area: float
    annotation_mode: AnnotationMode
    annotation: ProposedTriangleAnnotation


def plan_hw_area(request: HwAreaRequest) -> HwAreaPlan:
    return HwAreaPlan(
        command_alias="HW",
        legacy_symbol="xiHWArea",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut, xiHWArea_sub DCL, and xiConfig recover triangle formula/result and Exist/Point choices",
        semantic_gaps=(
            "triangle acquisition and horizontal/vertical projection rules are compiled",
            "formula and result text formatting are caller supplied",
        ),
        evidence_level=EvidenceLevel.DCL_CONFIG_AND_SHORTCUT_RECOVERED,
        triangle=request.triangle,
        computed_area=request.triangle.horizontal_length * request.triangle.vertical_length / 2,
        annotation_mode=request.annotation_mode,
        annotation=request.exact_annotation,
    )


class CurveSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    geometry_revision: str = Field(min_length=1)


class ProposedAreaBoundary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    boundary_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=1)
    exact_vertices: tuple[Point3D, ...] = Field(min_length=3)
    reported_area: float = Field(gt=0)
    layer: str = Field(min_length=1)


class ProposedAreaText(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    boundary_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)


class TableMode(StrEnum):
    GENERAL = "Tb1_rdo"
    CAD = "Tb2_rdo"


class MakeAreaCenterRequest(ContractRequest):
    centerlines: tuple[CurveSnapshot, ...] = Field(min_length=1)
    recognition_layer_pattern: str = Field(min_length=1)
    turn_off_other_layers: bool
    output_layer: str = Field(min_length=1)
    exact_boundaries: tuple[ProposedAreaBoundary, ...] = Field(min_length=1)
    write_individual_areas: bool
    exact_area_texts: tuple[ProposedAreaText, ...] = ()
    make_basis_table: bool
    table_mode: TableMode | None = None
    decimal_places: int = Field(ge=0, le=12)
    rounding_policy: str = Field(min_length=1)
    input_unit: str = Field(pattern="^(m|mm)$")

    @model_validator(mode="after")
    def validate_results(self) -> MakeAreaCenterRequest:
        handles = {item.handle.casefold() for item in self.centerlines}
        if len(handles) != len(self.centerlines):
            raise ValueError("MAC centerline handles must be unique")
        consumed = {handle.casefold() for item in self.exact_boundaries for handle in item.source_handles}
        if not consumed <= handles:
            raise ValueError("MAC boundary references an unknown centerline")
        boundary_ids = {item.boundary_id.casefold() for item in self.exact_boundaries}
        if len(boundary_ids) != len(self.exact_boundaries):
            raise ValueError("MAC boundary ids must be unique")
        text_ids = {item.boundary_id.casefold() for item in self.exact_area_texts}
        if self.write_individual_areas and text_ids != boundary_ids:
            raise ValueError("MAC requires one exact area text per boundary")
        if not self.write_individual_areas and self.exact_area_texts:
            raise ValueError("MAC area texts require AText_tgl")
        if self.make_basis_table != (self.table_mode is not None):
            raise ValueError("MAC MakeTb_tgl and table mode must be supplied together")
        return self


class MakeAreaCenterPlan(Batch24bPlan):
    source_centerlines: tuple[CurveSnapshot, ...]
    recognition_layer_pattern: str
    turn_off_other_layers: bool
    output_layer: str
    creates_boundaries: tuple[ProposedAreaBoundary, ...]
    creates_texts: tuple[ProposedAreaText, ...]
    make_basis_table: bool
    table_mode: TableMode | None
    decimal_places: int
    rounding_policy: str
    input_unit: str


def plan_make_area_center(request: MakeAreaCenterRequest) -> MakeAreaCenterPlan:
    return MakeAreaCenterPlan(
        command_alias="MAC",
        legacy_symbol="xiMakeAreaCenter",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut, ZWCAD_xi0389_d.04.dcl, and xiConfig recover layers, labels, table, precision, rounding, and units",
        semantic_gaps=(
            "compiled centerline-to-boundary recognition is unavailable",
            "caller supplies exact boundary vertices, areas, and optional annotation payloads",
            "cuLay toggles and table layout internals are unavailable",
        ),
        evidence_level=EvidenceLevel.DCL_CONFIG_AND_SHORTCUT_RECOVERED,
        source_centerlines=request.centerlines,
        recognition_layer_pattern=request.recognition_layer_pattern,
        turn_off_other_layers=request.turn_off_other_layers,
        output_layer=request.output_layer,
        creates_boundaries=request.exact_boundaries,
        creates_texts=request.exact_area_texts,
        make_basis_table=request.make_basis_table,
        table_mode=request.table_mode,
        decimal_places=request.decimal_places,
        rounding_policy=request.rounding_policy,
        input_unit=request.input_unit,
    )


class RoomAreaSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    gross_area: float = Field(gt=0)
    excluded_area: float = Field(ge=0)
    geometry_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_area(self) -> RoomAreaSnapshot:
        if self.excluded_area >= self.gross_area:
            raise ValueError("MRT excluded area must be smaller than gross area")
        return self


class ProposedRoomRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    room_number: str = Field(min_length=1)
    room_name: str = Field(min_length=1)
    reported_area: float = Field(gt=0)


class RoomTableRequest(ContractRequest):
    rooms: tuple[RoomAreaSnapshot, ...] = Field(min_length=1)
    exact_rows: tuple[ProposedRoomRow, ...] = Field(min_length=1)
    table_mode: TableMode
    live_area_numbers: bool
    output_line_layer: str = Field(min_length=1)
    output_text_layer: str = Field(min_length=1)
    exclusion_layers: tuple[str, ...] = ()
    decimal_places: int = Field(ge=0, le=12)
    rounding_policy: str = Field(min_length=1)
    comma_grouping: bool
    table_text_height: float = Field(gt=0)
    order_by: str = Field(pattern="^(Num_rdo|Name_rdo)$")
    area_tolerance: float = Field(default=1e-6, gt=0)

    @model_validator(mode="after")
    def validate_rows(self) -> RoomTableRequest:
        room_map = {item.handle.casefold(): item for item in self.rooms}
        row_map = {item.source_handle.casefold(): item for item in self.exact_rows}
        if len(room_map) != len(self.rooms) or len(row_map) != len(self.exact_rows) or room_map.keys() != row_map.keys():
            raise ValueError("MRT requires one unique exact row per room snapshot")
        for handle, room in room_map.items():
            if not math.isclose(
                row_map[handle].reported_area,
                room.gross_area - room.excluded_area,
                abs_tol=self.area_tolerance,
                rel_tol=0,
            ):
                raise ValueError("MRT row area must equal gross minus explicit excluded area")
        return self


class RoomTablePlan(Batch24bPlan):
    rooms: tuple[RoomAreaSnapshot, ...]
    table_mode: TableMode
    live_area_numbers: bool
    output_line_layer: str
    output_text_layer: str
    exclusion_layers: tuple[str, ...]
    decimal_places: int
    rounding_policy: str
    comma_grouping: bool
    table_text_height: float
    rows: tuple[ProposedRoomRow, ...]
    order_by: str


def plan_room_table(request: RoomTableRequest) -> RoomTablePlan:
    return RoomTablePlan(
        command_alias="MRT",
        legacy_symbol="xiMakeRoomTable",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut and ACAD_xi0518_d.04.dcl recover layers, exclusions, table mode, live area, fields, formatting, and ordering",
        semantic_gaps=(
            "room-boundary recognition, exclusion extraction, field linkage, and exact table geometry are compiled",
            "caller supplies versioned room areas and exact rows",
        ),
        evidence_level=EvidenceLevel.DCL_AND_SHORTCUT_RECOVERED,
        rooms=request.rooms,
        table_mode=request.table_mode,
        live_area_numbers=request.live_area_numbers,
        output_line_layer=request.output_line_layer,
        output_text_layer=request.output_text_layer,
        exclusion_layers=request.exclusion_layers,
        decimal_places=request.decimal_places,
        rounding_policy=request.rounding_policy,
        comma_grouping=request.comma_grouping,
        table_text_height=request.table_text_height,
        rows=request.exact_rows,
        order_by=request.order_by,
    )


class SiteAreaMode(StrEnum):
    TRIANGLE = "Tri_rdo"
    RECTANGLE_AUTO = "Rect_rdo"
    RECTANGLE_MANUAL = "Rect1_rdo"


class SiteAreaSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    component_id: str = Field(min_length=1)
    reported_area: float = Field(gt=0)
    geometry_revision: str = Field(min_length=1)


class ProposedSiteAreaRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    component_id: str = Field(min_length=1)
    sequence_number: int = Field(ge=0)
    calculation_text: str = Field(min_length=1)
    area: float = Field(gt=0)


class SiteAreaRequest(ContractRequest):
    mode: SiteAreaMode
    components: tuple[SiteAreaSnapshot, ...] = Field(min_length=1)
    exact_rows: tuple[ProposedSiteAreaRow, ...] = Field(min_length=1)
    starting_number: int = Field(ge=0)
    unit: str = Field(min_length=1)
    decimal_places: int = Field(ge=0, le=12)
    ordering_key: str = Field(pattern="^(OrderPnt[1-4]_img)$")
    ordering_direction: str = Field(pattern="^(Order[1-4]_img)$")
    ordering_tolerance: float = Field(ge=0)
    rectangle_tolerance: float = Field(ge=0)
    delete_generated_boundaries: bool
    display_pyong: bool
    comma_grouping: bool
    geometry_layer: str = Field(min_length=1)
    table_layer: str = Field(min_length=1)
    text_layer: str = Field(min_length=1)
    area_tolerance: float = Field(default=1e-6, gt=0)

    @model_validator(mode="after")
    def validate_rows(self) -> SiteAreaRequest:
        snapshots = {item.component_id.casefold(): item.reported_area for item in self.components}
        rows = {item.component_id.casefold(): item for item in self.exact_rows}
        if len(snapshots) != len(self.components) or len(rows) != len(self.exact_rows) or snapshots.keys() != rows.keys():
            raise ValueError("SAR requires one unique exact row per component snapshot")
        expected_numbers = set(range(self.starting_number, self.starting_number + len(rows)))
        if {item.sequence_number for item in rows.values()} != expected_numbers:
            raise ValueError("SAR rows must use the explicit contiguous numbering range")
        if any(
            not math.isclose(area, rows[key].area, abs_tol=self.area_tolerance, rel_tol=0)
            for key, area in snapshots.items()
        ):
            raise ValueError("SAR row area must match its versioned component snapshot")
        return self


class SiteAreaPlan(Batch24bPlan):
    mode: SiteAreaMode
    components: tuple[SiteAreaSnapshot, ...]
    rows: tuple[ProposedSiteAreaRow, ...]
    starting_number: int
    unit: str
    decimal_places: int
    ordering_key: str
    ordering_direction: str
    ordering_tolerance: float
    rectangle_tolerance: float
    delete_generated_boundaries: bool
    display_pyong: bool
    comma_grouping: bool
    geometry_layer: str
    table_layer: str
    text_layer: str


def plan_site_area(request: SiteAreaRequest) -> SiteAreaPlan:
    return SiteAreaPlan(
        command_alias="SAR",
        legacy_symbol="xiSiteArea",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut, ZWCAD_xi0170_d.02.dcl, and xiConfig recover survey mode, numbering, units, ordering, tolerances, layers, deletion, pyong, and comma controls",
        semantic_gaps=(
            "triangulation/rectangle recognition, ordering geometry, table layout, and formula formatting are compiled",
            "caller supplies exact versioned component areas and calculation rows",
        ),
        evidence_level=EvidenceLevel.DCL_CONFIG_AND_SHORTCUT_RECOVERED,
        mode=request.mode,
        components=request.components,
        rows=request.exact_rows,
        starting_number=request.starting_number,
        unit=request.unit,
        decimal_places=request.decimal_places,
        ordering_key=request.ordering_key,
        ordering_direction=request.ordering_direction,
        ordering_tolerance=request.ordering_tolerance,
        rectangle_tolerance=request.rectangle_tolerance,
        delete_generated_boundaries=request.delete_generated_boundaries,
        display_pyong=request.display_pyong,
        comma_grouping=request.comma_grouping,
        geometry_layer=request.geometry_layer,
        table_layer=request.table_layer,
        text_layer=request.text_layer,
    )


class AreaGeometrySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    area: float = Field(gt=0)
    geometry_revision: str = Field(min_length=1)


class ProposedScaledArea(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    result_area: float = Field(gt=0)
    exact_vertices: tuple[Point3D, ...] = Field(min_length=3)
    result_layer: str = Field(min_length=1)


class ScaleAreaRequest(ContractRequest):
    sources: tuple[AreaGeometrySnapshot, ...] = Field(min_length=1)
    requested_operation_id: str = Field(min_length=1)
    exact_results: tuple[ProposedScaledArea, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_mapping(self) -> ScaleAreaRequest:
        source_ids = [item.handle.casefold() for item in self.sources]
        result_ids = [item.source_handle.casefold() for item in self.exact_results]
        if len(source_ids) != len(set(source_ids)) or len(result_ids) != len(set(result_ids)) or set(source_ids) != set(result_ids):
            raise ValueError("SCA requires one unique explicit result per source snapshot")
        return self


class ScaleAreaPlan(Batch24bPlan):
    sources: tuple[AreaGeometrySnapshot, ...]
    requested_operation_id: str
    results: tuple[ProposedScaledArea, ...]


def plan_scale_area(request: ScaleAreaRequest) -> ScaleAreaPlan:
    return ScaleAreaPlan(
        command_alias="SCA",
        legacy_symbol="xiScaleArea",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut identify only xiScaleArea and the description '면적 확대하기'",
        semantic_gaps=(
            "no command-specific DCL/config/data/readable source was found",
            "scale meaning, anchor selection, source retention, and geometry algorithm are compiled",
            "planner does not claim legacy equivalence and accepts only explicit result geometry",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        sources=request.sources,
        requested_operation_id=request.requested_operation_id,
        results=request.exact_results,
    )


class SelectableEntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    layer_name: str = Field(min_length=1)
    layer_color: int | None = None
    layer_linetype: str | None = None
    text: str | None = None
    text_style: str | None = None
    text_height: float | None = Field(default=None, gt=0)
    block_name: str | None = None
    dimension_style: str | None = None
    hatch_pattern: str | None = None
    length: float | None = Field(default=None, ge=0)
    area: float | None = Field(default=None, ge=0)
    angle_degrees: float | None = None
    radius: float | None = Field(default=None, ge=0)
    thickness: float | None = None
    elevation: float | None = None
    geometry_revision: str = Field(min_length=1)


class SameEntityCriteria(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    entity_type: bool = False
    layer_name: bool = False
    layer_color: bool = False
    layer_linetype: bool = False
    text: bool = False
    text_contains: bool = False
    text_style: bool = False
    text_height_tolerance: float | None = Field(default=None, ge=0)
    block_name: bool = False
    dimension_style: bool = False
    hatch_pattern: bool = False
    length_tolerance: float | None = Field(default=None, ge=0)
    area_tolerance: float | None = Field(default=None, ge=0)
    angle_tolerance: float | None = Field(default=None, ge=0)
    radius_tolerance: float | None = Field(default=None, ge=0)
    thickness_tolerance: float | None = Field(default=None, ge=0)
    elevation_tolerance: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_criterion(self) -> SameEntityCriteria:
        exact_enabled = (
            self.entity_type
            or self.layer_name
            or self.layer_color
            or self.layer_linetype
            or self.text
            or self.text_style
            or self.block_name
            or self.dimension_style
            or self.hatch_pattern
        )
        numeric_enabled = any(
            value is not None
            for value in (
                self.text_height_tolerance,
                self.length_tolerance,
                self.area_tolerance,
                self.angle_tolerance,
                self.radius_tolerance,
                self.thickness_tolerance,
                self.elevation_tolerance,
            )
        )
        if self.text_contains and not self.text:
            raise ValueError("SE text_contains requires the text criterion")
        if not exact_enabled and not numeric_enabled:
            raise ValueError("SE requires at least one enabled criterion")
        return self


class SelectSameRequest(ContractRequest):
    reference: SelectableEntitySnapshot
    candidates: tuple[SelectableEntitySnapshot, ...] = Field(min_length=1)
    criteria: SameEntityCriteria
    selection_area_handles: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def validate_candidates(self) -> SelectSameRequest:
        handles = [item.handle.casefold() for item in self.candidates]
        if len(handles) != len(set(handles)):
            raise ValueError("SE candidate handles must be unique")
        if self.selection_area_handles is not None:
            area = [item.casefold() for item in self.selection_area_handles]
            if len(area) != len(set(area)) or not set(area) <= set(handles):
                raise ValueError("SE selection area must contain unique known candidate handles")
        return self


class SelectSamePlan(Batch24bPlan):
    reference: SelectableEntitySnapshot
    selected_entities: tuple[SelectableEntitySnapshot, ...]
    selected_handles: tuple[str, ...]
    criteria: SameEntityCriteria


def _same_optional(left: object, right: object) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    return left == right


def _within(left: float | None, right: float | None, tolerance: float | None) -> bool:
    return left is not None and right is not None and tolerance is not None and math.isclose(left, right, abs_tol=tolerance, rel_tol=0)


def _matches(reference: SelectableEntitySnapshot, candidate: SelectableEntitySnapshot, c: SameEntityCriteria) -> bool:
    exact_fields = (
        (c.entity_type, reference.entity_type, candidate.entity_type),
        (c.layer_name, reference.layer_name, candidate.layer_name),
        (c.layer_color, reference.layer_color, candidate.layer_color),
        (c.layer_linetype, reference.layer_linetype, candidate.layer_linetype),
        (c.text_style, reference.text_style, candidate.text_style),
        (c.block_name, reference.block_name, candidate.block_name),
        (c.dimension_style, reference.dimension_style, candidate.dimension_style),
        (c.hatch_pattern, reference.hatch_pattern, candidate.hatch_pattern),
    )
    if any(enabled and not _same_optional(left, right) for enabled, left, right in exact_fields):
        return False
    if c.text:
        if reference.text is None or candidate.text is None:
            return False
        if c.text_contains:
            if reference.text.casefold() not in candidate.text.casefold():
                return False
        elif reference.text.casefold() != candidate.text.casefold():
            return False
    numeric = (
        (reference.text_height, candidate.text_height, c.text_height_tolerance),
        (reference.length, candidate.length, c.length_tolerance),
        (reference.area, candidate.area, c.area_tolerance),
        (reference.angle_degrees, candidate.angle_degrees, c.angle_tolerance),
        (reference.radius, candidate.radius, c.radius_tolerance),
        (reference.thickness, candidate.thickness, c.thickness_tolerance),
        (reference.elevation, candidate.elevation, c.elevation_tolerance),
    )
    return all(tolerance is None or _within(left, right, tolerance) for left, right, tolerance in numeric)


def plan_select_same(request: SelectSameRequest) -> SelectSamePlan:
    allowed = None if request.selection_area_handles is None else {item.casefold() for item in request.selection_area_handles}
    selected = tuple(
        item
        for item in request.candidates
        if (allowed is None or item.handle.casefold() in allowed) and _matches(request.reference, item, request.criteria)
    )
    return SelectSamePlan(
        command_alias="SE",
        legacy_symbol="xiSelectSameEntities",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut, ZWCAD_xi0219_d.08.dcl, and xiConfig recover explicit type/layer/text/block/dimension/hatch/numeric criteria and optional selection area",
        semantic_gaps=(
            "forced property overrides, field/mirror/scale matching, nested blocks, multi-file operations, and default-selection persistence remain compiled",
            "this planner exposes deterministic read-only matching only",
        ),
        evidence_level=EvidenceLevel.DCL_CONFIG_AND_SHORTCUT_RECOVERED,
        reference=request.reference,
        selected_entities=selected,
        selected_handles=tuple(item.handle for item in selected),
        criteria=request.criteria,
    )


def register_headless_core_batch24b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 24B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_hw", plan_hw_area),
        ("xicad_plan_mac", plan_make_area_center),
        ("xicad_plan_mrt", plan_room_table),
        ("xicad_plan_sar", plan_site_area),
        ("xicad_plan_sca", plan_scale_area),
        ("xicad_plan_se", plan_select_same),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
