"""Evidence-led headless contracts for xiCAD hatch/table batch 19A."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval fingerprint")


class Batch19APlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    semantic_evidence: str
    semantic_gaps: tuple[str, ...] = ()
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class HatchDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    loops: tuple[tuple[Point3D, ...], ...] = Field(min_length=1)
    pattern_name: str = Field(min_length=1)
    pattern_scale: float = Field(gt=0)
    pattern_angle_degrees: float
    color: int = Field(ge=0, le=256)
    layer: str = Field(min_length=1)
    associative: bool
    is_xref: bool = False
    locked_layer: bool = False


class HatchMergeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=2)
    require_identical_properties: bool = True
    delete_sources: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> HatchMergeRequest:
        if len({handle.casefold() for handle in self.source_handles}) != len(self.source_handles):
            raise ValueError("HM source handles must be unique")
        if not self.require_identical_properties:
            raise ValueError("HM property coercion is blocked because legacy precedence is unrecovered")
        _approval(self.dry_run, self.approval, "HM")
        return self


class HatchMergePlan(Batch19APlan):
    command_alias: str = "HM"
    legacy_symbol: str = "xiHatchMerge"
    semantic_evidence: str = "frozen shortcut only: 해치 합치기; exact property precedence unavailable"
    semantic_gaps: tuple[str, ...] = ("legacy property precedence", "associativity result")
    merged_definition: HatchDefinition
    delete_handles: tuple[str, ...]


def plan_hatch_merge(request: HatchMergeRequest, snapshots: Sequence[HatchDefinition]) -> HatchMergePlan:
    by = {item.handle.casefold(): item for item in snapshots}
    selected = []
    for handle in request.source_handles:
        item = by.get(handle.casefold())
        if item is None or item.is_xref or item.locked_layer:
            raise ValueError(f"HM hatch unavailable: {handle}")
        selected.append(item)
    first = selected[0]
    signature = (
        first.pattern_name.casefold(),
        first.pattern_scale,
        first.pattern_angle_degrees,
        first.color,
        first.layer.casefold(),
    )
    if any(
        (
            item.pattern_name.casefold(),
            item.pattern_scale,
            item.pattern_angle_degrees,
            item.color,
            item.layer.casefold(),
        )
        != signature
        for item in selected[1:]
    ):
        raise ValueError("HM requires identical hatch properties")
    merged = first.model_copy(
        update={
            "handle": "<new>",
            "loops": tuple(loop for item in selected for loop in item.loops),
            "associative": False,
        }
    )
    return HatchMergePlan(
        document_id=request.document_id,
        merged_definition=merged,
        delete_handles=request.source_handles if request.delete_sources else (),
        dry_run=request.dry_run,
    )


class PatternWorkMode(StrEnum):
    DRAW = "draw"
    SAVE = "save"


class PatternLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    angle_degrees: float
    origin_x: float
    origin_y: float
    delta_x: float
    delta_y: float
    dashes: tuple[float, ...] = ()


class HatchPatternRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    mode: PatternWorkMode
    pattern_name: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    description: str
    lines: tuple[PatternLine, ...] = Field(min_length=1)
    cell_origin: Point3D
    for_revit_model: bool
    output_definition_only: bool = True
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> HatchPatternRequest:
        if self.mode is PatternWorkMode.SAVE or not self.output_definition_only:
            raise ValueError("HPM external PAT save is blocked; request draw with definition output only")
        _approval(self.dry_run, self.approval, "HPM")
        return self


class HatchPatternPlan(Batch19APlan):
    command_alias: str = "HPM"
    legacy_symbol: str = "xiMakeHatchPtn"
    semantic_evidence: str = "AutoSave/XiCAD00s.dcl: draw/save, folder, PAT name/description, Revit model marker"
    semantic_gaps: tuple[str, ...] = ("legacy geometry-to-PAT conversion rules",)
    pattern_name: str
    description: str
    lines: tuple[PatternLine, ...]
    cell_origin: Point3D
    header_markers: tuple[str, ...]
    external_write_blocked: bool = True


def plan_hatch_pattern(request: HatchPatternRequest) -> HatchPatternPlan:
    markers = (";%TYPE=MODEL",) if request.for_revit_model else ()
    return HatchPatternPlan(
        document_id=request.document_id,
        pattern_name=request.pattern_name,
        description=request.description,
        lines=request.lines,
        cell_origin=request.cell_origin,
        header_markers=markers,
        dry_run=request.dry_run,
    )


class RandomSelectionMode(StrEnum):
    EXPLICIT = "explicit"
    LEGACY_RANDOM = "legacy_random"


class RandomSolidRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    candidate_boundary_handles: tuple[str, ...] = Field(min_length=1)
    selection_mode: RandomSelectionMode
    selected_boundary_handles: tuple[str, ...] = Field(min_length=1)
    layer: str = Field(min_length=1)
    color: int = Field(ge=0, le=256)
    associative: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> RandomSolidRequest:
        if self.selection_mode is RandomSelectionMode.LEGACY_RANDOM:
            raise ValueError("RDS legacy random distribution is unrecovered; use explicit selection")
        candidates = {handle.casefold() for handle in self.candidate_boundary_handles}
        if any(handle.casefold() not in candidates for handle in self.selected_boundary_handles):
            raise ValueError("RDS selected boundaries must be candidates")
        _approval(self.dry_run, self.approval, "RDS")
        return self


class SolidHatchSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    boundary_handle: str
    pattern_name: str = "SOLID"
    layer: str
    color: int
    associative: bool


class RandomSolidPlan(Batch19APlan):
    command_alias: str = "RDS"
    legacy_symbol: str = "xiRandomSolid"
    semantic_evidence: str = "current+frozen shortcut: 무작위 솔리드해치; no DCL/config random algorithm found"
    semantic_gaps: tuple[str, ...] = ("legacy random distribution", "selection probability and seed behavior")
    creates: tuple[SolidHatchSpec, ...]


def plan_random_solid(request: RandomSolidRequest) -> RandomSolidPlan:
    creates = tuple(
        SolidHatchSpec(
            boundary_handle=handle, layer=request.layer, color=request.color, associative=request.associative
        )
        for handle in request.selected_boundary_handles
    )
    return RandomSolidPlan(document_id=request.document_id, creates=creates, dry_run=request.dry_run)


class SolidHatchRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    boundary_handles: tuple[str, ...] = Field(min_length=1)
    layer: str = Field(min_length=1)
    color: int = Field(ge=0, le=256)
    associative: bool
    island_detection: str = Field(pattern=r"^(normal|outer|ignore)$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SolidHatchRequest:
        if len({handle.casefold() for handle in self.boundary_handles}) != len(self.boundary_handles):
            raise ValueError("SOL boundary handles must be unique")
        _approval(self.dry_run, self.approval, "SOL")
        return self


class SolidHatchPlan(Batch19APlan):
    command_alias: str = "SOL"
    legacy_symbol: str = "xiSOLID"
    semantic_evidence: str = "current+frozen shortcut: 솔리드 해치하기; ZWCAD PAT confirms *SOLID fill"
    semantic_gaps: tuple[str, ...] = ("legacy boundary prompting and island defaults",)
    creates: tuple[SolidHatchSpec, ...]
    island_detection: str


def plan_solid_hatch(request: SolidHatchRequest) -> SolidHatchPlan:
    return SolidHatchPlan(
        document_id=request.document_id,
        creates=tuple(
            SolidHatchSpec(
                boundary_handle=handle, layer=request.layer, color=request.color, associative=request.associative
            )
            for handle in request.boundary_handles
        ),
        island_detection=request.island_detection,
        dry_run=request.dry_run,
    )


class TableKind(StrEnum):
    GENERAL = "general"
    CAD_TABLE = "cad_table"


class TableMethod(StrEnum):
    DIVIDE_EXTENTS = "divide_extents"
    EXPLICIT_SPACING = "explicit_spacing"


class TableRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    insertion_point: Point3D
    kind: TableKind
    method: TableMethod
    row_count: int = Field(gt=0)
    column_count: int = Field(gt=0)
    row_heights: tuple[float, ...] = Field(min_length=1)
    column_widths: tuple[float, ...] = Field(min_length=1)
    approximate_division: bool
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TableRequest:
        if len(self.row_heights) != self.row_count or len(self.column_widths) != self.column_count:
            raise ValueError("TB row/column sizes must match counts")
        if self.method is TableMethod.DIVIDE_EXTENTS and (
            len(set(self.row_heights)) != 1 or len(set(self.column_widths)) != 1
        ):
            raise ValueError("TB divide_extents requires uniform row and column sizes")
        _approval(self.dry_run, self.approval, "TB")
        return self


class TablePlan(Batch19APlan):
    command_alias: str = "TB"
    legacy_symbol: str = "xiTable"
    semantic_evidence: str = "AutoSave/ACAD_xi0295_d.01.dcl: general/CAD table, divide/input method, layer, row/column count/size, nearest division"
    semantic_gaps: tuple[str, ...] = ("legacy table style selection",)
    request_spec: TableRequest
    x_offsets: tuple[float, ...]
    y_offsets: tuple[float, ...]


def plan_table(request: TableRequest) -> TablePlan:
    x = [0.0]
    for width in request.column_widths:
        x.append(x[-1] + width)
    y = [0.0]
    for height in request.row_heights:
        y.append(y[-1] - height)
    return TablePlan(
        document_id=request.document_id,
        request_spec=request,
        x_offsets=tuple(x),
        y_offsets=tuple(y),
        dry_run=request.dry_run,
    )


class TableTextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    row_count: int = Field(gt=0)
    column_count: int = Field(gt=0)
    locked_layer: bool = False


class TableTextCell(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    text: str


class TableTextRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    table_handle: str = Field(min_length=1)
    cells: tuple[TableTextCell, ...] = Field(min_length=1)
    overwrite_nonempty: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TableTextRequest:
        positions = [(cell.row, cell.column) for cell in self.cells]
        if len(positions) != len(set(positions)):
            raise ValueError("TBT cell positions must be unique")
        _approval(self.dry_run, self.approval, "TBT")
        return self


class TableTextPlan(Batch19APlan):
    command_alias: str = "TBT"
    legacy_symbol: str = "xiTableText"
    semantic_evidence: str = "frozen shortcut only: ACAD 테이블에 문자 넣기; no current shortcut or DCL found"
    semantic_gaps: tuple[str, ...] = ("legacy cell traversal order", "text formatting and merge behavior")
    table_handle: str
    cells: tuple[TableTextCell, ...]
    overwrite_nonempty: bool


def plan_table_text(request: TableTextRequest, snapshots: Sequence[TableTextSnapshot]) -> TableTextPlan:
    table = next((item for item in snapshots if item.handle.casefold() == request.table_handle.casefold()), None)
    if table is None or table.locked_layer:
        raise ValueError("TBT table unavailable")
    if any(cell.row >= table.row_count or cell.column >= table.column_count for cell in request.cells):
        raise ValueError("TBT cell outside table bounds")
    return TableTextPlan(
        document_id=request.document_id,
        table_handle=table.handle,
        cells=request.cells,
        overwrite_nonempty=request.overwrite_nonempty,
        dry_run=request.dry_run,
    )


def register_headless_core_batch19a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 19A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    def register(name: str):
        return lambda function: mcp.tool(name=name, annotations=annotations)(function)

    @register("xicad_plan_hm")
    def hm_tool(request: HatchMergeRequest, snapshots: tuple[HatchDefinition, ...]) -> HatchMergePlan:
        return plan_hatch_merge(request, snapshots)

    @register("xicad_plan_hpm")
    def hpm_tool(request: HatchPatternRequest) -> HatchPatternPlan:
        return plan_hatch_pattern(request)

    @register("xicad_plan_rds")
    def rds_tool(request: RandomSolidRequest) -> RandomSolidPlan:
        return plan_random_solid(request)

    @register("xicad_plan_sol")
    def sol_tool(request: SolidHatchRequest) -> SolidHatchPlan:
        return plan_solid_hatch(request)

    @register("xicad_plan_tb")
    def tb_tool(request: TableRequest) -> TablePlan:
        return plan_table(request)

    @register("xicad_plan_tbt")
    def tbt_tool(request: TableTextRequest, snapshots: tuple[TableTextSnapshot, ...]) -> TableTextPlan:
        return plan_table_text(request, snapshots)
