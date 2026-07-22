"""Evidence-bounded dialog-free planners for xiCAD batch 25B."""

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
    SHORTCUT_ONLY_EXPLICIT_RESULT = "shortcut_only_explicit_result_not_legacy_equivalent"
    SHORTCUT_ONLY_EXPLICIT_POLICY = "shortcut_only_explicit_policy_not_legacy_equivalent"


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


class Batch25bPlan(BaseModel):
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


class TableResultMode(StrEnum):
    GENERAL_TABLE = "Table_rdo"
    CAD_TABLE = "Excel_rdo"


class TextCoordinateMode(StrEnum):
    ABSOLUTE = "Absolute_rdo"
    FRAME_RELATIVE = "Relative_rdo"


class WorkspaceMode(StrEnum):
    MODEL = "WorkModel_rdo"
    PAPER = "WorkPaper_rdo"
    BOTH = "WorkBoth_rdo"


class TableTextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    text: str
    insertion_point: Point3D
    space: str = Field(pattern="^(model|paper)$")
    geometry_revision: str = Field(min_length=1)


class ProposedTableCell(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    text: str


class TextsToTableRequest(ContractRequest):
    result_mode: TableResultMode
    coordinate_mode: TextCoordinateMode
    workspace: WorkspaceMode
    frame_handle: str | None = None
    ordering_anchor: str = Field(pattern="^OrderPnt[1-4]_img$")
    ordering_direction: str = Field(pattern="^Order[1-4]_img$")
    ordering_tolerance: float = Field(ge=0)
    selection_order_first: bool
    source_texts: tuple[TableTextSnapshot, ...] = Field(min_length=1)
    exact_cells: tuple[ProposedTableCell, ...] = Field(min_length=1)
    output_line_layer: str = Field(min_length=1)
    output_text_layer: str = Field(min_length=1)
    table_text_height: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_mapping(self) -> TextsToTableRequest:
        sources = {item.handle.casefold(): item for item in self.source_texts}
        cells = {item.source_handle.casefold(): item for item in self.exact_cells}
        if len(sources) != len(self.source_texts) or len(cells) != len(self.exact_cells) or sources.keys() != cells.keys():
            raise ValueError("TTT requires one unique exact cell per source text")
        if len({(item.row, item.column) for item in self.exact_cells}) != len(self.exact_cells):
            raise ValueError("TTT exact cell coordinates must be unique")
        if any(cells[key].text != source.text for key, source in sources.items()):
            raise ValueError("TTT exact cell text must preserve its source text")
        if self.coordinate_mode is TextCoordinateMode.FRAME_RELATIVE and self.frame_handle is None:
            raise ValueError("TTT Relative_rdo requires an explicit frame handle")
        if self.coordinate_mode is TextCoordinateMode.ABSOLUTE and self.frame_handle is not None:
            raise ValueError("TTT Absolute_rdo does not accept a frame handle")
        allowed_spaces = {
            WorkspaceMode.MODEL: {"model"},
            WorkspaceMode.PAPER: {"paper"},
            WorkspaceMode.BOTH: {"model", "paper"},
        }[self.workspace]
        if any(item.space not in allowed_spaces for item in self.source_texts):
            raise ValueError("TTT source space conflicts with the recovered workspace choice")
        return self


class TextsToTablePlan(Batch25bPlan):
    result_mode: TableResultMode
    coordinate_mode: TextCoordinateMode
    workspace: WorkspaceMode
    frame_handle: str | None
    source_texts: tuple[TableTextSnapshot, ...]
    cells: tuple[ProposedTableCell, ...]
    ordering_anchor: str
    ordering_direction: str
    ordering_tolerance: float
    selection_order_first: bool
    output_line_layer: str
    output_text_layer: str
    table_text_height: float


def plan_texts_to_table(request: TextsToTableRequest) -> TextsToTablePlan:
    return TextsToTablePlan(
        command_alias="TTT",
        legacy_symbol="xiTextsToTable",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts, ACAD_xi0471_d.01.dcl, and xiConfig recover table, coordinate, workspace, ordering, layer, and text-height choices",
        semantic_gaps=(
            "compiled frame recognition, geometric row/column clustering, and table layout are unavailable",
            "multi-file opening and writing are deliberately not exposed",
            "caller supplies versioned text snapshots and the exact cell mapping",
        ),
        evidence_level=EvidenceLevel.DCL_CONFIG_AND_SHORTCUT_RECOVERED,
        result_mode=request.result_mode,
        coordinate_mode=request.coordinate_mode,
        workspace=request.workspace,
        frame_handle=request.frame_handle,
        source_texts=request.source_texts,
        cells=request.exact_cells,
        ordering_anchor=request.ordering_anchor,
        ordering_direction=request.ordering_direction,
        ordering_tolerance=request.ordering_tolerance,
        selection_order_first=request.selection_order_first,
        output_line_layer=request.output_line_layer,
        output_text_layer=request.output_text_layer,
        table_text_height=request.table_text_height,
    )


class TextBoxShape(StrEnum):
    RECTANGLE = "line_rdo"
    PROJECTED = "exline_rdo"
    ROUNDED_RECTANGLE = "round_rdo"
    CIRCULAR_RECTANGLE = "round1_rdo"
    TWO_ARC_RECTANGLE = "round2_rdo"
    CIRCLE = "circle_rdo"
    ELLIPSE = "ellip_rdo"
    RHOMBUS = "rhomb0_rdo"
    LONG_RHOMBUS = "rhomb1_rdo"
    POLYGON = "polygon_rdo"


class MaskMode(StrEnum):
    NONE = "None_rdo"
    WIPEOUT = "WipeOut_rdo"
    SOLID = "Solid_rdo"


class TextEntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    text: str
    bounds_min: Point3D
    bounds_max: Point3D
    geometry_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> TextEntitySnapshot:
        if self.bounds_min.x >= self.bounds_max.x or self.bounds_min.y >= self.bounds_max.y:
            raise ValueError("TX text snapshot requires increasing XY bounds")
        return self


class ProposedTextBoundary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    exact_vertices: tuple[Point3D, ...] = Field(min_length=2)
    boundary_layer: str = Field(min_length=1)
    group_id: str | None = None


class TextBoxRequest(ContractRequest):
    sources: tuple[TextEntitySnapshot, ...] = Field(min_length=1)
    shape: TextBoxShape
    polygon_sides: int | None = Field(default=None, ge=3)
    uppercase: bool
    group_results: bool
    mask_mode: MaskMode
    solid_color: int | None = Field(default=None, ge=0, le=256)
    text_style: str = Field(min_length=1)
    text_layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    boundary_layer: str = Field(min_length=1)
    fixed_width: float | None = Field(default=None, gt=0)
    fixed_height: float | None = Field(default=None, gt=0)
    width_gap: float = Field(ge=0)
    height_gap: float = Field(ge=0)
    corner_radius: float = Field(ge=0)
    exact_boundaries: tuple[ProposedTextBoundary, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> TextBoxRequest:
        sources = {item.handle.casefold() for item in self.sources}
        results = {item.source_handle.casefold() for item in self.exact_boundaries}
        if len(sources) != len(self.sources) or len(results) != len(self.exact_boundaries) or sources != results:
            raise ValueError("TX requires one unique exact boundary per source text")
        if (self.shape is TextBoxShape.POLYGON) != (self.polygon_sides is not None):
            raise ValueError("TX polygon_rdo and polygon_sides must be supplied together")
        if (self.mask_mode is MaskMode.SOLID) != (self.solid_color is not None):
            raise ValueError("TX Solid_rdo and solid_color must be supplied together")
        if self.group_results and any(item.group_id is None for item in self.exact_boundaries):
            raise ValueError("TX Group_tgl requires a group id for every boundary")
        if not self.group_results and any(item.group_id is not None for item in self.exact_boundaries):
            raise ValueError("TX boundary group ids require Group_tgl")
        return self


class TextBoxPlan(Batch25bPlan):
    sources: tuple[TextEntitySnapshot, ...]
    shape: TextBoxShape
    polygon_sides: int | None
    uppercase: bool
    group_results: bool
    mask_mode: MaskMode
    solid_color: int | None
    text_style: str
    text_layer: str
    text_height: float
    boundary_layer: str
    fixed_width: float | None
    fixed_height: float | None
    width_gap: float
    height_gap: float
    corner_radius: float
    boundaries: tuple[ProposedTextBoundary, ...]


def plan_text_box(request: TextBoxRequest) -> TextBoxPlan:
    return TextBoxPlan(
        command_alias="TX",
        legacy_symbol="xiTextBox",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts, ZWCAD_xi0355_d.07.dcl, and xiConfig recover shape, mask, grouping, style, layers, size, gap, and radius choices",
        semantic_gaps=(
            "compiled text extents, curve construction, associative linkage, masking order, and grouping implementation are unavailable",
            "caller supplies versioned text bounds and exact result geometry",
        ),
        evidence_level=EvidenceLevel.DCL_CONFIG_AND_SHORTCUT_RECOVERED,
        sources=request.sources,
        shape=request.shape,
        polygon_sides=request.polygon_sides,
        uppercase=request.uppercase,
        group_results=request.group_results,
        mask_mode=request.mask_mode,
        solid_color=request.solid_color,
        text_style=request.text_style,
        text_layer=request.text_layer,
        text_height=request.text_height,
        boundary_layer=request.boundary_layer,
        fixed_width=request.fixed_width,
        fixed_height=request.fixed_height,
        width_gap=request.width_gap,
        height_gap=request.height_gap,
        corner_radius=request.corner_radius,
        boundaries=request.exact_boundaries,
    )


class LinetypeTextElement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str = Field(min_length=1)
    style: str = Field(min_length=1)
    scale: float = Field(gt=0)
    rotation_degrees: float
    x_offset: float
    y_offset: float


class ProposedLinetype(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    description: str
    dash_pattern: tuple[float, ...] = Field(min_length=1)
    text_elements: tuple[LinetypeTextElement, ...] = Field(min_length=1)
    target_lin_file: str | None = None


class MakeTextLinetypeRequest(ContractRequest):
    proposed_linetype: ProposedLinetype
    overwrite_existing: bool


class MakeTextLinetypePlan(Batch25bPlan):
    proposed_linetype: ProposedLinetype
    overwrite_existing: bool


def plan_make_text_linetype(request: MakeTextLinetypeRequest) -> MakeTextLinetypePlan:
    return MakeTextLinetypePlan(
        command_alias="MTLT",
        legacy_symbol="xiMakeLt",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify xiMakeLt and describe creating a line shape containing text",
        semantic_gaps=(
            "no command-specific DCL/config/data/readable source was found",
            "selection, pattern derivation, LIN serialization, loading, and replacement behavior are compiled",
            "the exact linetype definition is caller supplied and does not claim legacy equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        proposed_linetype=request.proposed_linetype,
        overwrite_existing=request.overwrite_existing,
    )


class EntityExtentsSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    minimum: Point3D
    maximum: Point3D
    coordinate_system_id: str = Field(min_length=1)
    geometry_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_extents(self) -> EntityExtentsSnapshot:
        if self.minimum.x > self.maximum.x or self.minimum.y > self.maximum.y or self.minimum.z > self.maximum.z:
            raise ValueError("PBB entity extents must be ordered")
        return self


class BoundingBoxRequest(ContractRequest):
    entities: tuple[EntityExtentsSnapshot, ...] = Field(min_length=1)
    output_layer: str = Field(min_length=1)
    close_polyline: bool = True

    @model_validator(mode="after")
    def validate_entities(self) -> BoundingBoxRequest:
        if len({item.handle.casefold() for item in self.entities}) != len(self.entities):
            raise ValueError("PBB entity handles must be unique")
        if len({item.coordinate_system_id for item in self.entities}) != 1:
            raise ValueError("PBB extents must use one explicit coordinate system")
        return self


class BoundingBoxPlan(Batch25bPlan):
    source_handles: tuple[str, ...]
    coordinate_system_id: str
    minimum: Point3D
    maximum: Point3D
    vertices: tuple[Point3D, Point3D, Point3D, Point3D]
    output_layer: str
    close_polyline: bool


def plan_bounding_box(request: BoundingBoxRequest) -> BoundingBoxPlan:
    minimum = Point3D(
        x=min(item.minimum.x for item in request.entities),
        y=min(item.minimum.y for item in request.entities),
        z=min(item.minimum.z for item in request.entities),
    )
    maximum = Point3D(
        x=max(item.maximum.x for item in request.entities),
        y=max(item.maximum.y for item in request.entities),
        z=max(item.maximum.z for item in request.entities),
    )
    vertices = (
        Point3D(x=minimum.x, y=minimum.y, z=minimum.z),
        Point3D(x=maximum.x, y=minimum.y, z=minimum.z),
        Point3D(x=maximum.x, y=maximum.y, z=minimum.z),
        Point3D(x=minimum.x, y=maximum.y, z=minimum.z),
    )
    return BoundingBoxPlan(
        command_alias="PBB",
        legacy_symbol="xiPBoundingBox",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify xiPBoundingBox and describe drawing an object boundary box",
        semantic_gaps=(
            "no command-specific DCL/config/data/readable source was found",
            "legacy selection scope, UCS projection, padding, layer, and source treatment are compiled",
            "this planner uses explicit versioned extents in one coordinate system and does not claim legacy equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        source_handles=tuple(item.handle for item in request.entities),
        coordinate_system_id=request.entities[0].coordinate_system_id,
        minimum=minimum,
        maximum=maximum,
        vertices=vertices,
        output_layer=request.output_layer,
        close_polyline=request.close_polyline,
    )


class OpenPolylineSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    entity_type: str = Field(pattern="^(LWPOLYLINE|POLYLINE)$")
    vertices: tuple[Point3D, ...] = Field(min_length=2)
    is_closed: bool = False
    geometry_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_open(self) -> OpenPolylineSnapshot:
        if self.is_closed:
            raise ValueError("PC accepts only an open polyline snapshot")
        return self


class PolylineCloseRequest(ContractRequest):
    polylines: tuple[OpenPolylineSnapshot, ...] = Field(min_length=1)
    closure_policy: str = Field(default="set_closed_flag", pattern="^set_closed_flag$")

    @model_validator(mode="after")
    def validate_unique(self) -> PolylineCloseRequest:
        if len({item.handle.casefold() for item in self.polylines}) != len(self.polylines):
            raise ValueError("PC polyline handles must be unique")
        return self


class ClosedPolylineResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    vertices: tuple[Point3D, ...]
    set_closed: bool = True


class PolylineClosePlan(Batch25bPlan):
    updates: tuple[ClosedPolylineResult, ...]
    closure_policy: str


def plan_polyline_close(request: PolylineCloseRequest) -> PolylineClosePlan:
    return PolylineClosePlan(
        command_alias="PC",
        legacy_symbol="xiPolyClose",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify xiPolyClose and describe closing open polylines",
        semantic_gaps=(
            "no command-specific DCL/config/data/readable source was found",
            "legacy eligibility, tolerance, 3D handling, and whether it adds a vertex or sets the closed flag are compiled",
            "this explicit policy preserves vertices and sets the closed flag without claiming legacy equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        updates=tuple(ClosedPolylineResult(handle=item.handle, vertices=item.vertices) for item in request.polylines),
        closure_policy=request.closure_policy,
    )


class CurveTangentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    base_point: Point3D
    tangent_x: float
    tangent_y: float
    geometry_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_tangent(self) -> CurveTangentSnapshot:
        if math.hypot(self.tangent_x, self.tangent_y) <= 1e-12:
            raise ValueError("PEC tangent vector must be non-zero")
        return self


class PerpendicularCurveRequest(ContractRequest):
    curves: tuple[CurveTangentSnapshot, ...] = Field(min_length=1)
    negative_length: float = Field(gt=0)
    positive_length: float = Field(gt=0)
    output_layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique(self) -> PerpendicularCurveRequest:
        if len({item.handle.casefold() for item in self.curves}) != len(self.curves):
            raise ValueError("PEC curve handles must be unique")
        return self


class ProposedPerpendicularLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    base_point: Point3D
    start_point: Point3D
    end_point: Point3D
    output_layer: str


class PerpendicularCurvePlan(Batch25bPlan):
    lines: tuple[ProposedPerpendicularLine, ...]
    negative_length: float
    positive_length: float


def plan_perpendicular_curve(request: PerpendicularCurveRequest) -> PerpendicularCurvePlan:
    lines: list[ProposedPerpendicularLine] = []
    for curve in request.curves:
        length = math.hypot(curve.tangent_x, curve.tangent_y)
        perpendicular_x = -curve.tangent_y / length
        perpendicular_y = curve.tangent_x / length
        lines.append(
            ProposedPerpendicularLine(
                source_handle=curve.handle,
                base_point=curve.base_point,
                start_point=Point3D(
                    x=curve.base_point.x - perpendicular_x * request.negative_length,
                    y=curve.base_point.y - perpendicular_y * request.negative_length,
                    z=curve.base_point.z,
                ),
                end_point=Point3D(
                    x=curve.base_point.x + perpendicular_x * request.positive_length,
                    y=curve.base_point.y + perpendicular_y * request.positive_length,
                    z=curve.base_point.z,
                ),
                output_layer=request.output_layer,
            )
        )
    return PerpendicularCurvePlan(
        command_alias="PEC",
        legacy_symbol="xiPerCurve",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify xiPerCurve and describe drawing perpendicular lines at their own positions",
        semantic_gaps=(
            "no command-specific DCL/config/data/readable source was found",
            "legacy curve sampling, side, length, count, and layer behavior are compiled",
            "this planner requires versioned tangent samples and explicit two-sided lengths and does not claim legacy equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        lines=tuple(lines),
        negative_length=request.negative_length,
        positive_length=request.positive_length,
    )


def register_headless_core_batch25b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 25B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_ttt", plan_texts_to_table),
        ("xicad_plan_tx", plan_text_box),
        ("xicad_plan_mtlt", plan_make_text_linetype),
        ("xicad_plan_pbb", plan_bounding_box),
        ("xicad_plan_pc", plan_polyline_close),
        ("xicad_plan_pec", plan_perpendicular_curve),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
