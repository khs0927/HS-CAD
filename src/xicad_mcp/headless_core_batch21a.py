"""Evidence-led deterministic planners for xiCAD Multi batch 21A."""

from __future__ import annotations

from enum import StrEnum
from math import hypot
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval fingerprint")


class Batch21APlan(BaseModel):
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


class TransformSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    translation: Point3D
    rotation_degrees: float
    rotation_center: Point3D


class DivideArcCopyRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=1)
    center: Point3D
    start_angle_degrees: float
    end_angle_degrees: float
    division_count: int = Field(gt=0)
    include_start: bool
    include_end: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DivideArcCopyRequest:
        if self.start_angle_degrees == self.end_angle_degrees:
            raise ValueError("DAC angle range must be non-zero")
        if len({handle.casefold() for handle in self.source_handles}) != len(self.source_handles):
            raise ValueError("DAC source handles must be unique")
        _approval(self.dry_run, self.approval, "DAC")
        return self


class DivideArcCopyPlan(Batch21APlan):
    command_alias: str = "DAC"
    legacy_symbol: str = "xiDivideArcCopy"
    semantic_evidence: str = "current+frozen shortcut: 각도 등분 기록; no DCL/config/source found"
    semantic_gaps: tuple[str, ...] = ("meaning of 기록", "source orientation policy", "endpoint inclusion defaults")
    transforms: tuple[TransformSpec, ...]


def plan_divide_arc_copy(request: DivideArcCopyRequest) -> DivideArcCopyPlan:
    step = (request.end_angle_degrees - request.start_angle_degrees) / request.division_count
    indexes = range(request.division_count + 1)
    angles = tuple(
        request.start_angle_degrees + index * step
        for index in indexes
        if (request.include_start or index != 0) and (request.include_end or index != request.division_count)
    )
    transforms = tuple(
        TransformSpec(
            source_handle=handle,
            translation=Point3D(x=0, y=0, z=0),
            rotation_degrees=angle - request.start_angle_degrees,
            rotation_center=request.center,
        )
        for angle in angles
        for handle in request.source_handles
    )
    return DivideArcCopyPlan(document_id=request.document_id, transforms=transforms, dry_run=request.dry_run)


class DistanceDivisionMode(StrEnum):
    COUNT = "count"
    SPACING = "spacing"


class DivideCopyRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=1)
    path_start: Point3D
    path_end: Point3D
    mode: DistanceDivisionMode
    division_count: int | None = Field(default=None, gt=0)
    spacing: float | None = Field(default=None, gt=0)
    include_start: bool
    include_end: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DivideCopyRequest:
        if self.path_start == self.path_end:
            raise ValueError("DVC path must be non-zero")
        if self.mode is DistanceDivisionMode.COUNT and self.division_count is None:
            raise ValueError("DVC count mode requires division_count")
        if self.mode is DistanceDivisionMode.SPACING and self.spacing is None:
            raise ValueError("DVC spacing mode requires spacing")
        _approval(self.dry_run, self.approval, "DVC")
        return self


class DivideCopyPlan(Batch21APlan):
    command_alias: str = "DVC"
    legacy_symbol: str = "xiDivideCopy"
    semantic_evidence: str = "current+frozen shortcut: 거리 등분 복사; no DCL/config/source found"
    semantic_gaps: tuple[str, ...] = (
        "count versus spacing prompt",
        "endpoint inclusion defaults",
        "path entity support",
    )
    transforms: tuple[TransformSpec, ...]


def plan_divide_copy(request: DivideCopyRequest) -> DivideCopyPlan:
    dx, dy, dz = (
        request.path_end.x - request.path_start.x,
        request.path_end.y - request.path_start.y,
        request.path_end.z - request.path_start.z,
    )
    length = (dx * dx + dy * dy + dz * dz) ** 0.5
    divisions = (
        request.division_count
        if request.mode is DistanceDivisionMode.COUNT
        else max(1, int(length // (request.spacing or length)))
    )
    indexes = range(divisions + 1)
    fractions = tuple(
        index / divisions
        for index in indexes
        if (request.include_start or index != 0) and (request.include_end or index != divisions)
    )
    transforms = tuple(
        TransformSpec(
            source_handle=handle,
            translation=Point3D(x=dx * fraction, y=dy * fraction, z=dz * fraction),
            rotation_degrees=0,
            rotation_center=request.path_start,
        )
        for fraction in fractions
        for handle in request.source_handles
    )
    return DivideCopyPlan(document_id=request.document_id, transforms=transforms, dry_run=request.dry_run)


class LineSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    start: Point3D
    end: Point3D
    layer: str = Field(min_length=1)
    is_xref: bool = False
    locked_layer: bool = False

    @model_validator(mode="after")
    def validate_line(self) -> LineSnapshot:
        if self.start == self.end:
            raise ValueError("line endpoints must be distinct")
        return self


class LineAnchor(StrEnum):
    START = "start"
    END = "end"
    CENTER = "center"


class ExtendLineRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    anchor: LineAnchor
    target_length: float = Field(gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> ExtendLineRequest:
        _approval(self.dry_run, self.approval, "EXL")
        return self


class ExtendLinePlan(Batch21APlan):
    command_alias: str = "EXL"
    legacy_symbol: str = "xiExtendLine"
    semantic_evidence: str = "current+frozen shortcut: 선 길이 조정; straight-line anchor/length policy explicit"
    semantic_gaps: tuple[str, ...] = ("legacy anchor prompt/default", "non-line entity support")
    endpoints: dict[str, tuple[Point3D, Point3D]]


def plan_extend_line(request: ExtendLineRequest, snapshots: tuple[LineSnapshot, ...]) -> ExtendLinePlan:
    by = {item.handle.casefold(): item for item in snapshots}
    result = {}
    for handle in request.target_handles:
        item = by.get(handle.casefold())
        if item is None or item.is_xref or item.locked_layer:
            raise ValueError(f"EXL line unavailable: {handle}")
        dx, dy, dz = item.end.x - item.start.x, item.end.y - item.start.y, item.end.z - item.start.z
        length = (dx * dx + dy * dy + dz * dz) ** 0.5
        ux, uy, uz = dx / length, dy / length, dz / length
        if request.anchor is LineAnchor.START:
            start, end = (
                item.start,
                Point3D(
                    x=item.start.x + ux * request.target_length,
                    y=item.start.y + uy * request.target_length,
                    z=item.start.z + uz * request.target_length,
                ),
            )
        elif request.anchor is LineAnchor.END:
            end, start = (
                item.end,
                Point3D(
                    x=item.end.x - ux * request.target_length,
                    y=item.end.y - uy * request.target_length,
                    z=item.end.z - uz * request.target_length,
                ),
            )
        else:
            center = Point3D(
                x=(item.start.x + item.end.x) / 2, y=(item.start.y + item.end.y) / 2, z=(item.start.z + item.end.z) / 2
            )
            half = request.target_length / 2
            start, end = (
                Point3D(x=center.x - ux * half, y=center.y - uy * half, z=center.z - uz * half),
                Point3D(x=center.x + ux * half, y=center.y + uy * half, z=center.z + uz * half),
            )
        result[item.handle] = (start, end)
    return ExtendLinePlan(document_id=request.document_id, endpoints=result, dry_run=request.dry_run)


class JoinLineRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    ordered_handles: tuple[str, ...] = Field(min_length=2)
    reverse_handles: tuple[str, ...] = ()
    tolerance: float = Field(gt=0)
    target_layer: str = Field(min_length=1)
    delete_sources: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> JoinLineRequest:
        handles = {handle.casefold() for handle in self.ordered_handles}
        if len(handles) != len(self.ordered_handles) or any(
            handle.casefold() not in handles for handle in self.reverse_handles
        ):
            raise ValueError("JL handles must be unique and reversals must be selected")
        _approval(self.dry_run, self.approval, "JL")
        return self


class JoinLinePlan(Batch21APlan):
    command_alias: str = "JL"
    legacy_symbol: str = "xiJoinLine"
    semantic_evidence: str = "current+frozen shortcut: 라인 이어주기; caller supplies order/reversal/tolerance"
    semantic_gaps: tuple[str, ...] = ("legacy automatic ordering", "gap bridging policy", "output entity type")
    vertices: tuple[Point3D, ...]
    target_layer: str
    delete_handles: tuple[str, ...]


def plan_join_line(request: JoinLineRequest, snapshots: tuple[LineSnapshot, ...]) -> JoinLinePlan:
    by = {item.handle.casefold(): item for item in snapshots}
    reverse = {handle.casefold() for handle in request.reverse_handles}
    lines = []
    for handle in request.ordered_handles:
        item = by.get(handle.casefold())
        if item is None:
            raise ValueError(f"JL line missing: {handle}")
        lines.append((item.end, item.start) if item.handle.casefold() in reverse else (item.start, item.end))
    if any(
        hypot(first[1].x - second[0].x, first[1].y - second[0].y) > request.tolerance
        for first, second in zip(lines, lines[1:], strict=False)
    ):
        raise ValueError("JL ordered endpoints exceed tolerance")
    vertices = (lines[0][0],) + tuple(line[1] for line in lines)
    return JoinLinePlan(
        document_id=request.document_id,
        vertices=vertices,
        target_layer=request.target_layer,
        delete_handles=request.ordered_handles if request.delete_sources else (),
        dry_run=request.dry_run,
    )


class MultiCopyRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=1)
    displacement: Point3D
    copy_count: int = Field(gt=0)
    include_original_position: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> MultiCopyRequest:
        if self.displacement == Point3D(x=0, y=0, z=0):
            raise ValueError("MC displacement must be non-zero")
        _approval(self.dry_run, self.approval, "MC")
        return self


class MultiCopyPlan(Batch21APlan):
    command_alias: str = "MC"
    legacy_symbol: str = "xiMCopy"
    semantic_evidence: str = "current+frozen shortcut: 등간격 연속 복사 (하위버전을 위해); displacement/count explicit"
    semantic_gaps: tuple[str, ...] = (
        "legacy count prompting",
        "base-point interaction",
        "array compatibility behavior",
    )
    transforms: tuple[TransformSpec, ...]


def plan_multi_copy(request: MultiCopyRequest) -> MultiCopyPlan:
    start = 0 if request.include_original_position else 1
    transforms = tuple(
        TransformSpec(
            source_handle=handle,
            translation=Point3D(
                x=request.displacement.x * index, y=request.displacement.y * index, z=request.displacement.z * index
            ),
            rotation_degrees=0,
            rotation_center=Point3D(x=0, y=0, z=0),
        )
        for index in range(start, request.copy_count + 1)
        for handle in request.source_handles
    )
    return MultiCopyPlan(document_id=request.document_id, transforms=transforms, dry_run=request.dry_run)


class MlineSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    component_lines: tuple[tuple[Point3D, ...], ...] = Field(min_length=1)
    source_style: str = Field(min_length=1)
    is_xref: bool = False
    locked_layer: bool = False


class MlineConvertRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    wall_layer: str = Field(min_length=1)
    delete_sources: bool
    require_supplied_components: bool = True
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> MlineConvertRequest:
        if not self.require_supplied_components:
            raise ValueError("MLC style decomposition is unrecovered; supplied components are required")
        _approval(self.dry_run, self.approval, "MLC")
        return self


class MlineConvertPlan(Batch21APlan):
    command_alias: str = "MLC"
    legacy_symbol: str = "xiMlineCv"
    semantic_evidence: str = (
        "frozen shortcut only: 멀티라인을 일반 벽체레이어로 자동 변경; absent from current shortcut"
    )
    semantic_gaps: tuple[str, ...] = ("MLINE style decomposition", "cap/joint handling", "wall-layer mapping rule")
    component_lines: dict[str, tuple[tuple[Point3D, ...], ...]]
    wall_layer: str
    delete_handles: tuple[str, ...]


def plan_mline_convert(request: MlineConvertRequest, snapshots: tuple[MlineSnapshot, ...]) -> MlineConvertPlan:
    by = {item.handle.casefold(): item for item in snapshots}
    result = {}
    for handle in request.target_handles:
        item = by.get(handle.casefold())
        if item is None or item.is_xref or item.locked_layer:
            raise ValueError(f"MLC source unavailable: {handle}")
        result[item.handle] = item.component_lines
    return MlineConvertPlan(
        document_id=request.document_id,
        component_lines=result,
        wall_layer=request.wall_layer,
        delete_handles=request.target_handles if request.delete_sources else (),
        dry_run=request.dry_run,
    )


def register_headless_core_batch21a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 21A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    def register(name: str):
        return lambda function: mcp.tool(name=name, annotations=annotations)(function)

    @register("xicad_plan_dac")
    def dac_tool(request: DivideArcCopyRequest) -> DivideArcCopyPlan:
        return plan_divide_arc_copy(request)

    @register("xicad_plan_dvc")
    def dvc_tool(request: DivideCopyRequest) -> DivideCopyPlan:
        return plan_divide_copy(request)

    @register("xicad_plan_exl")
    def exl_tool(request: ExtendLineRequest, snapshots: tuple[LineSnapshot, ...]) -> ExtendLinePlan:
        return plan_extend_line(request, snapshots)

    @register("xicad_plan_jl")
    def jl_tool(request: JoinLineRequest, snapshots: tuple[LineSnapshot, ...]) -> JoinLinePlan:
        return plan_join_line(request, snapshots)

    @register("xicad_plan_mc")
    def mc_tool(request: MultiCopyRequest) -> MultiCopyPlan:
        return plan_multi_copy(request)

    @register("xicad_plan_mlc")
    def mlc_tool(request: MlineConvertRequest, snapshots: tuple[MlineSnapshot, ...]) -> MlineConvertPlan:
        return plan_mline_convert(request, snapshots)
