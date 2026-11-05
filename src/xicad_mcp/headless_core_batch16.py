"""Dialog-free planners for xiCAD architectural drawing batch 16."""

from __future__ import annotations

from calendar import Calendar, month_name
from collections.abc import Sequence
from enum import StrEnum
from math import radians, tan
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch14 import GeometrySnapshot


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval fingerprint")


class Batch16Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    semantic_evidence: str
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class TableCell(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    text: str


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    insertion_point: Point3D
    rows: int = Field(gt=0)
    columns: int = Field(gt=0)
    row_height: float = Field(gt=0)
    column_widths: tuple[float, ...] = Field(min_length=1)
    cells: tuple[TableCell, ...]
    grid_layer: str = Field(min_length=1)
    text_layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ScheduleRequest:
        if len(self.column_widths) != self.columns:
            raise ValueError("schedule column_widths must match columns")
        if any(cell.row >= self.rows or cell.column >= self.columns for cell in self.cells):
            raise ValueError("schedule cell is outside table bounds")
        _approval(self.dry_run, self.approval, "BLI/CLI")
        return self


class TablePlan(Batch16Plan):
    horizontal_lines: tuple[tuple[Point3D, Point3D], ...]
    vertical_lines: tuple[tuple[Point3D, Point3D], ...]
    cells: tuple[TableCell, ...]
    grid_layer: str
    text_layer: str
    text_height: float


def _schedule(request: ScheduleRequest, alias: str, symbol: str, evidence: str) -> TablePlan:
    x, y, z = request.insertion_point.x, request.insertion_point.y, request.insertion_point.z
    width = sum(request.column_widths)
    horizontal = tuple(
        (Point3D(x=x, y=y - row * request.row_height, z=z), Point3D(x=x + width, y=y - row * request.row_height, z=z))
        for row in range(request.rows + 1)
    )
    offsets = [0.0]
    for value in request.column_widths:
        offsets.append(offsets[-1] + value)
    vertical = tuple(
        (Point3D(x=x + offset, y=y, z=z), Point3D(x=x + offset, y=y - request.rows * request.row_height, z=z))
        for offset in offsets
    )
    return TablePlan(
        command_alias=alias,
        legacy_symbol=symbol,
        semantic_evidence=evidence,
        document_id=request.document_id,
        horizontal_lines=horizontal,
        vertical_lines=vertical,
        cells=request.cells,
        grid_layer=request.grid_layer,
        text_layer=request.text_layer,
        text_height=request.text_height,
        dry_run=request.dry_run,
    )


def plan_beam_schedule(request: ScheduleRequest) -> TablePlan:
    return _schedule(
        request, "BLI", "xiBeamList", "xiShortkey: 보일람표그리기; caller supplies table cells and dimensions"
    )


def plan_column_schedule(request: ScheduleRequest) -> TablePlan:
    return _schedule(
        request, "CLI", "xiColumnList", "xiColumnList DCL: 기둥 배근도 layers/scale/rebar/text; table data explicit"
    )


class PatternElement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_name: str = Field(min_length=1)
    offset: Point3D
    rotation_degrees: float = 0
    scale: float = Field(gt=0)


class BlockPatternRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    pattern_name: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    base_point: Point3D
    elements: tuple[PatternElement, ...] = Field(min_length=1)
    output_definition_only: bool = True
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> BlockPatternRequest:
        if not self.output_definition_only:
            raise ValueError("BPT direct PAT/file installation is blocked; definition output only")
        _approval(self.dry_run, self.approval, "BPT")
        return self


class BlockPatternPlan(Batch16Plan):
    command_alias: str = "BPT"
    legacy_symbol: str = "xiBPatt"
    semantic_evidence: str = "xiShortkey: 블럭 해치 패턴 만들기; file installation intentionally blocked"
    pattern_name: str
    base_point: Point3D
    elements: tuple[PatternElement, ...]
    external_write_blocked: bool = True


def plan_block_pattern(request: BlockPatternRequest) -> BlockPatternPlan:
    return BlockPatternPlan(
        document_id=request.document_id,
        pattern_name=request.pattern_name,
        base_point=request.base_point,
        elements=request.elements,
        dry_run=request.dry_run,
    )


class CalendarRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    year: int = Field(ge=1, le=9999)
    month: int = Field(ge=1, le=12)
    week_start: int = Field(ge=0, le=6)
    insertion_point: Point3D
    cell_width: float = Field(gt=0)
    cell_height: float = Field(gt=0)
    layer: str = Field(min_length=1)
    text_style: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> CalendarRequest:
        _approval(self.dry_run, self.approval, "CALENDAR")
        return self


class CalendarPlan(Batch16Plan):
    command_alias: str = "CALENDAR"
    legacy_symbol: str = "xiCalendar"
    semantic_evidence: str = "xiShortkey: 달력 그리기; year/month/week start/layout explicit"
    title: str
    weeks: tuple[tuple[int, ...], ...]
    insertion_point: Point3D
    cell_width: float
    cell_height: float
    layer: str
    text_style: str


def plan_calendar(request: CalendarRequest) -> CalendarPlan:
    weeks = tuple(tuple(week) for week in Calendar(request.week_start).monthdayscalendar(request.year, request.month))
    return CalendarPlan(
        document_id=request.document_id,
        title=f"{month_name[request.month]} {request.year}",
        weeks=weeks,
        insertion_point=request.insertion_point,
        cell_width=request.cell_width,
        cell_height=request.cell_height,
        layer=request.layer,
        text_style=request.text_style,
        dry_run=request.dry_run,
    )


class CenterMode(StrEnum):
    CENTER = "center"
    HALF_CONTOURS = "half_contours"
    DIVIDE = "divide"


class CenterPolylineRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    first_handle: str = Field(min_length=1)
    second_handle: str = Field(min_length=1)
    mode: CenterMode
    node_count: int = Field(gt=1)
    divisions: int = Field(default=2, gt=1)
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> CenterPolylineRequest:
        if self.first_handle.casefold() == self.second_handle.casefold():
            raise ValueError("CEP requires two distinct polylines")
        if self.mode is CenterMode.HALF_CONTOURS and self.divisions != 2:
            raise ValueError("CEP half_contours requires divisions=2")
        _approval(self.dry_run, self.approval, "CEP")
        return self


class CenterPolylinePlan(Batch16Plan):
    command_alias: str = "CEP"
    legacy_symbol: str = "xiCenterPoly"
    semantic_evidence: str = "xiCenterPoly DCL: center/half/arbitrary divide, node count, divide count"
    output_lines: tuple[tuple[Point3D, ...], ...]
    layer: str


def plan_center_polyline(request: CenterPolylineRequest, snapshots: Sequence[GeometrySnapshot]) -> CenterPolylinePlan:
    by_handle = {item.handle.casefold(): item for item in snapshots}
    first, second = by_handle.get(request.first_handle.casefold()), by_handle.get(request.second_handle.casefold())
    if first is None or second is None or len(first.vertices) != len(second.vertices):
        raise ValueError("CEP requires available polylines with equal explicit node counts")
    if len(first.vertices) != request.node_count:
        raise ValueError("CEP node_count must equal supplied snapshot vertices")
    fractions = (
        (0.5,)
        if request.mode is CenterMode.CENTER
        else tuple(i / request.divisions for i in range(1, request.divisions))
    )
    outputs = tuple(
        tuple(
            Point3D(x=a.x + (b.x - a.x) * fraction, y=a.y + (b.y - a.y) * fraction, z=a.z + (b.z - a.z) * fraction)
            for a, b in zip(first.vertices, second.vertices, strict=True)
        )
        for fraction in fractions
    )
    return CenterPolylinePlan(
        document_id=request.document_id, output_lines=outputs, layer=request.layer, dry_run=request.dry_run
    )


class ColumnKind(StrEnum):
    RC = "rc"
    SC = "sc"
    SRC = "src"


class ConcreteShape(StrEnum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"


class ColumnRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    insertion_points: tuple[Point3D, ...] = Field(min_length=1)
    kind: ColumnKind
    concrete_shape: ConcreteShape
    concrete_width: float = Field(gt=0)
    concrete_depth: float = Field(gt=0)
    eccentric_x: float = 0
    eccentric_y: float = 0
    steel_width: float | None = Field(default=None, gt=0)
    steel_depth: float | None = Field(default=None, gt=0)
    web_thickness: float | None = Field(default=None, gt=0)
    flange_thickness: float | None = Field(default=None, gt=0)
    steel_rotation_degrees: float = 0
    concrete_layer: str = Field(min_length=1)
    steel_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ColumnRequest:
        if self.kind in {ColumnKind.SC, ColumnKind.SRC} and any(
            value is None for value in (self.steel_width, self.steel_depth, self.web_thickness, self.flange_thickness)
        ):
            raise ValueError("COL SC/SRC requires all steel dimensions")
        _approval(self.dry_run, self.approval, "COL")
        return self


class ColumnSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    center: Point3D
    kind: ColumnKind
    concrete_shape: ConcreteShape
    concrete_width: float
    concrete_depth: float
    steel_dimensions: tuple[float, float, float, float] | None
    steel_rotation_degrees: float
    concrete_layer: str
    steel_layer: str


class ColumnPlan(Batch16Plan):
    command_alias: str = "COL"
    legacy_symbol: str = "xiDrawColumn"
    semantic_evidence: str = (
        "xiDrawColumn DCL: RC/SC/SRC, rectangle/circle, eccentricity, steel dimensions/rotation/layers"
    )
    creates: tuple[ColumnSpec, ...]


def plan_column(request: ColumnRequest) -> ColumnPlan:
    steel = None
    if request.kind in {ColumnKind.SC, ColumnKind.SRC}:
        steel = (request.steel_width, request.steel_depth, request.web_thickness, request.flange_thickness)
    creates = tuple(
        ColumnSpec(
            center=Point3D(x=p.x + request.eccentric_x, y=p.y + request.eccentric_y, z=p.z),
            kind=request.kind,
            concrete_shape=request.concrete_shape,
            concrete_width=request.concrete_width,
            concrete_depth=request.concrete_depth,
            steel_dimensions=steel,
            steel_rotation_degrees=request.steel_rotation_degrees,
            concrete_layer=request.concrete_layer,
            steel_layer=request.steel_layer,
        )
        for p in request.insertion_points
    )
    return ColumnPlan(document_id=request.document_id, creates=creates, dry_run=request.dry_run)


class CurtainType(StrEnum):
    CURTAIN_WALL = "curtain_wall"
    FIXED_WINDOW = "fixed_window"


class BarPlacement(StrEnum):
    INSIDE = "inside"
    CENTER = "center"


class CurtainWallRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    baseline: tuple[Point3D, ...] = Field(min_length=2)
    kind: CurtainType
    divisions: int = Field(gt=0)
    bar_width: float = Field(gt=0)
    bar_depth: float = Field(gt=0)
    cap_enabled: bool
    cap_width: float | None = Field(default=None, gt=0)
    cap_depth: float | None = Field(default=None, gt=0)
    placement: BarPlacement
    glass_thickness: float = Field(gt=0)
    glass_layer: str = Field(min_length=1)
    bar_layer: str = Field(min_length=1)
    elevation_layer: str = Field(min_length=1)
    straighten_curves: bool
    group_output: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> CurtainWallRequest:
        if self.cap_enabled and (self.cap_width is None or self.cap_depth is None):
            raise ValueError("CW cap requires cap_width and cap_depth")
        if len(self.baseline) > 2 and not self.straighten_curves:
            raise ValueError("CW curved bar/glass offsets are blocked without curve parameterization")
        _approval(self.dry_run, self.approval, "CW")
        return self


class CurtainWallPlan(Batch16Plan):
    command_alias: str = "CW"
    legacy_symbol: str = "xiCWALL"
    semantic_evidence: str = "xiCWall DCL: type/divisions/cap/bar/glass/placement/layers/curve/group settings"
    baseline: tuple[Point3D, ...]
    division_fractions: tuple[float, ...]
    request_spec: CurtainWallRequest


def plan_curtain_wall(request: CurtainWallRequest) -> CurtainWallPlan:
    return CurtainWallPlan(
        document_id=request.document_id,
        baseline=request.baseline,
        division_fractions=tuple(i / request.divisions for i in range(1, request.divisions)),
        request_spec=request,
        dry_run=request.dry_run,
    )


class DoorVariant(StrEnum):
    D1 = "d1"
    D2 = "d2"
    D3 = "d3"


class DoorSwing(StrEnum):
    ONE_WAY = "one_way"
    DOUBLE_ACTING = "double_acting"


class DoorLeafDivision(StrEnum):
    EQUAL = "equal"
    TWO_TO_ONE = "two_to_one"
    ONE_FIXED = "one_fixed"


class SwingDisplay(StrEnum):
    ARC = "arc"
    LINE = "line"
    NONE = "none"


class DoorRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    variant: DoorVariant
    hinge_point: Point3D
    opening_end_point: Point3D
    wall_depth: float = Field(gt=0)
    offset: float = Field(ge=0)
    swing: DoorSwing
    leaf_division: DoorLeafDivision
    opening_angle_degrees: float = Field(gt=0, le=180)
    frame_width: float = Field(gt=0)
    leaf_thickness: float = Field(gt=0)
    threshold_depth: float = Field(ge=0)
    swing_display: SwingDisplay
    frame_layer: str = Field(min_length=1)
    swing_layer: str = Field(min_length=1)
    elevation_layer: str = Field(min_length=1)
    group_output: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DoorRequest:
        if self.hinge_point == self.opening_end_point:
            raise ValueError("door opening endpoints must be distinct")
        _approval(self.dry_run, self.approval, self.variant.value.upper())
        return self


class DoorPlan(Batch16Plan):
    variant: DoorVariant
    opening_line: tuple[Point3D, Point3D]
    leaf_ratios: tuple[float, ...]
    request_spec: DoorRequest


def plan_door(request: DoorRequest) -> DoorPlan:
    ratios = {
        DoorLeafDivision.EQUAL: (0.5, 0.5),
        DoorLeafDivision.TWO_TO_ONE: (2 / 3, 1 / 3),
        DoorLeafDivision.ONE_FIXED: (0.5, 0.5),
    }[request.leaf_division]
    symbol = "xiDoor1" if request.variant is DoorVariant.D1 else "xiDoor2"
    evidence = "xiDoor1 DCL" if request.variant is DoorVariant.D1 else "xiDoor2 DCL (D2/D3 variants)"
    return DoorPlan(
        command_alias=request.variant.value.upper(),
        legacy_symbol=symbol,
        semantic_evidence=f"{evidence}: swing/division/angle/frame/threshold/display/layers/group",
        document_id=request.document_id,
        variant=request.variant,
        opening_line=(request.hinge_point, request.opening_end_point),
        leaf_ratios=ratios,
        request_spec=request,
        dry_run=request.dry_run,
    )


class ExplodedViewRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    station_points: tuple[Point3D, ...] = Field(min_length=2)
    base_height: float
    draw_horizontal: bool
    draw_vertical: bool
    border_layer: str = Field(min_length=1)
    separator_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ExplodedViewRequest:
        if not self.draw_horizontal and not self.draw_vertical:
            raise ValueError("DEV must draw at least one border direction")
        _approval(self.dry_run, self.approval, "DEV")
        return self


class ExplodedViewPlan(Batch16Plan):
    command_alias: str = "DEV"
    legacy_symbol: str = "xiDrawExplodedView"
    semantic_evidence: str = "xiDrawExplodedView DCL: border/separator layers, base height, horizontal/vertical toggles"
    station_points: tuple[Point3D, ...]
    base_height: float
    horizontal_lines: tuple[tuple[Point3D, Point3D], ...]
    vertical_points: tuple[Point3D, ...]
    border_layer: str
    separator_layer: str


def plan_exploded_view(request: ExplodedViewRequest) -> ExplodedViewPlan:
    horizontal = ()
    if request.draw_horizontal:
        horizontal = ((request.station_points[0], request.station_points[-1]),)
    vertical = request.station_points if request.draw_vertical else ()
    return ExplodedViewPlan(
        document_id=request.document_id,
        station_points=request.station_points,
        base_height=request.base_height,
        horizontal_lines=horizontal,
        vertical_points=vertical,
        border_layer=request.border_layer,
        separator_layer=request.separator_layer,
        dry_run=request.dry_run,
    )


class EscalatorStyle(StrEnum):
    STYLE1 = "style1"
    STYLE2 = "style2"
    STYLE3 = "style3"


class EscalatorElevationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    insertion_point: Point3D
    style: EscalatorStyle
    floors: int = Field(gt=0)
    floor_height: float = Field(gt=0)
    angle_degrees: int
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> EscalatorElevationRequest:
        if self.angle_degrees not in {30, 35}:
            raise ValueError("EED DCL supports only 30 or 35 degrees")
        _approval(self.dry_run, self.approval, "EED")
        return self


class EscalatorElevationPlan(Batch16Plan):
    command_alias: str = "EED"
    legacy_symbol: str = "xiEED"
    semantic_evidence: str = "xiEED DCL: three styles, floor count/height, 30/35 degree width calculation, layer"
    style: EscalatorStyle
    rise: float
    run: float
    endpoints: tuple[Point3D, Point3D]
    layer: str


def plan_escalator_elevation(request: EscalatorElevationRequest) -> EscalatorElevationPlan:
    rise = request.floors * request.floor_height
    run = rise / tan(radians(request.angle_degrees))
    end = Point3D(x=request.insertion_point.x + run, y=request.insertion_point.y + rise, z=request.insertion_point.z)
    return EscalatorElevationPlan(
        document_id=request.document_id,
        style=request.style,
        rise=rise,
        run=run,
        endpoints=(request.insertion_point, end),
        layer=request.layer,
        dry_run=request.dry_run,
    )


def register_headless_core_batch16_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 16 Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    def register(name: str):
        return lambda function: mcp.tool(name=name, annotations=annotations)(function)

    @register("xicad_plan_bli")
    def bli_tool(request: ScheduleRequest) -> TablePlan:
        return plan_beam_schedule(request)

    @register("xicad_plan_bpt")
    def bpt_tool(request: BlockPatternRequest) -> BlockPatternPlan:
        return plan_block_pattern(request)

    @register("xicad_plan_calendar")
    def calendar_tool(request: CalendarRequest) -> CalendarPlan:
        return plan_calendar(request)

    @register("xicad_plan_cep")
    def cep_tool(request: CenterPolylineRequest, snapshots: tuple[GeometrySnapshot, ...]) -> CenterPolylinePlan:
        return plan_center_polyline(request, snapshots)

    @register("xicad_plan_cli")
    def cli_tool(request: ScheduleRequest) -> TablePlan:
        return plan_column_schedule(request)

    @register("xicad_plan_col")
    def col_tool(request: ColumnRequest) -> ColumnPlan:
        return plan_column(request)

    @register("xicad_plan_cw")
    def cw_tool(request: CurtainWallRequest) -> CurtainWallPlan:
        return plan_curtain_wall(request)

    @register("xicad_plan_d1")
    def d1_tool(request: DoorRequest) -> DoorPlan:
        if request.variant is not DoorVariant.D1:
            raise ValueError("D1 requires variant=d1")
        return plan_door(request)

    @register("xicad_plan_d2")
    def d2_tool(request: DoorRequest) -> DoorPlan:
        if request.variant is not DoorVariant.D2:
            raise ValueError("D2 requires variant=d2")
        return plan_door(request)

    @register("xicad_plan_d3")
    def d3_tool(request: DoorRequest) -> DoorPlan:
        if request.variant is not DoorVariant.D3:
            raise ValueError("D3 requires variant=d3")
        return plan_door(request)

    @register("xicad_plan_dev")
    def dev_tool(request: ExplodedViewRequest) -> ExplodedViewPlan:
        return plan_exploded_view(request)

    @register("xicad_plan_eed")
    def eed_tool(request: EscalatorElevationRequest) -> EscalatorElevationPlan:
        return plan_escalator_elevation(request)
