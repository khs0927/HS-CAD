from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import dist
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch5 import TextEntityKind, TextEntitySnapshot
from .headless_core_batch11 import DimensionKind, DimensionSnapshot
from .headless_core_batch12 import LeaderKind


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval")


def _unique(values: Sequence[str], name: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{name} must be unique")


class Batch13Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class SourceDisposition(StrEnum):
    PRESERVE = "preserve"
    REPLACE = "replace"


# LX / TL
class LeaderDefinitionSource(StrEnum):
    DRAWING_STYLE = "drawing_style"
    XICAD_EXPLICIT = "xicad_explicit"


class LeaderEndShape(StrEnum):
    DOT = "dot"
    ARROW = "arrow"
    WAVE = "wave"
    POLYLINE = "polyline"


class LeaderTextLocation(StrEnum):
    SIDE = "side"
    TOP = "top"


class LeaderTextKind(StrEnum):
    TEXT = "text"
    MTEXT = "mtext"


class LeaderPlacement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    arrow_point: Point3D
    elbow_point: Point3D
    text_point: Point3D
    text: str
    source_block_name: str | None = None


class AutoLeaderRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    placements: tuple[LeaderPlacement, ...] = Field(min_length=1)
    definition_source: LeaderDefinitionSource
    style: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    text_kind: LeaderTextKind
    end_shape: LeaderEndShape
    text_location: LeaderTextLocation
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    head_size: float = Field(gt=0)
    dimscale: float = Field(gt=0)
    fixed_angle_degrees: float | None = None
    polyline_head_height: float | None = Field(default=None, gt=0)
    polyline_head_width: float | None = Field(default=None, gt=0)
    use_block_name_as_text: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> AutoLeaderRequest:
        if self.end_shape is LeaderEndShape.POLYLINE and (
            self.polyline_head_height is None or self.polyline_head_width is None
        ):
            raise ValueError("LX polyline head requires height and width")
        if self.use_block_name_as_text and any(not p.source_block_name for p in self.placements):
            raise ValueError("LX block-name text requires source_block_name for every placement")
        _approval(self.dry_run, self.approval, "LX")
        return self


class LeaderCreateSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_text_handle: str | None = None
    kind: LeaderKind
    points: tuple[Point3D, ...]
    text: str
    style: str
    layer: str
    end_shape: LeaderEndShape
    text_location: LeaderTextLocation
    text_style: str
    text_height: float
    head_size: float
    dimscale: float
    fixed_angle_degrees: float | None


class AutoLeaderPlan(Batch13Plan):
    command_alias: str = "LX"
    legacy_symbol: str = "xiAutoLeader"
    creates: tuple[LeaderCreateSpec, ...]


def plan_auto_leader(request: AutoLeaderRequest) -> AutoLeaderPlan:
    creates = tuple(
        LeaderCreateSpec(
            kind=LeaderKind.MLEADER,
            points=(p.arrow_point, p.elbow_point, p.text_point),
            text=p.source_block_name if request.use_block_name_as_text else p.text,
            style=request.style,
            layer=request.layer,
            end_shape=request.end_shape,
            text_location=request.text_location,
            text_style=request.text_style,
            text_height=request.text_height,
            head_size=request.head_size,
            dimscale=request.dimscale,
            fixed_angle_degrees=request.fixed_angle_degrees,
        )
        for p in request.placements
    )
    return AutoLeaderPlan(document_id=request.document_id, creates=creates, dry_run=request.dry_run)


class TextLeaderPlacement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text_handle: str = Field(min_length=1)
    arrow_point: Point3D
    elbow_point: Point3D


class TextToLeaderRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    placements: tuple[TextLeaderPlacement, ...] = Field(min_length=1)
    leader_kind: LeaderKind
    style: str = Field(min_length=1)
    dimscale: float = Field(gt=0)
    layer: str = Field(min_length=1)
    end_shape: LeaderEndShape
    head_size: float = Field(gt=0)
    fixed_angle_degrees: float | None = None
    match_text_to_style: bool
    target_text_style: str | None = None
    target_text_height: float | None = Field(default=None, gt=0)
    preserve_selection_order: bool
    line_gap_height_factor: float = Field(ge=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextToLeaderRequest:
        _unique(tuple(p.text_handle for p in self.placements), "text handles")
        if self.match_text_to_style and (not self.target_text_style or self.target_text_height is None):
            raise ValueError("TL style matching requires text style and height")
        _approval(self.dry_run, self.approval, "TL")
        return self


class TextToLeaderPlan(Batch13Plan):
    command_alias: str = "TL"
    legacy_symbol: str = "xiText2Leader"
    creates: tuple[LeaderCreateSpec, ...]
    text_style_changes: dict[str, tuple[str, float]]


def plan_text_to_leader(request: TextToLeaderRequest, entities: Sequence[TextEntitySnapshot]) -> TextToLeaderPlan:
    by_handle = {entity.handle.casefold(): entity for entity in entities}
    creates, changes = [], {}
    for placement in request.placements:
        entity = by_handle.get(placement.text_handle.casefold())
        if (
            entity is None
            or entity.is_xref
            or entity.locked_layer
            or entity.kind not in {TextEntityKind.TEXT, TextEntityKind.MTEXT}
        ):
            raise ValueError(f"TL text unavailable: {placement.text_handle}")
        creates.append(
            LeaderCreateSpec(
                source_text_handle=entity.handle,
                kind=request.leader_kind,
                points=(placement.arrow_point, placement.elbow_point, entity.insertion_point),
                text=entity.text,
                style=request.style,
                layer=request.layer,
                end_shape=request.end_shape,
                text_location=LeaderTextLocation.SIDE,
                text_style=request.target_text_style or entity.text_style,
                text_height=request.target_text_height or entity.text_height,
                head_size=request.head_size,
                dimscale=request.dimscale,
                fixed_angle_degrees=request.fixed_angle_degrees,
            )
        )
        if request.match_text_to_style:
            changes[entity.handle] = (request.target_text_style, request.target_text_height)
    return TextToLeaderPlan(
        document_id=request.document_id, creates=tuple(creates), text_style_changes=changes, dry_run=request.dry_run
    )


# SD
class SplitDimensionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handle: str = Field(min_length=1)
    split_points: tuple[Point3D, ...] = Field(min_length=1)
    source_disposition: SourceDisposition
    preserve_style: bool = True
    preserve_text_override: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SplitDimensionRequest:
        _approval(self.dry_run, self.approval, "SD")
        return self


class SplitDimensionSegment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    first_point: Point3D
    second_point: Point3D
    style: str | None
    text_override: str


class SplitDimensionPlan(Batch13Plan):
    command_alias: str = "SD"
    legacy_symbol: str = "xiSplitDim"
    segments: tuple[SplitDimensionSegment, ...]
    erase_source: bool


def plan_split_dimension(request: SplitDimensionRequest, dimensions: Sequence[DimensionSnapshot]) -> SplitDimensionPlan:
    source = next((d for d in dimensions if d.handle.casefold() == request.source_handle.casefold()), None)
    if (
        source is None
        or source.is_xref
        or source.locked_layer
        or source.kind not in {DimensionKind.ALIGNED, DimensionKind.ROTATED}
    ):
        raise ValueError("SD requires an available linear dimension")
    points = (source.first_extension_origin, *request.split_points, source.second_extension_origin)
    if any(dist((a.x, a.y, a.z), (b.x, b.y, b.z)) == 0 for a, b in zip(points, points[1:], strict=False)):
        raise ValueError("SD split points create zero-length segment")
    segments = tuple(
        SplitDimensionSegment(
            source_handle=source.handle,
            first_point=a,
            second_point=b,
            style=source.style if request.preserve_style else None,
            text_override=source.text_override if request.preserve_text_override else "",
        )
        for a, b in zip(points, points[1:], strict=False)
    )
    return SplitDimensionPlan(
        document_id=request.document_id,
        segments=segments,
        erase_source=request.source_disposition is SourceDisposition.REPLACE,
        dry_run=request.dry_run,
    )


# Generic geometry snapshots for shape commands.
class PolylineSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    vertices: tuple[Point3D, ...] = Field(min_length=2)
    closed: bool = False
    layer: str = Field(min_length=1)
    locked_layer: bool = False
    is_xref: bool = False


class GeometryCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handles: tuple[str, ...]
    vertices: tuple[Point3D, ...] = Field(min_length=2)
    closed: bool
    layer: str


# 2DP
class ProjectionPolicy(StrEnum):
    AFFINE_MATRIX = "affine_matrix"
    NORMALIZED_BOUNDARY_MAP = "normalized_boundary_map"


class ProjectionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=1)
    source_boundary_handle: str
    target_boundary_handle: str
    policy: ProjectionPolicy
    affine_matrix_4x4: tuple[tuple[float, float, float, float], ...] | None = None
    normalized_output_vertices: dict[str, tuple[Point3D, ...]] = {}
    target_layer: str = Field(min_length=1)
    source_disposition: SourceDisposition
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ProjectionRequest:
        if self.policy is ProjectionPolicy.AFFINE_MATRIX and (
            self.affine_matrix_4x4 is None
            or len(self.affine_matrix_4x4) != 4
            or any(len(row) != 4 for row in self.affine_matrix_4x4)
        ):
            raise ValueError("2DP affine policy requires a 4x4 matrix")
        if self.policy is ProjectionPolicy.NORMALIZED_BOUNDARY_MAP and set(
            h.casefold() for h in self.normalized_output_vertices
        ) != set(h.casefold() for h in self.source_handles):
            raise ValueError("2DP normalized map requires output vertices for every source")
        _approval(self.dry_run, self.approval, "2DP")
        return self


class ProjectionPlan(Batch13Plan):
    command_alias: str = "2DP"
    legacy_symbol: str = "xi2dPro"
    creates: tuple[GeometryCreate, ...]
    erase_source_handles: tuple[str, ...]


def plan_projection(request: ProjectionRequest, geometries: Sequence[PolylineSnapshot]) -> ProjectionPlan:
    by_handle = {g.handle.casefold(): g for g in geometries}
    creates = []
    for handle in request.source_handles:
        source = by_handle.get(handle.casefold())
        if source is None or source.is_xref or source.locked_layer:
            raise ValueError(f"2DP source unavailable: {handle}")
        if request.policy is ProjectionPolicy.NORMALIZED_BOUNDARY_MAP:
            vertices = next(
                v for h, v in request.normalized_output_vertices.items() if h.casefold() == handle.casefold()
            )
        else:
            m = request.affine_matrix_4x4
            vertices = tuple(
                Point3D(
                    x=m[0][0] * p.x + m[0][1] * p.y + m[0][2] * p.z + m[0][3],
                    y=m[1][0] * p.x + m[1][1] * p.y + m[1][2] * p.z + m[1][3],
                    z=m[2][0] * p.x + m[2][1] * p.y + m[2][2] * p.z + m[2][3],
                )
                for p in source.vertices
            )
        creates.append(
            GeometryCreate(
                source_handles=(source.handle,), vertices=vertices, closed=source.closed, layer=request.target_layer
            )
        )
    return ProjectionPlan(
        document_id=request.document_id,
        creates=tuple(creates),
        erase_source_handles=request.source_handles if request.source_disposition is SourceDisposition.REPLACE else (),
        dry_run=request.dry_run,
    )


# 3TP
class FlattenPolicy(StrEnum):
    DROP_Z = "drop_z"
    CONSTANT_Z = "constant_z"
    EXPLICIT_PROJECTED_VERTICES = "explicit_projected_vertices"


class Polyline3DConvertRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    flatten_policy: FlattenPolicy
    constant_z: float | None = None
    projected_vertices: dict[str, tuple[Point3D, ...]] = {}
    source_disposition: SourceDisposition
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> Polyline3DConvertRequest:
        if self.flatten_policy is FlattenPolicy.CONSTANT_Z and self.constant_z is None:
            raise ValueError("3TP constant_z policy requires value")
        if self.flatten_policy is FlattenPolicy.EXPLICIT_PROJECTED_VERTICES and set(
            h.casefold() for h in self.projected_vertices
        ) != set(h.casefold() for h in self.target_handles):
            raise ValueError("3TP projected vertices required for every target")
        _approval(self.dry_run, self.approval, "3TP")
        return self


class Polyline3DConvertPlan(Batch13Plan):
    command_alias: str = "3TP"
    legacy_symbol: str = "xi3dPolyToLwPoly"
    creates: tuple[GeometryCreate, ...]
    erase_source_handles: tuple[str, ...]


def plan_3dpoly_to_lwpoly(
    request: Polyline3DConvertRequest, polylines: Sequence[PolylineSnapshot]
) -> Polyline3DConvertPlan:
    by = {p.handle.casefold(): p for p in polylines}
    creates = []
    for handle in request.target_handles:
        p = by.get(handle.casefold())
        if p is None or p.is_xref or p.locked_layer:
            raise ValueError(f"3TP source unavailable: {handle}")
        if request.flatten_policy is FlattenPolicy.EXPLICIT_PROJECTED_VERTICES:
            vertices = next(v for h, v in request.projected_vertices.items() if h.casefold() == handle.casefold())
        else:
            z = 0 if request.flatten_policy is FlattenPolicy.DROP_Z else request.constant_z
            vertices = tuple(Point3D(x=v.x, y=v.y, z=z) for v in p.vertices)
        creates.append(GeometryCreate(source_handles=(p.handle,), vertices=vertices, closed=p.closed, layer=p.layer))
    return Polyline3DConvertPlan(
        document_id=request.document_id,
        creates=tuple(creates),
        erase_source_handles=request.target_handles if request.source_disposition is SourceDisposition.REPLACE else (),
        dry_run=request.dry_run,
    )


# BOO
class JoinPolylineRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    ordered_handles: tuple[str, ...] = Field(min_length=2)
    reverse_handles: tuple[str, ...] = ()
    tolerance: float = Field(ge=0)
    close_result: bool = False
    target_layer: str = Field(min_length=1)
    source_disposition: SourceDisposition
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> JoinPolylineRequest:
        _unique(self.ordered_handles, "ordered_handles")
        if not set(h.casefold() for h in self.reverse_handles) <= set(h.casefold() for h in self.ordered_handles):
            raise ValueError("BOO reverse handles must be joined handles")
        _approval(self.dry_run, self.approval, "BOO")
        return self


class JoinPolylinePlan(Batch13Plan):
    command_alias: str = "BOO"
    legacy_symbol: str = "xiBoo"
    create: GeometryCreate
    erase_source_handles: tuple[str, ...]


def plan_join_polylines(request: JoinPolylineRequest, polylines: Sequence[PolylineSnapshot]) -> JoinPolylinePlan:
    by = {p.handle.casefold(): p for p in polylines}
    vertices = []
    for handle in request.ordered_handles:
        p = by.get(handle.casefold())
        if p is None or p.is_xref or p.locked_layer:
            raise ValueError(f"BOO source unavailable: {handle}")
        part = (
            list(reversed(p.vertices))
            if handle.casefold() in {h.casefold() for h in request.reverse_handles}
            else list(p.vertices)
        )
        if (
            vertices
            and dist((vertices[-1].x, vertices[-1].y, vertices[-1].z), (part[0].x, part[0].y, part[0].z))
            > request.tolerance
        ):
            raise ValueError("BOO endpoints exceed tolerance")
        vertices.extend(part[1:] if vertices else part)
    create = GeometryCreate(
        source_handles=request.ordered_handles,
        vertices=tuple(vertices),
        closed=request.close_result,
        layer=request.target_layer,
    )
    return JoinPolylinePlan(
        document_id=request.document_id,
        create=create,
        erase_source_handles=request.ordered_handles if request.source_disposition is SourceDisposition.REPLACE else (),
        dry_run=request.dry_run,
    )


# BS / CM / CMW / DRL / JUL use explicit create specifications.
class BreakSymbolKind(StrEnum):
    ZIGZAG = "zigzag"
    WAVE = "wave"
    DOUBLE_LINE = "double_line"


class BreakSymbolRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str
    start: Point3D
    end: Point3D
    kind: BreakSymbolKind
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    layer: str
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def val(self):
        if self.start == self.end:
            raise ValueError("BS endpoints must differ")
        _approval(self.dry_run, self.approval, "BS")
        return self


class BreakSymbolPlan(Batch13Plan):
    command_alias: str = "BS"
    legacy_symbol: str = "xiBrkSymDCL"
    start: Point3D
    end: Point3D
    kind: BreakSymbolKind
    width: float
    height: float
    layer: str


def plan_break_symbol(r: BreakSymbolRequest) -> BreakSymbolPlan:
    return BreakSymbolPlan(
        document_id=r.document_id,
        start=r.start,
        end=r.end,
        kind=r.kind,
        width=r.width,
        height=r.height,
        layer=r.layer,
        dry_run=r.dry_run,
    )


class ContourJoinEnd(StrEnum):
    START = "start"
    END = "end"
    BOTH = "both"


class ContourJoinRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str
    contour_handle: str
    boundary_handle: str
    ends: ContourJoinEnd
    start_boundary_point: Point3D | None = None
    end_boundary_point: Point3D | None = None
    source_disposition: SourceDisposition
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def val(self):
        if self.ends in {ContourJoinEnd.START, ContourJoinEnd.BOTH} and self.start_boundary_point is None:
            raise ValueError("CBJ start boundary point required")
        if self.ends in {ContourJoinEnd.END, ContourJoinEnd.BOTH} and self.end_boundary_point is None:
            raise ValueError("CBJ end boundary point required")
        _approval(self.dry_run, self.approval, "CBJ")
        return self


class ContourJoinPlan(Batch13Plan):
    command_alias: str = "CBJ"
    legacy_symbol: str = "xiContourBoxJoin"
    create: GeometryCreate
    erase_source: bool


def plan_contour_join(r: ContourJoinRequest, polylines: Sequence[PolylineSnapshot]) -> ContourJoinPlan:
    p = next((p for p in polylines if p.handle.casefold() == r.contour_handle.casefold()), None)
    if p is None or p.is_xref or p.locked_layer:
        raise ValueError("CBJ contour unavailable")
    v = list(p.vertices)
    if r.ends in {ContourJoinEnd.START, ContourJoinEnd.BOTH}:
        v.insert(0, r.start_boundary_point)
    if r.ends in {ContourJoinEnd.END, ContourJoinEnd.BOTH}:
        v.append(r.end_boundary_point)
    return ContourJoinPlan(
        document_id=r.document_id,
        create=GeometryCreate(
            source_handles=(p.handle, r.boundary_handle), vertices=tuple(v), closed=False, layer=p.layer
        ),
        erase_source=r.source_disposition is SourceDisposition.REPLACE,
        dry_run=r.dry_run,
    )


class CloudStyle(StrEnum):
    NORMAL = "normal"
    CALLIGRAPHY = "calligraphy"


class RevisionCloudRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str
    boundary_vertices: tuple[Point3D, ...] = Field(min_length=3)
    closed: bool = True
    min_arc_length: float = Field(gt=0)
    max_arc_length: float = Field(gt=0)
    style: CloudStyle
    layer: str
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def val(self):
        if self.max_arc_length < self.min_arc_length:
            raise ValueError("CM max arc must not be less than min")
        _approval(self.dry_run, self.approval, "CM")
        return self


class RevisionCloudPlan(Batch13Plan):
    command_alias: str = "CM"
    legacy_symbol: str = "xiCM"
    vertices: tuple[Point3D, ...]
    closed: bool
    min_arc_length: float
    max_arc_length: float
    style: CloudStyle
    layer: str


def plan_revision_cloud(r: RevisionCloudRequest) -> RevisionCloudPlan:
    return RevisionCloudPlan(
        document_id=r.document_id,
        vertices=r.boundary_vertices,
        closed=r.closed,
        min_arc_length=r.min_arc_length,
        max_arc_length=r.max_arc_length,
        style=r.style,
        layer=r.layer,
        dry_run=r.dry_run,
    )


class WidthSide(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"


class CloudWidthRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str
    target_handles: tuple[str, ...] = Field(min_length=1)
    width: float = Field(gt=0)
    side: WidthSide
    cap_ends: bool
    source_disposition: SourceDisposition
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def val(self):
        _approval(self.dry_run, self.approval, "CMW")
        return self


class CloudWidthSpec(BaseModel):
    source_handle: str
    vertices: tuple[Point3D, ...]
    width: float
    side: WidthSide
    cap_ends: bool
    layer: str


class CloudWidthPlan(Batch13Plan):
    command_alias: str = "CMW"
    legacy_symbol: str = "xiCloudMarkWidth"
    specs: tuple[CloudWidthSpec, ...]
    erase_source_handles: tuple[str, ...]


def plan_cloud_width(r: CloudWidthRequest, ps: Sequence[PolylineSnapshot]) -> CloudWidthPlan:
    by = {p.handle.casefold(): p for p in ps}
    specs = []
    for h in r.target_handles:
        p = by.get(h.casefold())
        if p is None or p.is_xref or p.locked_layer:
            raise ValueError(f"CMW cloud unavailable: {h}")
        specs.append(
            CloudWidthSpec(
                source_handle=p.handle,
                vertices=p.vertices,
                width=r.width,
                side=r.side,
                cap_ends=r.cap_ends,
                layer=p.layer,
            )
        )
    return CloudWidthPlan(
        document_id=r.document_id,
        specs=tuple(specs),
        erase_source_handles=r.target_handles if r.source_disposition is SourceDisposition.REPLACE else (),
        dry_run=r.dry_run,
    )


class DirectionOperation(StrEnum):
    REVERSE = "reverse"
    ANNOTATE = "annotate"


class DirectionLineRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str
    target_handles: tuple[str, ...] = Field(min_length=1)
    operation: DirectionOperation
    arrow_fraction: float = Field(default=0.5, ge=0, le=1)
    arrow_size: float = Field(gt=0)
    layer: str
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def val(self):
        _approval(self.dry_run, self.approval, "DRL")
        return self


class DirectionLinePlan(Batch13Plan):
    command_alias: str = "DRL"
    legacy_symbol: str = "xiDirectionLine"
    reversed_vertices: dict[str, tuple[Point3D, ...]]
    arrow_specs: dict[str, tuple[float, float, str]]


def plan_direction_line(r: DirectionLineRequest, ps: Sequence[PolylineSnapshot]) -> DirectionLinePlan:
    by = {p.handle.casefold(): p for p in ps}
    rev = {}
    arrows = {}
    for h in r.target_handles:
        p = by.get(h.casefold())
        if p is None or p.is_xref or p.locked_layer:
            raise ValueError(f"DRL line unavailable: {h}")
        if r.operation is DirectionOperation.REVERSE:
            rev[p.handle] = tuple(reversed(p.vertices))
        else:
            arrows[p.handle] = (r.arrow_fraction, r.arrow_size, r.layer)
    return DirectionLinePlan(document_id=r.document_id, reversed_vertices=rev, arrow_specs=arrows, dry_run=r.dry_run)


class JumpSide(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    ALTERNATE = "alternate"


class JumpRepresentation(StrEnum):
    ARC = "arc"
    BREAK = "break"


class JumpLineRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str
    base_handle: str
    crossing_points: tuple[Point3D, ...] = Field(min_length=1)
    radius: float = Field(gt=0)
    side: JumpSide
    representation: JumpRepresentation
    layer: str
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def val(self):
        _approval(self.dry_run, self.approval, "JUL")
        return self


class JumpSpec(BaseModel):
    crossing_point: Point3D
    radius: float
    side: JumpSide
    representation: JumpRepresentation
    layer: str


class JumpLinePlan(Batch13Plan):
    command_alias: str = "JUL"
    legacy_symbol: str = "xiJumpD"
    base_handle: str
    jumps: tuple[JumpSpec, ...]


def plan_jump_line(r: JumpLineRequest, ps: Sequence[PolylineSnapshot]) -> JumpLinePlan:
    p = next((p for p in ps if p.handle.casefold() == r.base_handle.casefold()), None)
    if p is None or p.is_xref or p.locked_layer:
        raise ValueError("JUL base unavailable")
    jumps = tuple(
        JumpSpec(
            crossing_point=point,
            radius=r.radius,
            side=(
                JumpSide.LEFT
                if r.side is JumpSide.ALTERNATE and i % 2 == 0
                else JumpSide.RIGHT
                if r.side is JumpSide.ALTERNATE
                else r.side
            ),
            representation=r.representation,
            layer=r.layer,
        )
        for i, point in enumerate(r.crossing_points)
    )
    return JumpLinePlan(document_id=r.document_id, base_handle=p.handle, jumps=jumps, dry_run=r.dry_run)


def register_headless_core_batch13_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    ro = ToolAnnotations(
        title="xiCAD Headless Core Batch 13 Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    def reg(name):
        return lambda f: mcp.tool(name=name, annotations=ro)(f)

    @reg("xicad_plan_lx")
    def a(r: AutoLeaderRequest) -> AutoLeaderPlan:
        return plan_auto_leader(r)

    @reg("xicad_plan_sd")
    def b(r: SplitDimensionRequest, d: tuple[DimensionSnapshot, ...]) -> SplitDimensionPlan:
        return plan_split_dimension(r, d)

    @reg("xicad_plan_tl")
    def c(r: TextToLeaderRequest, e: tuple[TextEntitySnapshot, ...]) -> TextToLeaderPlan:
        return plan_text_to_leader(r, e)

    @reg("xicad_plan_2dp")
    def d(r: ProjectionRequest, g: tuple[PolylineSnapshot, ...]) -> ProjectionPlan:
        return plan_projection(r, g)

    @reg("xicad_plan_3tp")
    def e(r: Polyline3DConvertRequest, p: tuple[PolylineSnapshot, ...]) -> Polyline3DConvertPlan:
        return plan_3dpoly_to_lwpoly(r, p)

    @reg("xicad_plan_boo")
    def f(r: JoinPolylineRequest, p: tuple[PolylineSnapshot, ...]) -> JoinPolylinePlan:
        return plan_join_polylines(r, p)

    @reg("xicad_plan_bs")
    def g(r: BreakSymbolRequest) -> BreakSymbolPlan:
        return plan_break_symbol(r)

    @reg("xicad_plan_cbj")
    def h(r: ContourJoinRequest, p: tuple[PolylineSnapshot, ...]) -> ContourJoinPlan:
        return plan_contour_join(r, p)

    @reg("xicad_plan_cm")
    def i(r: RevisionCloudRequest) -> RevisionCloudPlan:
        return plan_revision_cloud(r)

    @reg("xicad_plan_cmw")
    def j(r: CloudWidthRequest, p: tuple[PolylineSnapshot, ...]) -> CloudWidthPlan:
        return plan_cloud_width(r, p)

    @reg("xicad_plan_drl")
    def k(r: DirectionLineRequest, p: tuple[PolylineSnapshot, ...]) -> DirectionLinePlan:
        return plan_direction_line(r, p)

    @reg("xicad_plan_jul")
    def plan_jul_tool(r: JumpLineRequest, p: tuple[PolylineSnapshot, ...]) -> JumpLinePlan:
        return plan_jump_line(r, p)
