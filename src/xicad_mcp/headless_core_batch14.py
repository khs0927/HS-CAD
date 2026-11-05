"""Dialog-free, read-only execution planners for xiCAD batch 14.

Only K/LEX/LXP have recoverable aliases in the frozen xiShortkey corpus.  The
remaining campaign names are therefore deliberately modelled with explicit
geometry operations instead of pretending that undocumented legacy prompts
were recovered.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import cos, isclose, radians, sin
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval fingerprint")


def _unique(handles: Sequence[str]) -> None:
    folded = [handle.casefold() for handle in handles]
    if len(folded) != len(set(folded)):
        raise ValueError("target handles must be unique")


class SourceDisposition(StrEnum):
    PRESERVE = "preserve"
    REPLACE = "replace"


class GeometrySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    vertices: tuple[Point3D, ...] = Field(min_length=1)
    layer: str = Field(min_length=1)
    closed: bool = False
    constant_width: float = Field(default=0, ge=0)
    elevation: float = 0
    is_xref: bool = False
    locked_layer: bool = False


def _selected(
    handles: Sequence[str], snapshots: Sequence[GeometrySnapshot], alias: str
) -> tuple[GeometrySnapshot, ...]:
    _unique(handles)
    by_handle = {snapshot.handle.casefold(): snapshot for snapshot in snapshots}
    result: list[GeometrySnapshot] = []
    for handle in handles:
        snapshot = by_handle.get(handle.casefold())
        if snapshot is None:
            raise ValueError(f"{alias} target not found: {handle}")
        if snapshot.is_xref or snapshot.locked_layer:
            raise ValueError(f"{alias} target is not editable: {handle}")
        result.append(snapshot)
    return tuple(result)


class Batch14Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False
    semantic_evidence: str


# K -- recoverable alias: xiK / K 기호그리기.
class KMarkRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    insertion_points: tuple[Point3D, ...] = Field(min_length=1)
    size: float = Field(gt=0)
    rotation_degrees: float = 0
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> KMarkRequest:
        _approval(self.dry_run, self.approval, "K")
        return self


class KMarkSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    strokes: tuple[tuple[Point3D, Point3D], ...]
    layer: str


class KMarkPlan(Batch14Plan):
    command_alias: str = "K"
    legacy_symbol: str = "xiK"
    semantic_evidence: str = "xiShortkey: K 기호그리기; geometry parameters explicit"
    creates: tuple[KMarkSpec, ...]


def plan_k_mark(request: KMarkRequest) -> KMarkPlan:
    angle = radians(request.rotation_degrees)

    def transform(origin: Point3D, x: float, y: float) -> Point3D:
        return Point3D(
            x=origin.x + request.size * (x * cos(angle) - y * sin(angle)),
            y=origin.y + request.size * (x * sin(angle) + y * cos(angle)),
            z=origin.z,
        )

    creates = tuple(
        KMarkSpec(
            strokes=(
                (transform(point, -0.5, -0.5), transform(point, -0.5, 0.5)),
                (transform(point, -0.5, 0), transform(point, 0.5, 0.5)),
                (transform(point, -0.5, 0), transform(point, 0.5, -0.5)),
            ),
            layer=request.layer,
        )
        for point in request.insertion_points
    )
    return KMarkPlan(document_id=request.document_id, creates=creates, dry_run=request.dry_run)


# LEX -- line-shape export is represented as data, never an implicit file write.
class LineExportRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    origin: Point3D
    normalize_scale: bool
    include_layer: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LineExportRequest:
        _unique(self.target_handles)
        _approval(self.dry_run, self.approval, "LEX")
        return self


class ExportedGeometry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    entity_type: str
    relative_vertices: tuple[Point3D, ...]
    layer: str | None


class LineExportPlan(Batch14Plan):
    command_alias: str = "LEX"
    legacy_symbol: str = "xiLTEx"
    semantic_evidence: str = "xiShortkey: 선 모양 내보내기; destination I/O intentionally excluded"
    exports: tuple[ExportedGeometry, ...]


def plan_line_export(request: LineExportRequest, snapshots: Sequence[GeometrySnapshot]) -> LineExportPlan:
    selected = _selected(request.target_handles, snapshots, "LEX")
    scale = 1.0
    if request.normalize_scale:
        maximum = max(
            (
                abs(value)
                for item in selected
                for point in item.vertices
                for value in (point.x - request.origin.x, point.y - request.origin.y)
            ),
            default=0,
        )
        if maximum == 0:
            raise ValueError("LEX cannot normalize zero-size geometry")
        scale = maximum
    exports = tuple(
        ExportedGeometry(
            source_handle=item.handle,
            entity_type=item.entity_type,
            relative_vertices=tuple(
                Point3D(
                    x=(point.x - request.origin.x) / scale,
                    y=(point.y - request.origin.y) / scale,
                    z=(point.z - request.origin.z) / scale,
                )
                for point in item.vertices
            ),
            layer=item.layer if request.include_layer else None,
        )
        for item in selected
    )
    return LineExportPlan(document_id=request.document_id, exports=exports, dry_run=request.dry_run)


# LXP -- explicit primitive decomposition; unsupported curve interpolation is blocked.
class ExplodePolicy(StrEnum):
    LINE_SEGMENTS = "line_segments"
    PRESERVE_ARCS = "preserve_arcs"


class LineExplodeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    policy: ExplodePolicy
    source_disposition: SourceDisposition
    target_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LineExplodeRequest:
        _unique(self.target_handles)
        if self.policy is ExplodePolicy.PRESERVE_ARCS:
            raise ValueError("LXP preserve_arcs is blocked until bulge semantics are supplied")
        _approval(self.dry_run, self.approval, "LXP")
        return self


class SegmentSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    start: Point3D
    end: Point3D
    layer: str


class LineExplodePlan(Batch14Plan):
    command_alias: str = "LXP"
    legacy_symbol: str = "xiLineXp"
    semantic_evidence: str = "xiShortkey: 선 모양대로 폭파하기; curve mode explicitly blocked"
    creates: tuple[SegmentSpec, ...]
    delete_handles: tuple[str, ...]


def plan_line_explode(request: LineExplodeRequest, snapshots: Sequence[GeometrySnapshot]) -> LineExplodePlan:
    selected = _selected(request.target_handles, snapshots, "LXP")
    creates: list[SegmentSpec] = []
    for item in selected:
        points = item.vertices + ((item.vertices[0],) if item.closed else ())
        creates.extend(
            SegmentSpec(source_handle=item.handle, start=start, end=end, layer=request.target_layer)
            for start, end in zip(points, points[1:], strict=False)
            if start != end
        )
    return LineExplodePlan(
        document_id=request.document_id,
        creates=tuple(creates),
        delete_handles=request.target_handles if request.source_disposition is SourceDisposition.REPLACE else (),
        dry_run=request.dry_run,
    )


# Undocumented campaign aliases: callers must select the exact operation.
class EndpointOperation(StrEnum):
    MOVE_START = "move_start"
    MOVE_END = "move_end"
    EXTEND_START = "extend_start"
    EXTEND_END = "extend_end"


class EndpointEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handle: str = Field(min_length=1)
    operation: EndpointOperation
    target_point: Point3D
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> EndpointEditRequest:
        _approval(self.dry_run, self.approval, "ME")
        return self


class VertexPlan(Batch14Plan):
    target_vertices: dict[str, tuple[Point3D, ...]]
    delete_handles: tuple[str, ...] = ()


def plan_endpoint_edit(request: EndpointEditRequest, snapshots: Sequence[GeometrySnapshot]) -> VertexPlan:
    item = _selected((request.target_handle,), snapshots, "ME")[0]
    vertices = list(item.vertices)
    if request.operation is EndpointOperation.MOVE_START:
        vertices[0] = request.target_point
    elif request.operation is EndpointOperation.MOVE_END:
        vertices[-1] = request.target_point
    elif request.operation is EndpointOperation.EXTEND_START:
        vertices.insert(0, request.target_point)
    else:
        vertices.append(request.target_point)
    return VertexPlan(
        command_alias="ME",
        legacy_symbol="unresolved:ME",
        semantic_evidence="alias absent from frozen xiShortkey; explicit endpoint operation required",
        document_id=request.document_id,
        target_vertices={item.handle: tuple(vertices)},
        dry_run=request.dry_run,
    )


class PolylineToCircleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handle: str = Field(min_length=1)
    sample_indices: tuple[int, int, int]
    source_disposition: SourceDisposition
    target_layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> PolylineToCircleRequest:
        if len(set(self.sample_indices)) != 3 or min(self.sample_indices) < 0:
            raise ValueError("P2C requires three distinct non-negative sample indices")
        _approval(self.dry_run, self.approval, "P2C")
        return self


class CircleSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    center: Point3D
    radius: float = Field(gt=0)
    layer: str


class PolylineToCirclePlan(Batch14Plan):
    command_alias: str = "P2C"
    legacy_symbol: str = "unresolved:P2C"
    semantic_evidence: str = "alias absent from frozen xiShortkey; explicit three-point circumcircle policy"
    create: CircleSpec
    delete_handles: tuple[str, ...]


def plan_polyline_to_circle(
    request: PolylineToCircleRequest, snapshots: Sequence[GeometrySnapshot]
) -> PolylineToCirclePlan:
    item = _selected((request.source_handle,), snapshots, "P2C")[0]
    if max(request.sample_indices) >= len(item.vertices):
        raise ValueError("P2C sample index is outside source vertices")
    a, b, c = (item.vertices[index] for index in request.sample_indices)
    determinant = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
    if isclose(determinant, 0, abs_tol=1e-12):
        raise ValueError("P2C sample points are collinear")
    ux = (
        (a.x**2 + a.y**2) * (b.y - c.y) + (b.x**2 + b.y**2) * (c.y - a.y) + (c.x**2 + c.y**2) * (a.y - b.y)
    ) / determinant
    uy = (
        (a.x**2 + a.y**2) * (c.x - b.x) + (b.x**2 + b.y**2) * (a.x - c.x) + (c.x**2 + c.y**2) * (b.x - a.x)
    ) / determinant
    radius = ((ux - a.x) ** 2 + (uy - a.y) ** 2) ** 0.5
    return PolylineToCirclePlan(
        document_id=request.document_id,
        create=CircleSpec(center=Point3D(x=ux, y=uy, z=a.z), radius=radius, layer=request.target_layer),
        delete_handles=(item.handle,) if request.source_disposition is SourceDisposition.REPLACE else (),
        dry_run=request.dry_run,
    )


class PolylineEditMode(StrEnum):
    CLOSE = "close"
    OPEN = "open"
    SET_WIDTH = "set_width"
    SET_ELEVATION = "set_elevation"


class PolylineEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: PolylineEditMode
    width: float | None = Field(default=None, ge=0)
    elevation: float | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> PolylineEditRequest:
        if self.mode is PolylineEditMode.SET_WIDTH and self.width is None:
            raise ValueError("PE set_width requires width")
        if self.mode is PolylineEditMode.SET_ELEVATION and self.elevation is None:
            raise ValueError("PE set_elevation requires elevation")
        _unique(self.target_handles)
        _approval(self.dry_run, self.approval, "PE")
        return self


class PolylineEditSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    closed: bool
    width: float
    elevation: float


class PolylineEditPlan(Batch14Plan):
    command_alias: str = "PE"
    legacy_symbol: str = "unresolved:PE"
    semantic_evidence: str = "alias absent from frozen xiShortkey; exact edit mode required"
    edits: tuple[PolylineEditSpec, ...]


def plan_polyline_edit(request: PolylineEditRequest, snapshots: Sequence[GeometrySnapshot]) -> PolylineEditPlan:
    edits = []
    for item in _selected(request.target_handles, snapshots, "PE"):
        edits.append(
            PolylineEditSpec(
                handle=item.handle,
                closed=request.mode is PolylineEditMode.CLOSE
                or (item.closed and request.mode is not PolylineEditMode.OPEN),
                width=request.width if request.mode is PolylineEditMode.SET_WIDTH else item.constant_width,
                elevation=request.elevation if request.mode is PolylineEditMode.SET_ELEVATION else item.elevation,
            )
        )
    return PolylineEditPlan(document_id=request.document_id, edits=tuple(edits), dry_run=request.dry_run)


class BreakPolylineRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handle: str = Field(min_length=1)
    break_after_index: int = Field(ge=0)
    close_outputs: bool
    source_disposition: SourceDisposition
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> BreakPolylineRequest:
        _approval(self.dry_run, self.approval, "PLBC" if self.close_outputs else "PLB")
        return self


class BreakPolylinePlan(Batch14Plan):
    output_vertices: tuple[tuple[Point3D, ...], tuple[Point3D, ...]]
    outputs_closed: bool
    delete_handles: tuple[str, ...]


def plan_break_polyline(request: BreakPolylineRequest, snapshots: Sequence[GeometrySnapshot]) -> BreakPolylinePlan:
    alias = "PLBC" if request.close_outputs else "PLB"
    item = _selected((request.source_handle,), snapshots, alias)[0]
    if request.break_after_index >= len(item.vertices) - 1:
        raise ValueError(f"{alias} break index must leave at least one segment on both sides")
    left = item.vertices[: request.break_after_index + 1]
    right = item.vertices[request.break_after_index + 1 :]
    return BreakPolylinePlan(
        command_alias=alias,
        legacy_symbol=f"unresolved:{alias}",
        semantic_evidence="alias absent from frozen xiShortkey; explicit vertex split and close policy",
        document_id=request.document_id,
        output_vertices=(left, right),
        outputs_closed=request.close_outputs,
        delete_handles=(item.handle,) if request.source_disposition is SourceDisposition.REPLACE else (),
        dry_run=request.dry_run,
    )


class ExtendSide(StrEnum):
    START = "start"
    END = "end"


class PolylineExtendRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handle: str = Field(min_length=1)
    side: ExtendSide
    extension_points: tuple[Point3D, ...] = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> PolylineExtendRequest:
        _approval(self.dry_run, self.approval, "PLE")
        return self


def plan_polyline_extend(request: PolylineExtendRequest, snapshots: Sequence[GeometrySnapshot]) -> VertexPlan:
    item = _selected((request.source_handle,), snapshots, "PLE")[0]
    vertices = (
        tuple(reversed(request.extension_points)) + item.vertices
        if request.side is ExtendSide.START
        else item.vertices + request.extension_points
    )
    return VertexPlan(
        command_alias="PLE",
        legacy_symbol="unresolved:PLE",
        semantic_evidence="alias absent from frozen xiShortkey; explicit side and extension vertices",
        document_id=request.document_id,
        target_vertices={item.handle: vertices},
        dry_run=request.dry_run,
    )


class HandleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> HandleRequest:
        _unique(self.target_handles)
        _approval(self.dry_run, self.approval, "PLR")
        return self


def plan_polyline_reverse(request: HandleRequest, snapshots: Sequence[GeometrySnapshot]) -> VertexPlan:
    selected = _selected(request.target_handles, snapshots, "PLR")
    return VertexPlan(
        command_alias="PLR",
        legacy_symbol="unresolved:PLR",
        semantic_evidence="alias absent from frozen xiShortkey; deterministic vertex reversal",
        document_id=request.document_id,
        target_vertices={item.handle: tuple(reversed(item.vertices)) for item in selected},
        dry_run=request.dry_run,
    )


class ProjectionAxis(StrEnum):
    XY = "xy"
    XZ = "xz"
    YZ = "yz"


class ProjectRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    plane: ProjectionAxis
    offset: float = 0
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ProjectRequest:
        _unique(self.target_handles)
        _approval(self.dry_run, self.approval, "PR")
        return self


def plan_project(request: ProjectRequest, snapshots: Sequence[GeometrySnapshot]) -> VertexPlan:
    selected = _selected(request.target_handles, snapshots, "PR")

    def project(point: Point3D) -> Point3D:
        if request.plane is ProjectionAxis.XY:
            return Point3D(x=point.x, y=point.y, z=request.offset)
        if request.plane is ProjectionAxis.XZ:
            return Point3D(x=point.x, y=request.offset, z=point.z)
        return Point3D(x=request.offset, y=point.y, z=point.z)

    return VertexPlan(
        command_alias="PR",
        legacy_symbol="unresolved:PR",
        semantic_evidence="alias absent from frozen xiShortkey; explicit orthogonal projection plane",
        document_id=request.document_id,
        target_vertices={item.handle: tuple(project(point) for point in item.vertices) for item in selected},
        dry_run=request.dry_run,
    )


class RectangleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    center: Point3D
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    rotation_degrees: float = 0
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> RectangleRequest:
        _approval(self.dry_run, self.approval, "REC")
        return self


class RectanglePlan(Batch14Plan):
    command_alias: str = "REC"
    legacy_symbol: str = "unresolved:REC"
    semantic_evidence: str = "alias absent from frozen xiShortkey; center/size/rotation geometry explicit"
    vertices: tuple[Point3D, Point3D, Point3D, Point3D]
    layer: str


def plan_rectangle(request: RectangleRequest) -> RectanglePlan:
    angle = radians(request.rotation_degrees)
    vertices = []
    for x, y in (
        (-request.width / 2, -request.height / 2),
        (request.width / 2, -request.height / 2),
        (request.width / 2, request.height / 2),
        (-request.width / 2, request.height / 2),
    ):
        vertices.append(
            Point3D(
                x=request.center.x + x * cos(angle) - y * sin(angle),
                y=request.center.y + x * sin(angle) + y * cos(angle),
                z=request.center.z,
            )
        )
    return RectanglePlan(
        document_id=request.document_id, vertices=tuple(vertices), layer=request.layer, dry_run=request.dry_run
    )


def register_headless_core_batch14_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 14 Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    def register(name: str):
        return lambda function: mcp.tool(name=name, annotations=annotations)(function)

    @register("xicad_plan_k")
    def k_tool(request: KMarkRequest) -> KMarkPlan:
        return plan_k_mark(request)

    @register("xicad_plan_lex")
    def lex_tool(request: LineExportRequest, snapshots: tuple[GeometrySnapshot, ...]) -> LineExportPlan:
        return plan_line_export(request, snapshots)

    @register("xicad_plan_lxp")
    def lxp_tool(request: LineExplodeRequest, snapshots: tuple[GeometrySnapshot, ...]) -> LineExplodePlan:
        return plan_line_explode(request, snapshots)

    @register("xicad_plan_me")
    def me_tool(request: EndpointEditRequest, snapshots: tuple[GeometrySnapshot, ...]) -> VertexPlan:
        return plan_endpoint_edit(request, snapshots)

    @register("xicad_plan_p2c")
    def p2c_tool(request: PolylineToCircleRequest, snapshots: tuple[GeometrySnapshot, ...]) -> PolylineToCirclePlan:
        return plan_polyline_to_circle(request, snapshots)

    @register("xicad_plan_pe")
    def pe_tool(request: PolylineEditRequest, snapshots: tuple[GeometrySnapshot, ...]) -> PolylineEditPlan:
        return plan_polyline_edit(request, snapshots)

    @register("xicad_plan_plb")
    def plb_tool(request: BreakPolylineRequest, snapshots: tuple[GeometrySnapshot, ...]) -> BreakPolylinePlan:
        if request.close_outputs:
            raise ValueError("PLB requires close_outputs=false")
        return plan_break_polyline(request, snapshots)

    @register("xicad_plan_plbc")
    def plbc_tool(request: BreakPolylineRequest, snapshots: tuple[GeometrySnapshot, ...]) -> BreakPolylinePlan:
        if not request.close_outputs:
            raise ValueError("PLBC requires close_outputs=true")
        return plan_break_polyline(request, snapshots)

    @register("xicad_plan_ple")
    def ple_tool(request: PolylineExtendRequest, snapshots: tuple[GeometrySnapshot, ...]) -> VertexPlan:
        return plan_polyline_extend(request, snapshots)

    @register("xicad_plan_plr")
    def plr_tool(request: HandleRequest, snapshots: tuple[GeometrySnapshot, ...]) -> VertexPlan:
        return plan_polyline_reverse(request, snapshots)

    @register("xicad_plan_pr")
    def pr_tool(request: ProjectRequest, snapshots: tuple[GeometrySnapshot, ...]) -> VertexPlan:
        return plan_project(request, snapshots)

    @register("xicad_plan_rec")
    def rec_tool(request: RectangleRequest) -> RectanglePlan:
        return plan_rectangle(request)
