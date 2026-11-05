"""Evidence-bounded deterministic planners for xiCAD drawing-frame batch 23A."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


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


class Batch23APlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    semantic_evidence: str
    semantic_gaps: tuple[str, ...]
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class FramePlacement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_reference_handle: str = Field(min_length=1)
    source_anchor: Point3D
    target_anchor: Point3D


class FrameSortRequest(ContractRequest):
    placements: tuple[FramePlacement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_placements(self) -> FrameSortRequest:
        _unique(tuple(item.block_reference_handle for item in self.placements), "DBS")
        if any(item.source_anchor == item.target_anchor for item in self.placements):
            raise ValueError("DBS placements must move every supplied frame")
        return self


class FrameMove(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_reference_handle: str
    displacement: Point3D


class FrameSortPlan(Batch23APlan):
    moves: tuple[FrameMove, ...]


def plan_frame_sort(request: FrameSortRequest) -> FrameSortPlan:
    return FrameSortPlan(
        command_alias="DBS",
        legacy_symbol="xiDboxSort",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current+frozen shortcut: 도곽 정렬; target anchors are caller-supplied",
        semantic_gaps=("legacy spatial order", "spacing derivation", "frame detection", "rotation policy"),
        moves=tuple(
            FrameMove(
                block_reference_handle=item.block_reference_handle,
                displacement=Point3D(
                    x=item.target_anchor.x - item.source_anchor.x,
                    y=item.target_anchor.y - item.source_anchor.y,
                    z=item.target_anchor.z - item.source_anchor.z,
                ),
            )
            for item in request.placements
        ),
    )


class PaperSize(StrEnum):
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"


class DrawingUnit(StrEnum):
    MILLIMETER = "mm"
    METER = "m"


class FrameExtent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    block_reference_handle: str = Field(min_length=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class FindFrameScaleRequest(ContractRequest):
    frames: tuple[FrameExtent, ...] = Field(min_length=1)
    paper_size: PaperSize
    drawing_unit: DrawingUnit
    allow_rotated_sheet: bool
    relative_tolerance: float = Field(default=0.005, gt=0, lt=1)
    proposed_ltscale: float | None = Field(default=None, gt=0)
    proposed_dimscale: float | None = Field(default=None, gt=0)
    ask_before_apply: bool = True

    @model_validator(mode="after")
    def validate_frames(self) -> FindFrameScaleRequest:
        _unique(tuple(frame.block_reference_handle for frame in self.frames), "DFS")
        return self


class ScaleFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_reference_handle: str
    scale_denominator: float
    width_scale: float
    height_scale: float
    within_tolerance: bool
    rotated_sheet: bool


class SystemVariableProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    value: float
    requires_confirmation: bool


class FindFrameScalePlan(Batch23APlan):
    findings: tuple[ScaleFinding, ...]
    system_variable_proposals: tuple[SystemVariableProposal, ...]


_PAPER_MM: dict[PaperSize, tuple[float, float]] = {
    PaperSize.A0: (1189, 841),
    PaperSize.A1: (841, 594),
    PaperSize.A2: (594, 420),
    PaperSize.A3: (420, 297),
    PaperSize.A4: (297, 210),
}


def plan_find_frame_scale(request: FindFrameScaleRequest) -> FindFrameScalePlan:
    paper_width, paper_height = _PAPER_MM[request.paper_size]
    unit_factor = 1 if request.drawing_unit is DrawingUnit.MILLIMETER else 1000
    findings = []
    for frame in request.frames:
        width_mm, height_mm = frame.width * unit_factor, frame.height * unit_factor
        normal = (width_mm / paper_width, height_mm / paper_height, False)
        rotated = (width_mm / paper_height, height_mm / paper_width, True)
        candidates = (normal, rotated) if request.allow_rotated_sheet else (normal,)
        width_scale, height_scale, is_rotated = min(candidates, key=lambda item: abs(item[0] - item[1]))
        denominator = (width_scale + height_scale) / 2
        relative_error = abs(width_scale - height_scale) / denominator
        findings.append(
            ScaleFinding(
                block_reference_handle=frame.block_reference_handle,
                scale_denominator=denominator,
                width_scale=width_scale,
                height_scale=height_scale,
                within_tolerance=relative_error <= request.relative_tolerance,
                rotated_sheet=is_rotated,
            )
        )
    proposals = tuple(
        SystemVariableProposal(name=name, value=value, requires_confirmation=request.ask_before_apply)
        for name, value in (("LTSCALE", request.proposed_ltscale), ("DIMSCALE", request.proposed_dimscale))
        if value is not None
    )
    return FindFrameScalePlan(
        command_alias="DFS",
        legacy_symbol="xiDboxFindScale",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="DCL exposes A0-A4, mm/m, LTSCALE, DIMSCALE and ask-before-apply controls",
        semantic_gaps=("legacy frame extent extraction", "legacy rounding/display format", "text-output creation"),
        findings=tuple(findings),
        system_variable_proposals=proposals,
    )


class NestedDimensionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    block_reference_handle: str = Field(min_length=1)
    dimension_handle: str = Field(min_length=1)
    current_dimscale: float = Field(gt=0)


class ChangeBlockDimensionScaleRequest(ContractRequest):
    dimensions: tuple[NestedDimensionSnapshot, ...] = Field(min_length=1)
    target_dimscale: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_dimensions(self) -> ChangeBlockDimensionScaleRequest:
        _unique(tuple(item.dimension_handle for item in self.dimensions), "DSB")
        if all(item.current_dimscale == self.target_dimscale for item in self.dimensions):
            raise ValueError("DSB requires at least one dimension scale change")
        return self


class DimensionScaleUpdate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_reference_handle: str
    dimension_handle: str
    old_dimscale: float
    new_dimscale: float


class ChangeBlockDimensionScalePlan(Batch23APlan):
    updates: tuple[DimensionScaleUpdate, ...]


def plan_change_block_dimension_scale(request: ChangeBlockDimensionScaleRequest) -> ChangeBlockDimensionScalePlan:
    return ChangeBlockDimensionScalePlan(
        command_alias="DSB",
        legacy_symbol="xiDimScaleBlock",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current+frozen shortcut: 도곽 블럭내부 치수축척 일괄변경",
        semantic_gaps=("nested dimension discovery", "annotative dimensions", "block-definition versus instance scope"),
        updates=tuple(
            DimensionScaleUpdate(
                block_reference_handle=item.block_reference_handle,
                dimension_handle=item.dimension_handle,
                old_dimscale=item.current_dimscale,
                new_dimscale=request.target_dimscale,
            )
            for item in request.dimensions
            if item.current_dimscale != request.target_dimscale
        ),
    )


class DrawingListRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    frame_handle: str = Field(min_length=1)
    drawing_number: str
    drawing_name: str
    a1_scale: str
    a3_scale: str
    revision: str = ""


class MakeDrawingListRequest(ContractRequest):
    ordered_records: tuple[DrawingListRecord, ...] = Field(min_length=1)
    list_scale: float = Field(gt=0)
    text_height: float = Field(gt=0)
    line_gap: float = Field(gt=0)
    column_gaps: tuple[float, float, float, float] = Field()
    title_prefix: str = ""
    text_layer: str = Field(min_length=1)
    line_layer: str = Field(min_length=1)
    show_vertical_lines: bool = True

    @model_validator(mode="after")
    def validate_records(self) -> MakeDrawingListRequest:
        _unique(tuple(item.frame_handle for item in self.ordered_records), "MDL")
        if any(gap <= 0 for gap in self.column_gaps):
            raise ValueError("MDL column gaps must be positive")
        return self


class DrawingListRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    ordinal: int
    values: tuple[str, str, str, str, str]


class MakeDrawingListPlan(Batch23APlan):
    rows: tuple[DrawingListRow, ...]
    list_scale: float
    text_height: float
    line_gap: float
    column_gaps: tuple[float, float, float, float]
    text_layer: str
    line_layer: str
    show_vertical_lines: bool


def plan_make_drawing_list(request: MakeDrawingListRequest) -> MakeDrawingListPlan:
    rows = tuple(
        DrawingListRow(
            ordinal=index,
            values=(
                record.drawing_number,
                request.title_prefix + record.drawing_name,
                record.a1_scale,
                record.a3_scale,
                record.revision,
            ),
        )
        for index, record in enumerate(request.ordered_records, start=1)
    )
    return MakeDrawingListPlan(
        command_alias="MDL",
        legacy_symbol="xiMakeDwgList",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="DCL exposes ordered frame records and drawing-number/name/A1/A3/revision table columns",
        semantic_gaps=("attribute extraction", "registered-frame matching", "table insertion point", "multi-file I/O"),
        rows=rows,
        list_scale=request.list_scale,
        text_height=request.text_height,
        line_gap=request.line_gap,
        column_gaps=request.column_gaps,
        text_layer=request.text_layer,
        line_layer=request.line_layer,
        show_vertical_lines=request.show_vertical_lines,
    )


class Box2D(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    minimum_x: float
    minimum_y: float
    maximum_x: float
    maximum_y: float

    @model_validator(mode="after")
    def validate_box(self) -> Box2D:
        if self.minimum_x >= self.maximum_x or self.minimum_y >= self.maximum_y:
            raise ValueError("box extents must increase in X and Y")
        return self


class PlotBoundarySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_reference_handle: str = Field(min_length=1)
    expected_boundary: Box2D
    observed_boundary: Box2D | None = None


class CheckPlotBoxRequest(ContractRequest):
    frames: tuple[PlotBoundarySnapshot, ...] = Field(min_length=1)
    coordinate_tolerance: float = Field(default=1e-6, ge=0)

    @model_validator(mode="after")
    def validate_frames(self) -> CheckPlotBoxRequest:
        _unique(tuple(item.block_reference_handle for item in self.frames), "PBS")
        return self


class PlotBoundaryFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_reference_handle: str
    status: str
    maximum_coordinate_delta: float | None


class CheckPlotBoxPlan(Batch23APlan):
    findings: tuple[PlotBoundaryFinding, ...]


def plan_check_plot_box(request: CheckPlotBoxRequest) -> CheckPlotBoxPlan:
    findings = []
    for frame in request.frames:
        if frame.observed_boundary is None:
            findings.append(
                PlotBoundaryFinding(
                    block_reference_handle=frame.block_reference_handle,
                    status="missing_observed_boundary",
                    maximum_coordinate_delta=None,
                )
            )
            continue
        expected = frame.expected_boundary
        observed = frame.observed_boundary
        delta = max(
            abs(expected.minimum_x - observed.minimum_x),
            abs(expected.minimum_y - observed.minimum_y),
            abs(expected.maximum_x - observed.maximum_x),
            abs(expected.maximum_y - observed.maximum_y),
        )
        findings.append(
            PlotBoundaryFinding(
                block_reference_handle=frame.block_reference_handle,
                status="matched" if delta <= request.coordinate_tolerance else "mismatched",
                maximum_coordinate_delta=delta,
            )
        )
    return CheckPlotBoxPlan(
        command_alias="PBS",
        legacy_symbol="xiPPlotBox",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current+frozen shortcut: 블럭도곽 경계 확인; both expected and observed bounds are explicit",
        semantic_gaps=("plot-boundary discovery", "accepted entity type", "legacy visual marking"),
        findings=tuple(findings),
    )


class NumberingTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_reference_handle: str = Field(min_length=1)
    attribute_handle: str = Field(min_length=1)
    attribute_tag: str = Field(min_length=1)
    old_text: str


class TitleNumberingRequest(ContractRequest):
    ordered_targets: tuple[NumberingTarget, ...] = Field(min_length=1)
    prefix: str = ""
    starting_number: int
    step: int
    suffix: str = ""
    zero_pad_width: int = Field(default=0, ge=0, le=32)

    @model_validator(mode="after")
    def validate_targets(self) -> TitleNumberingRequest:
        _unique(tuple(item.block_reference_handle for item in self.ordered_targets), "TN block")
        _unique(tuple(item.attribute_handle for item in self.ordered_targets), "TN attribute")
        if self.step == 0:
            raise ValueError("TN numbering step must be non-zero")
        return self


class AttributeTextUpdate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_reference_handle: str
    attribute_handle: str
    attribute_tag: str
    old_text: str
    new_text: str


class TitleNumberingPlan(Batch23APlan):
    updates: tuple[AttributeTextUpdate, ...]


def plan_title_numbering(request: TitleNumberingRequest) -> TitleNumberingPlan:
    updates = []
    for index, target in enumerate(request.ordered_targets):
        number = request.starting_number + index * request.step
        digits = str(abs(number)).zfill(request.zero_pad_width)
        rendered = ("-" if number < 0 else "") + digits
        updates.append(
            AttributeTextUpdate(
                block_reference_handle=target.block_reference_handle,
                attribute_handle=target.attribute_handle,
                attribute_tag=target.attribute_tag,
                old_text=target.old_text,
                new_text=request.prefix + rendered + request.suffix,
            )
        )
    return TitleNumberingPlan(
        command_alias="TN",
        legacy_symbol="xiTitleNumbering",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="DCL exposes block attribute, prefix, number, suffix, step, workspace and explicit order",
        semantic_gaps=("frame/attribute discovery", "spatial ordering", "multi-file I/O", "legacy zero-padding default"),
        updates=tuple(updates),
    )


def _unique(handles: tuple[str, ...], alias: str) -> None:
    folded = [handle.casefold() for handle in handles]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{alias} handles must be unique")


def register_headless_core_batch23a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 23A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_dbs", plan_frame_sort),
        ("xicad_plan_dfs", plan_find_frame_scale),
        ("xicad_plan_dsb", plan_change_block_dimension_scale),
        ("xicad_plan_mdl", plan_make_drawing_list),
        ("xicad_plan_pbs", plan_check_plot_box),
        ("xicad_plan_tn", plan_title_numbering),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
