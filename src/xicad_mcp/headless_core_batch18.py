"""Dialog-free xiCAD planners for stairs, openings, tables and hatches."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import hypot
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch17 import HatchSnapshot


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval fingerprint")


class Batch18Plan(BaseModel):
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


class StairPlanKind(StrEnum):
    STRAIGHT = "straight"
    TURNING = "turning"


class StairDirection(StrEnum):
    UP = "up"
    DOWN = "down"
    BOTH = "both"


class StairPlanRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    origin: Point3D
    kind: StairPlanKind
    direction: StairDirection
    flight_width: float = Field(gt=0)
    start_gap: float = Field(ge=0)
    step_count: int = Field(gt=0)
    tread_depth: float = Field(gt=0)
    flight_gap: float = Field(ge=0)
    landing_width: float = Field(gt=0)
    handrail_enabled: bool
    handrail_width: float | None = Field(default=None, gt=0)
    arrow_enabled: bool
    cut_line_enabled: bool
    anti_slip_enabled: bool
    stair_layer: str = Field(min_length=1)
    handrail_layer: str = Field(min_length=1)
    symbol_layer: str = Field(min_length=1)
    text_layer: str = Field(min_length=1)
    number_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> StairPlanRequest:
        if self.handrail_enabled and self.handrail_width is None:
            raise ValueError("STP handrail requires handrail_width")
        _approval(self.dry_run, self.approval, "STP")
        return self


class StairPlanPlan(Batch18Plan):
    command_alias: str = "STP"
    legacy_symbol: str = "xiSTP"
    semantic_evidence: str = (
        "xiSTP DCL: straight/turning, direction, gap/count/depth/landing, handrail/arrow/cut/anti-slip/layers"
    )
    tread_lines: tuple[tuple[Point3D, Point3D], ...]
    request_spec: StairPlanRequest


def plan_stair_plan(request: StairPlanRequest) -> StairPlanPlan:
    x = request.origin.x + request.start_gap
    lines = tuple(
        (
            Point3D(x=x + i * request.tread_depth, y=request.origin.y, z=request.origin.z),
            Point3D(x=x + i * request.tread_depth, y=request.origin.y + request.flight_width, z=request.origin.z),
        )
        for i in range(request.step_count + 1)
    )
    return StairPlanPlan(
        document_id=request.document_id, tread_lines=lines, request_spec=request, dry_run=request.dry_run
    )


class CadTableSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    cells: tuple[tuple[str, ...], ...] = Field(min_length=1)
    column_widths: tuple[float, ...] = Field(min_length=1)
    text_height: float = Field(gt=0)
    locked_layer: bool = False

    @model_validator(mode="after")
    def validate_table(self) -> CadTableSnapshot:
        columns = len(self.column_widths)
        if any(len(row) != columns for row in self.cells):
            raise ValueError("table rows must match column_widths")
        return self


class TableWidthRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    table_handles: tuple[str, ...] = Field(min_length=1)
    character_width_factor: float = Field(gt=0)
    horizontal_padding: float = Field(ge=0)
    minimum_width: float = Field(gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> TableWidthRequest:
        _approval(self.dry_run, self.approval, "TAJ")
        return self


class TableWidthPlan(Batch18Plan):
    command_alias: str = "TAJ"
    legacy_symbol: str = "xiTableWidAj"
    semantic_evidence: str = "frozen xiShortkey: 캐드 테이블 문자에 맞추어 폭 자동 변경; width metric explicit"
    widths_by_handle: dict[str, tuple[float, ...]]


def plan_table_width(request: TableWidthRequest, snapshots: Sequence[CadTableSnapshot]) -> TableWidthPlan:
    by = {item.handle.casefold(): item for item in snapshots}
    result = {}
    for handle in request.table_handles:
        item = by.get(handle.casefold())
        if item is None or item.locked_layer:
            raise ValueError(f"TAJ table unavailable: {handle}")
        result[item.handle] = tuple(
            max(
                request.minimum_width,
                max(len(row[col]) for row in item.cells) * item.text_height * request.character_width_factor
                + 2 * request.horizontal_padding,
            )
            for col in range(len(item.column_widths))
        )
    return TableWidthPlan(document_id=request.document_id, widths_by_handle=result, dry_run=request.dry_run)


class TrussRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    start: Point3D
    end: Point3D
    depth: float = Field(gt=0)
    panel_count: int = Field(gt=1)
    diagonal_starts_up: bool
    chord_layer: str = Field(min_length=1)
    web_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TrussRequest:
        if self.start == self.end:
            raise ValueError("TRUSS endpoints must be distinct")
        _approval(self.dry_run, self.approval, "TRUSS")
        return self


class TrussPlan(Batch18Plan):
    command_alias: str = "TRUSS"
    legacy_symbol: str = "xitruss"
    semantic_evidence: str = "xiShortkey: 트러스 그리기; depth/panels/diagonal policy explicit"
    lower_chord: tuple[Point3D, Point3D]
    upper_chord: tuple[Point3D, Point3D]
    webs: tuple[tuple[Point3D, Point3D], ...]
    chord_layer: str
    web_layer: str


def plan_truss(request: TrussRequest) -> TrussPlan:
    dx, dy = request.end.x - request.start.x, request.end.y - request.start.y
    length = hypot(dx, dy)
    nx, ny = -dy / length * request.depth, dx / length * request.depth
    upper_start = Point3D(x=request.start.x + nx, y=request.start.y + ny, z=request.start.z)
    upper_end = Point3D(x=request.end.x + nx, y=request.end.y + ny, z=request.end.z)
    lower = tuple(
        Point3D(
            x=request.start.x + dx * i / request.panel_count,
            y=request.start.y + dy * i / request.panel_count,
            z=request.start.z,
        )
        for i in range(request.panel_count + 1)
    )
    upper = tuple(Point3D(x=p.x + nx, y=p.y + ny, z=p.z) for p in lower)
    webs = tuple(
        (lower[i], upper[i + 1]) if (i % 2 == 0) == request.diagonal_starts_up else (upper[i], lower[i + 1])
        for i in range(request.panel_count)
    )
    return TrussPlan(
        document_id=request.document_id,
        lower_chord=(request.start, request.end),
        upper_chord=(upper_start, upper_end),
        webs=webs,
        chord_layer=request.chord_layer,
        web_layer=request.web_layer,
        dry_run=request.dry_run,
    )


class WindowVariant(StrEnum):
    W1 = "w1"
    W2 = "w2"
    W3 = "w3"


class WindowGlazing(StrEnum):
    SINGLE = "single"
    DOUBLE = "double"


class WindowDetail(StrEnum):
    SIMPLE = "simple"
    DETAIL = "detail"


class WindowRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    variant: WindowVariant
    start: Point3D
    end: Point3D
    wall_depth: float = Field(gt=0)
    divisions: int = Field(ge=1, le=4)
    glazing: WindowGlazing
    detail: WindowDetail
    reverse_frame: bool
    frame_depth: float = Field(gt=0)
    frame_width: float = Field(gt=0)
    glass_thickness: float = Field(gt=0)
    wall_gap: float = Field(ge=0)
    frame_layer: str = Field(min_length=1)
    elevation_layer: str = Field(min_length=1)
    glass_layer: str = Field(min_length=1)
    center_layer: str = Field(min_length=1)
    group_output: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> WindowRequest:
        if self.start == self.end:
            raise ValueError("window endpoints must be distinct")
        if self.variant is WindowVariant.W1 and self.divisions < 1:
            raise ValueError("W1 requires at least one division")
        if self.variant in {WindowVariant.W2, WindowVariant.W3} and self.divisions not in {2, 3, 4}:
            raise ValueError("W2/W3 DCL supports only 2, 3 or 4 divisions")
        _approval(self.dry_run, self.approval, self.variant.value.upper())
        return self


class WindowPlan(Batch18Plan):
    variant: WindowVariant
    opening_line: tuple[Point3D, Point3D]
    division_fractions: tuple[float, ...]
    request_spec: WindowRequest


def plan_window(request: WindowRequest) -> WindowPlan:
    symbol = "xiWin1" if request.variant is WindowVariant.W1 else "xiWin2"
    evidence = "xiWin1 DCL" if request.variant is WindowVariant.W1 else "xiWin2 DCL (W2/W3 variant files)"
    return WindowPlan(
        command_alias=request.variant.value.upper(),
        legacy_symbol=symbol,
        semantic_evidence=f"{evidence}: divisions/glazing/detail/reverse/frame/glass/gap/layers/group",
        document_id=request.document_id,
        variant=request.variant,
        opening_line=(request.start, request.end),
        division_fractions=tuple(i / request.divisions for i in range(1, request.divisions)),
        request_spec=request,
        dry_run=request.dry_run,
    )


class WallCleanup(StrEnum):
    FOLLOW_FIRST = "follow_first"
    EACH_WALL = "each_wall"


class WallOpeningRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    start: Point3D
    end: Point3D
    centered: bool
    offset: float = Field(ge=0)
    external_projection: float = Field(ge=0)
    internal_projection: float = Field(ge=0)
    omit_elevation_line: bool
    cleanup: WallCleanup
    elevation_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> WallOpeningRequest:
        if self.start == self.end:
            raise ValueError("WO endpoints must be distinct")
        _approval(self.dry_run, self.approval, "WO")
        return self


class WallOpeningPlan(Batch18Plan):
    command_alias: str = "WO"
    legacy_symbol: str = "xiWallOpening"
    semantic_evidence: str = (
        "xiWallOpening DCL: elevation omission/center/offset/internal/external projection/wall cleanup/layer"
    )
    opening_line: tuple[Point3D, Point3D]
    request_spec: WallOpeningRequest


def plan_wall_opening(request: WallOpeningRequest) -> WallOpeningPlan:
    return WallOpeningPlan(
        document_id=request.document_id,
        opening_line=(request.start, request.end),
        request_spec=request,
        dry_run=request.dry_run,
    )


class ZigZagRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    start: Point3D
    end: Point3D
    amplitude: float = Field(gt=0)
    pitch: float = Field(gt=0)
    start_positive: bool
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ZigZagRequest:
        if self.start == self.end:
            raise ValueError("ZIGZAG endpoints must be distinct")
        _approval(self.dry_run, self.approval, "ZIGZAG")
        return self


class ZigZagPlan(Batch18Plan):
    command_alias: str = "ZIGZAG"
    legacy_symbol: str = "xiZIGZAG"
    semantic_evidence: str = "xiShortkey: 지그재그 폴리선 그리기; amplitude/pitch/phase explicit"
    vertices: tuple[Point3D, ...]
    layer: str


def plan_zigzag(request: ZigZagRequest) -> ZigZagPlan:
    dx, dy = request.end.x - request.start.x, request.end.y - request.start.y
    length = hypot(dx, dy)
    segments = max(1, round(length / request.pitch))
    nx, ny = -dy / length, dx / length
    points = [request.start]
    for i in range(1, segments):
        fraction = i / segments
        sign = 1 if (i % 2 == 1) == request.start_positive else -1
        points.append(
            Point3D(
                x=request.start.x + dx * fraction + nx * request.amplitude * sign,
                y=request.start.y + dy * fraction + ny * request.amplitude * sign,
                z=request.start.z + (request.end.z - request.start.z) * fraction,
            )
        )
    points.append(request.end)
    return ZigZagPlan(
        document_id=request.document_id, vertices=tuple(points), layer=request.layer, dry_run=request.dry_run
    )


class TableTransferFormat(StrEnum):
    MATRIX = "matrix"
    TSV = "tsv"


class CadToExcelRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    table_handle: str = Field(min_length=1)
    transfer_format: TableTransferFormat
    include_geometry: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> CadToExcelRequest:
        _approval(self.dry_run, self.approval, "C2E")
        return self


class CadToExcelPlan(Batch18Plan):
    command_alias: str = "C2E"
    legacy_symbol: str = "xiCad2Excel"
    semantic_evidence: str = "frozen xiShortkey: CAD table to Excel; external Excel automation blocked, data returned"
    cells: tuple[tuple[str, ...], ...]
    column_widths: tuple[float, ...] | None
    external_excel_blocked: bool = True


def plan_cad_to_excel(request: CadToExcelRequest, snapshots: Sequence[CadTableSnapshot]) -> CadToExcelPlan:
    item = next((table for table in snapshots if table.handle.casefold() == request.table_handle.casefold()), None)
    if item is None:
        raise ValueError("C2E table not found")
    return CadToExcelPlan(
        document_id=request.document_id,
        cells=item.cells,
        column_widths=item.column_widths if request.include_geometry else None,
        dry_run=request.dry_run,
    )


class ExcelToCadRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    cells: tuple[tuple[str, ...], ...] = Field(min_length=1)
    column_widths: tuple[float, ...] = Field(min_length=1)
    row_heights: tuple[float, ...] = Field(min_length=1)
    insertion_point: Point3D
    grid_layer: str = Field(min_length=1)
    text_layer: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ExcelToCadRequest:
        if len(self.cells) != len(self.row_heights) or any(len(row) != len(self.column_widths) for row in self.cells):
            raise ValueError("E2C matrix dimensions must match row_heights and column_widths")
        _approval(self.dry_run, self.approval, "E2C")
        return self


class ExcelToCadPlan(Batch18Plan):
    command_alias: str = "E2C"
    legacy_symbol: str = "xiExcel2Cad"
    semantic_evidence: str = (
        "frozen xiShortkey: Excel table to CAD; digest-bound matrix input, external Excel automation blocked"
    )
    request_spec: ExcelToCadRequest
    external_excel_blocked: bool = True


def plan_excel_to_cad(request: ExcelToCadRequest) -> ExcelToCadPlan:
    return ExcelToCadPlan(document_id=request.document_id, request_spec=request, dry_run=request.dry_run)


class HatchCloneTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    insertion_point: Point3D
    rotation_degrees: float = 0
    scale: float = Field(gt=0)


class HatchCloneRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handle: str = Field(min_length=1)
    targets: tuple[HatchCloneTarget, ...] = Field(min_length=1)
    preserve_associativity: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> HatchCloneRequest:
        if self.preserve_associativity:
            raise ValueError("HC associativity is blocked without target boundary handles")
        _approval(self.dry_run, self.approval, "HC")
        return self


class HatchClonePlan(Batch18Plan):
    command_alias: str = "HC"
    legacy_symbol: str = "xiHatchClone"
    semantic_evidence: str = "frozen xiShortkey: 해치 복제; explicit target transforms, associativity blocked"
    source: HatchSnapshot
    targets: tuple[HatchCloneTarget, ...]


def plan_hatch_clone(request: HatchCloneRequest, snapshots: Sequence[HatchSnapshot]) -> HatchClonePlan:
    source = next((item for item in snapshots if item.handle.casefold() == request.source_handle.casefold()), None)
    if source is None:
        raise ValueError("HC source hatch not found")
    return HatchClonePlan(
        document_id=request.document_id, source=source, targets=request.targets, dry_run=request.dry_run
    )


class HatchExportRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    hatch_handles: tuple[str, ...] = Field(min_length=1)
    include_boundaries: bool
    output_definition_only: bool = True
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> HatchExportRequest:
        if not self.output_definition_only:
            raise ValueError("HEX file write is blocked; definition output only")
        _approval(self.dry_run, self.approval, "HEX")
        return self


class HatchExportPlan(Batch18Plan):
    command_alias: str = "HEX"
    legacy_symbol: str = "xiHatchExport"
    semantic_evidence: str = "frozen xiShortkey: 해치 내보내기; data export only, file write blocked"
    definitions: tuple[HatchSnapshot, ...]
    include_boundaries: bool
    external_write_blocked: bool = True


def plan_hatch_export(request: HatchExportRequest, snapshots: Sequence[HatchSnapshot]) -> HatchExportPlan:
    by = {item.handle.casefold(): item for item in snapshots}
    definitions = []
    for handle in request.hatch_handles:
        item = by.get(handle.casefold())
        if item is None:
            raise ValueError(f"HEX hatch not found: {handle}")
        definitions.append(item)
    return HatchExportPlan(
        document_id=request.document_id,
        definitions=tuple(definitions),
        include_boundaries=request.include_boundaries,
        dry_run=request.dry_run,
    )


def register_headless_core_batch18_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 18 Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    def register(name: str):
        return lambda function: mcp.tool(name=name, annotations=annotations)(function)

    @register("xicad_plan_stp")
    def stp_tool(request: StairPlanRequest) -> StairPlanPlan:
        return plan_stair_plan(request)

    @register("xicad_plan_taj")
    def taj_tool(request: TableWidthRequest, snapshots: tuple[CadTableSnapshot, ...]) -> TableWidthPlan:
        return plan_table_width(request, snapshots)

    @register("xicad_plan_truss")
    def truss_tool(request: TrussRequest) -> TrussPlan:
        return plan_truss(request)

    @register("xicad_plan_w1")
    def w1_tool(request: WindowRequest) -> WindowPlan:
        if request.variant is not WindowVariant.W1:
            raise ValueError("W1 requires variant=w1")
        return plan_window(request)

    @register("xicad_plan_w2")
    def w2_tool(request: WindowRequest) -> WindowPlan:
        if request.variant is not WindowVariant.W2:
            raise ValueError("W2 requires variant=w2")
        return plan_window(request)

    @register("xicad_plan_w3")
    def w3_tool(request: WindowRequest) -> WindowPlan:
        if request.variant is not WindowVariant.W3:
            raise ValueError("W3 requires variant=w3")
        return plan_window(request)

    @register("xicad_plan_wo")
    def wo_tool(request: WallOpeningRequest) -> WallOpeningPlan:
        return plan_wall_opening(request)

    @register("xicad_plan_zigzag")
    def zigzag_tool(request: ZigZagRequest) -> ZigZagPlan:
        return plan_zigzag(request)

    @register("xicad_plan_c2e")
    def c2e_tool(request: CadToExcelRequest, snapshots: tuple[CadTableSnapshot, ...]) -> CadToExcelPlan:
        return plan_cad_to_excel(request, snapshots)

    @register("xicad_plan_e2c")
    def e2c_tool(request: ExcelToCadRequest) -> ExcelToCadPlan:
        return plan_excel_to_cad(request)

    @register("xicad_plan_hc")
    def hc_tool(request: HatchCloneRequest, snapshots: tuple[HatchSnapshot, ...]) -> HatchClonePlan:
        return plan_hatch_clone(request, snapshots)

    @register("xicad_plan_hex")
    def hex_tool(request: HatchExportRequest, snapshots: tuple[HatchSnapshot, ...]) -> HatchExportPlan:
        return plan_hatch_export(request, snapshots)
