"""Dialog-free planning contracts for xiCAD drawing batch 17."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch14 import GeometrySnapshot


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval fingerprint")


class Batch17Plan(BaseModel):
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


class RectSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    center: Point3D
    width: float = Field(gt=0)
    depth: float = Field(gt=0)
    layer: str = Field(min_length=1)


class ElevatorRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    center: Point3D
    shaft_width: float = Field(gt=0)
    shaft_depth: float = Field(gt=0)
    car_width: float = Field(gt=0)
    car_depth: float = Field(gt=0)
    door_width: float = Field(gt=0)
    car_count: int = Field(gt=0)
    shaft_layer: str = Field(min_length=1)
    car_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ElevatorRequest:
        if self.car_width * self.car_count > self.shaft_width or self.car_depth > self.shaft_depth:
            raise ValueError("ELV cars must fit inside the shaft")
        if self.door_width > self.car_width:
            raise ValueError("ELV door must fit inside a car")
        _approval(self.dry_run, self.approval, "ELV")
        return self


class ElevatorPlan(Batch17Plan):
    command_alias: str = "ELV"
    legacy_symbol: str = "xiElevator"
    semantic_evidence: str = "xiShortkey: 엘리베이터 그리기; all shaft/car/door geometry explicit"
    shaft: RectSpec
    cars: tuple[RectSpec, ...]
    door_width: float


def plan_elevator(request: ElevatorRequest) -> ElevatorPlan:
    start = request.center.x - (request.car_count - 1) * request.car_width / 2
    cars = tuple(
        RectSpec(
            center=Point3D(x=start + i * request.car_width, y=request.center.y, z=request.center.z),
            width=request.car_width,
            depth=request.car_depth,
            layer=request.car_layer,
        )
        for i in range(request.car_count)
    )
    return ElevatorPlan(
        document_id=request.document_id,
        shaft=RectSpec(
            center=request.center, width=request.shaft_width, depth=request.shaft_depth, layer=request.shaft_layer
        ),
        cars=cars,
        door_width=request.door_width,
        dry_run=request.dry_run,
    )


class EscalatorPlanRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    start: Point3D
    end: Point3D
    overall_width: float = Field(gt=0)
    tread_width: float = Field(gt=0)
    step_pitch: float = Field(gt=0)
    balustrade_width: float = Field(ge=0)
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> EscalatorPlanRequest:
        if self.start == self.end or self.tread_width + 2 * self.balustrade_width > self.overall_width:
            raise ValueError("EPD requires a valid run and components fitting overall width")
        _approval(self.dry_run, self.approval, "EPD")
        return self


class EscalatorPlanPlan(Batch17Plan):
    command_alias: str = "EPD"
    legacy_symbol: str = "xiEPD"
    semantic_evidence: str = "xiShortkey: 에스컬레이터 평면 그리기; run and widths explicit"
    centerline: tuple[Point3D, Point3D]
    overall_width: float
    tread_width: float
    step_pitch: float
    layer: str


def plan_escalator_plan(request: EscalatorPlanRequest) -> EscalatorPlanPlan:
    return EscalatorPlanPlan(
        document_id=request.document_id,
        centerline=(request.start, request.end),
        overall_width=request.overall_width,
        tread_width=request.tread_width,
        step_pitch=request.step_pitch,
        layer=request.layer,
        dry_run=request.dry_run,
    )


class HatchSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    loops: tuple[tuple[Point3D, ...], ...] = Field(min_length=1)
    origin: Point3D
    layer: str = Field(min_length=1)
    is_xref: bool = False
    locked_layer: bool = False


class HatchBoundaryRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    hatch_handles: tuple[str, ...] = Field(min_length=1)
    target_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> HatchBoundaryRequest:
        _approval(self.dry_run, self.approval, "HB")
        return self


class HatchBoundaryPlan(Batch17Plan):
    command_alias: str = "HB"
    legacy_symbol: str = "xiHatBDraw"
    semantic_evidence: str = "xiShortkey: 해치경계 다시 그리기; hatch loops supplied as snapshots"
    boundaries: dict[str, tuple[tuple[Point3D, ...], ...]]
    target_layer: str


def plan_hatch_boundary(request: HatchBoundaryRequest, snapshots: Sequence[HatchSnapshot]) -> HatchBoundaryPlan:
    by = {item.handle.casefold(): item for item in snapshots}
    result = {}
    for handle in request.hatch_handles:
        item = by.get(handle.casefold())
        if item is None:
            raise ValueError(f"HB hatch not found: {handle}")
        result[item.handle] = item.loops
    return HatchBoundaryPlan(
        document_id=request.document_id, boundaries=result, target_layer=request.target_layer, dry_run=request.dry_run
    )


class HeatGridRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    lower_left: Point3D
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    spacing: float = Field(gt=0)
    edge_offset: float = Field(ge=0)
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> HeatGridRequest:
        if 2 * self.edge_offset >= min(self.width, self.height):
            raise ValueError("HGRID edge_offset leaves no drawable area")
        _approval(self.dry_run, self.approval, "HGRID")
        return self


class HeatGridPlan(Batch17Plan):
    command_alias: str = "HGRID"
    legacy_symbol: str = "xiHeatGrid"
    semantic_evidence: str = "xiShortkey: 바닥난방 XL파이프 그리기; rectangular serpentine policy explicit"
    path: tuple[Point3D, ...]
    layer: str


def plan_heat_grid(request: HeatGridRequest) -> HeatGridPlan:
    x0, y0, z = (
        request.lower_left.x + request.edge_offset,
        request.lower_left.y + request.edge_offset,
        request.lower_left.z,
    )
    x1 = request.lower_left.x + request.width - request.edge_offset
    usable_height = request.height - 2 * request.edge_offset
    rows = max(1, int(usable_height // request.spacing))
    points = []
    for row in range(rows + 1):
        y = y0 + min(row * request.spacing, usable_height)
        points.extend(
            (Point3D(x=x0, y=y, z=z), Point3D(x=x1, y=y, z=z))
            if row % 2 == 0
            else (Point3D(x=x1, y=y, z=z), Point3D(x=x0, y=y, z=z))
        )
    return HeatGridPlan(
        document_id=request.document_id, path=tuple(points), layer=request.layer, dry_run=request.dry_run
    )


class HatchPointRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    hatch_handles: tuple[str, ...] = Field(min_length=1)
    new_origin: Point3D
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> HatchPointRequest:
        _approval(self.dry_run, self.approval, "HP")
        return self


class HatchPointPlan(Batch17Plan):
    command_alias: str = "HP"
    legacy_symbol: str = "xiHatchPoint"
    semantic_evidence: str = "xiShortkey: 해치기준점 변경"
    origin_changes: dict[str, Point3D]


def plan_hatch_point(request: HatchPointRequest, snapshots: Sequence[HatchSnapshot]) -> HatchPointPlan:
    by = {item.handle.casefold(): item for item in snapshots}
    changes = {}
    for handle in request.hatch_handles:
        item = by.get(handle.casefold())
        if item is None or item.is_xref or item.locked_layer:
            raise ValueError(f"HP hatch unavailable: {handle}")
        changes[item.handle] = request.new_origin
    return HatchPointPlan(document_id=request.document_id, origin_changes=changes, dry_run=request.dry_run)


class InsulationMode(StrEnum):
    SEPARATE_THICKNESS_DIRECTION = "separate_thickness_direction"
    COMBINED = "combined"


class InsulationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    baseline: tuple[Point3D, Point3D]
    thickness: float = Field(gt=0)
    mode: InsulationMode
    small_threshold: float = Field(gt=0)
    medium_threshold: float = Field(gt=0)
    cut_to_length: bool
    remove_end_piece: bool
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> InsulationRequest:
        if self.baseline[0] == self.baseline[1] or self.small_threshold >= self.medium_threshold:
            raise ValueError("INS requires a valid baseline and ordered thresholds")
        _approval(self.dry_run, self.approval, "INS")
        return self


class InsulationPlan(Batch17Plan):
    command_alias: str = "INS"
    legacy_symbol: str = "xiINSUL"
    semantic_evidence: str = "xiInsul DCL: thickness thresholds/mode/cut/end-piece/layer"
    baseline: tuple[Point3D, Point3D]
    thickness: float
    density_class: str
    cut_to_length: bool
    remove_end_piece: bool
    layer: str


def plan_insulation(request: InsulationRequest) -> InsulationPlan:
    density = (
        "small"
        if request.thickness < request.small_threshold
        else "medium"
        if request.thickness < request.medium_threshold
        else "large"
    )
    return InsulationPlan(
        document_id=request.document_id,
        baseline=request.baseline,
        thickness=request.thickness,
        density_class=density,
        cut_to_length=request.cut_to_length,
        remove_end_piece=request.remove_end_piece,
        layer=request.layer,
        dry_run=request.dry_run,
    )


class ParkingRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    origin: Point3D
    stall_count: int = Field(gt=0)
    stall_width: float = Field(gt=0)
    stall_depth: float = Field(gt=0)
    aisle_width: float = Field(ge=0)
    angle_degrees: int
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ParkingRequest:
        if self.angle_degrees not in {0, 30, 45, 60, 90}:
            raise ValueError("PK angle must be one of 0,30,45,60,90")
        _approval(self.dry_run, self.approval, "PK")
        return self


class ParkingPlan(Batch17Plan):
    command_alias: str = "PK"
    legacy_symbol: str = "xipk"
    semantic_evidence: str = "xiShortkey: 주차장 그리기; count/dimensions/angle explicit"
    stalls: tuple[RectSpec, ...]
    aisle_width: float
    angle_degrees: int


def plan_parking(request: ParkingRequest) -> ParkingPlan:
    stalls = tuple(
        RectSpec(
            center=Point3D(
                x=request.origin.x + (i + 0.5) * request.stall_width,
                y=request.origin.y + request.stall_depth / 2,
                z=request.origin.z,
            ),
            width=request.stall_width,
            depth=request.stall_depth,
            layer=request.layer,
        )
        for i in range(request.stall_count)
    )
    return ParkingPlan(
        document_id=request.document_id,
        stalls=stalls,
        aisle_width=request.aisle_width,
        angle_degrees=request.angle_degrees,
        dry_run=request.dry_run,
    )


class PartialZoomMode(StrEnum):
    OBJECTS = "objects"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    POLYGON = "polygon"


class PartialZoomRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=1)
    mode: PartialZoomMode
    source_center: Point3D
    target_center: Point3D
    zoom_factor: float = Field(gt=0)
    boundary_points: tuple[Point3D, ...] = Field(min_length=2)
    layer: str = Field(min_length=1)
    color: int = Field(ge=1, le=255)
    linetype: str = Field(min_length=1)
    create_block: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> PartialZoomRequest:
        if self.mode is PartialZoomMode.POLYGON and len(self.boundary_points) < 3:
            raise ValueError("PZ polygon requires at least three boundary points")
        _approval(self.dry_run, self.approval, "PZ")
        return self


class PartialZoomPlan(Batch17Plan):
    command_alias: str = "PZ"
    legacy_symbol: str = "xiPartialZoom"
    semantic_evidence: str = "xiPartialZoom DCL: objects/rectangle/circle/polygon, layer/color/linetype/factor/block"
    transformed_vertices: dict[str, tuple[Point3D, ...]]
    boundary_points: tuple[Point3D, ...]
    create_block: bool


def plan_partial_zoom(request: PartialZoomRequest, snapshots: Sequence[GeometrySnapshot]) -> PartialZoomPlan:
    by = {item.handle.casefold(): item for item in snapshots}
    transformed = {}
    for handle in request.source_handles:
        item = by.get(handle.casefold())
        if item is None:
            raise ValueError(f"PZ source missing: {handle}")
        transformed[item.handle] = tuple(
            Point3D(
                x=request.target_center.x + (p.x - request.source_center.x) * request.zoom_factor,
                y=request.target_center.y + (p.y - request.source_center.y) * request.zoom_factor,
                z=request.target_center.z + (p.z - request.source_center.z) * request.zoom_factor,
            )
            for p in item.vertices
        )
    return PartialZoomPlan(
        document_id=request.document_id,
        transformed_vertices=transformed,
        boundary_points=request.boundary_points,
        create_block=request.create_block,
        dry_run=request.dry_run,
    )


class QRCodeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    payload: str = Field(min_length=1)
    payload_digest: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    modules: tuple[tuple[bool, ...], ...] = Field(min_length=1)
    insertion_point: Point3D
    module_size: float = Field(gt=0)
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> QRCodeRequest:
        size = len(self.modules)
        if size < 21 or any(len(row) != size for row in self.modules):
            raise ValueError("QRC requires an explicit square QR module matrix of size >=21")
        _approval(self.dry_run, self.approval, "QRC")
        return self


class QRCodePlan(Batch17Plan):
    command_alias: str = "QRC"
    legacy_symbol: str = "xiQRcode"
    semantic_evidence: str = "xiShortkey: QR 코드 그리기; encoding delegated to digest-bound explicit module matrix"
    dark_cells: tuple[tuple[int, int], ...]
    insertion_point: Point3D
    module_size: float
    layer: str
    payload_digest: str


def plan_qr_code(request: QRCodeRequest) -> QRCodePlan:
    cells = tuple(
        (row, column) for row, values in enumerate(request.modules) for column, dark in enumerate(values) if dark
    )
    return QRCodePlan(
        document_id=request.document_id,
        dark_cells=cells,
        insertion_point=request.insertion_point,
        module_size=request.module_size,
        layer=request.layer,
        payload_digest=request.payload_digest,
        dry_run=request.dry_run,
    )


class ScaleBarRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    origin: Point3D
    drawing_scale: float = Field(gt=0)
    segment_length: float = Field(gt=0)
    segment_count: int = Field(gt=0)
    units_label: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> ScaleBarRequest:
        _approval(self.dry_run, self.approval, "SCB")
        return self


class ScaleBarPlan(Batch17Plan):
    command_alias: str = "SCB"
    legacy_symbol: str = "xiScaleBar"
    semantic_evidence: str = "frozen xiShortkey: 축척 막대 그리기; scale/segments/units explicit"
    tick_points: tuple[Point3D, ...]
    labels: tuple[str, ...]
    layer: str
    text_height: float


def plan_scale_bar(request: ScaleBarRequest) -> ScaleBarPlan:
    ticks = tuple(
        Point3D(x=request.origin.x + i * request.segment_length, y=request.origin.y, z=request.origin.z)
        for i in range(request.segment_count + 1)
    )
    labels = tuple(
        f"{i * request.segment_length / request.drawing_scale:g} {request.units_label}"
        for i in range(request.segment_count + 1)
    )
    return ScaleBarPlan(
        document_id=request.document_id,
        tick_points=ticks,
        labels=labels,
        layer=request.layer,
        text_height=request.text_height,
        dry_run=request.dry_run,
    )


class SteelBeamMode(StrEnum):
    ARCHITECTURAL = "architectural"
    STRUCTURAL_SYMBOL = "structural_symbol"


class ConnectionKind(StrEnum):
    RIGID = "rigid"
    PIN = "pin"


class SteelBeamRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    start: Point3D
    end: Point3D
    mode: SteelBeamMode
    offset: float = Field(ge=0)
    beam_width: float = Field(gt=0)
    web_thickness: float = Field(gt=0)
    web_linetype: str = Field(min_length=1)
    prefix: str
    beam_number: int = Field(ge=0)
    uppercase: bool
    head_connection: ConnectionKind
    tail_connection: ConnectionKind
    head_size: float = Field(gt=0)
    line_thickness: float = Field(gt=0)
    text_size: float = Field(gt=0)
    symbol_layer: str = Field(min_length=1)
    text_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SteelBeamRequest:
        if self.start == self.end or self.web_thickness >= self.beam_width:
            raise ValueError("STB requires a valid beam and web thinner than beam width")
        _approval(self.dry_run, self.approval, "STB")
        return self


class SteelBeamPlan(Batch17Plan):
    command_alias: str = "STB"
    legacy_symbol: str = "xiSTB"
    semantic_evidence: str = "xiSTB DCL: architectural/structural, offset,width,web,mark,connections,sizes,layers"
    centerline: tuple[Point3D, Point3D]
    beam_mark: str
    request_spec: SteelBeamRequest


def plan_steel_beam(request: SteelBeamRequest) -> SteelBeamPlan:
    mark = f"{request.prefix}{request.beam_number}"
    return SteelBeamPlan(
        document_id=request.document_id,
        centerline=(request.start, request.end),
        beam_mark=mark.upper() if request.uppercase else mark,
        request_spec=request,
        dry_run=request.dry_run,
    )


class StairView(StrEnum):
    SECTION = "section"
    ELEVATION = "elevation"


class StairRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    origin: Point3D
    view: StairView
    total_rise: float = Field(gt=0)
    total_run: float = Field(gt=0)
    step_count: int = Field(gt=0)
    round_tread_to_ten: bool
    slab_type: int = Field(ge=1, le=2)
    riser_depth: float = Field(gt=0)
    slab_thickness: float = Field(gt=0)
    top_finish_thickness: float = Field(ge=0)
    bottom_finish_thickness: float = Field(ge=0)
    handrail_height: float | None = Field(default=None, gt=0)
    elevation_layer: str = Field(min_length=1)
    section_layer: str = Field(min_length=1)
    handrail_layer: str = Field(min_length=1)
    finish_layer: str = Field(min_length=1)
    number_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> StairRequest:
        if self.round_tread_to_ten and round(self.total_run / self.step_count / 10) * 10 <= 0:
            raise ValueError("STC rounded tread width must remain positive")
        _approval(self.dry_run, self.approval, "STC")
        return self


class StairPlan(Batch17Plan):
    command_alias: str = "STC"
    legacy_symbol: str = "xiSTC"
    semantic_evidence: str = "xiSTC DCL: section/elevation, story/tread rounding/numbering, slab/finish/handrail/layers"
    tread: float
    riser: float
    step_vertices: tuple[Point3D, ...]
    request_spec: StairRequest


def plan_stair(request: StairRequest) -> StairPlan:
    tread = request.total_run / request.step_count
    if request.round_tread_to_ten:
        tread = round(tread / 10) * 10
    riser = request.total_rise / request.step_count
    vertices = tuple(
        Point3D(x=request.origin.x + i * tread, y=request.origin.y + i * riser, z=request.origin.z)
        for i in range(request.step_count + 1)
    )
    return StairPlan(
        document_id=request.document_id,
        tread=tread,
        riser=riser,
        step_vertices=vertices,
        request_spec=request,
        dry_run=request.dry_run,
    )


def register_headless_core_batch17_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 17 Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    def register(name: str):
        return lambda function: mcp.tool(name=name, annotations=annotations)(function)

    @register("xicad_plan_elv")
    def elv_tool(request: ElevatorRequest) -> ElevatorPlan:
        return plan_elevator(request)

    @register("xicad_plan_epd")
    def epd_tool(request: EscalatorPlanRequest) -> EscalatorPlanPlan:
        return plan_escalator_plan(request)

    @register("xicad_plan_hb")
    def hb_tool(request: HatchBoundaryRequest, snapshots: tuple[HatchSnapshot, ...]) -> HatchBoundaryPlan:
        return plan_hatch_boundary(request, snapshots)

    @register("xicad_plan_hgrid")
    def hgrid_tool(request: HeatGridRequest) -> HeatGridPlan:
        return plan_heat_grid(request)

    @register("xicad_plan_hp")
    def hp_tool(request: HatchPointRequest, snapshots: tuple[HatchSnapshot, ...]) -> HatchPointPlan:
        return plan_hatch_point(request, snapshots)

    @register("xicad_plan_ins")
    def ins_tool(request: InsulationRequest) -> InsulationPlan:
        return plan_insulation(request)

    @register("xicad_plan_pk")
    def pk_tool(request: ParkingRequest) -> ParkingPlan:
        return plan_parking(request)

    @register("xicad_plan_pz")
    def pz_tool(request: PartialZoomRequest, snapshots: tuple[GeometrySnapshot, ...]) -> PartialZoomPlan:
        return plan_partial_zoom(request, snapshots)

    @register("xicad_plan_qrc")
    def qrc_tool(request: QRCodeRequest) -> QRCodePlan:
        return plan_qr_code(request)

    @register("xicad_plan_scb")
    def scb_tool(request: ScaleBarRequest) -> ScaleBarPlan:
        return plan_scale_bar(request)

    @register("xicad_plan_stb")
    def stb_tool(request: SteelBeamRequest) -> SteelBeamPlan:
        return plan_steel_beam(request)

    @register("xicad_plan_stc")
    def stc_tool(request: StairRequest) -> StairPlan:
        return plan_stair(request)
