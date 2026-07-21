from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import atan2, degrees, hypot, isfinite
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D

_EPS = 1e-9


def _require_document(adapter: Any, document_id: str) -> None:
    active = adapter.active_document_id()
    if active != document_id:
        raise ValueError(f"active document mismatch: expected {document_id}, got {active}")


def _distance(a: Point3D, b: Point3D) -> float:
    return hypot(b.x - a.x, b.y - a.y)


def _unit(a: Point3D, b: Point3D) -> tuple[float, float]:
    length = _distance(a, b)
    if length <= _EPS:
        raise ValueError("geometry requires two distinct points")
    return ((b.x - a.x) / length, (b.y - a.y) / length)


def _point_at(a: Point3D, b: Point3D, ratio: float) -> Point3D:
    return Point3D(
        x=a.x + (b.x - a.x) * ratio,
        y=a.y + (b.y - a.y) * ratio,
        z=a.z + (b.z - a.z) * ratio,
    )


def _cross_distance(origin: Point3D, ux: float, uy: float, point: Point3D) -> float:
    # absolute 2D perpendicular distance to the line through origin
    return abs((point.x - origin.x) * (-uy) + (point.y - origin.y) * ux)


class SourcePolicy(StrEnum):
    PRESERVE = "preserve"
    REPLACE = "replace"


# ---------------------------------------------------------------------------
# DTD / xiDimTxOverRideSep
# Conservative deterministic replacement: the caller supplies the exact
# annotation text, replacement dimension override, and insertion geometry.
# ---------------------------------------------------------------------------


class DimensionTextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    current_override: str
    layer: str = Field(min_length=1)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)


class DimensionOverrideDetachItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dimension_handle: str = Field(min_length=1)
    expected_current_override: str
    replacement_override: str
    detached_text: str = Field(min_length=1)
    insertion_point: Point3D
    rotation_degrees: float = 0.0
    output_layer: str | None = None
    output_text_style: str | None = None
    output_text_height: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_finite(self) -> DimensionOverrideDetachItem:
        if not isfinite(self.rotation_degrees):
            raise ValueError("rotation_degrees must be finite")
        return self


class DimensionOverrideDetachRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    items: tuple[DimensionOverrideDetachItem, ...] = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DimensionOverrideDetachRequest:
        handles = [item.dimension_handle.casefold() for item in self.items]
        if len(handles) != len(set(handles)):
            raise ValueError("dimension handles must be unique")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("DTD execution requires explicit approval")
        return self


class DetachedTextSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    insertion_point: Point3D
    rotation_degrees: float
    layer: str
    text_style: str
    text_height: float


class DimensionOverrideDetachOperation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dimension_handle: str
    expected_current_override: str
    replacement_override: str
    detached_text: DetachedTextSpec


class DimensionOverrideDetachPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "DTD"
    legacy_symbol: str = "xiDimTxOverRideSep"
    document_id: str
    operations: tuple[DimensionOverrideDetachOperation, ...]
    destructive: bool = True
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class DimensionOverrideDetachResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: DimensionOverrideDetachPlan
    created_text_handles: tuple[str, ...]
    changed_dimension_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool


class DimensionOverrideDetachAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def read_dimensions(self, handles: Sequence[str]) -> Sequence[DimensionTextSnapshot]: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def set_dimension_override(self, handle: str, value: str) -> None: ...
    def create_text(self, spec: DetachedTextSpec) -> str: ...


def plan_dimension_override_detach(
    request: DimensionOverrideDetachRequest,
    dimensions: Sequence[DimensionTextSnapshot],
) -> DimensionOverrideDetachPlan:
    by_handle = {item.handle.casefold(): item for item in dimensions}
    operations: list[DimensionOverrideDetachOperation] = []
    for item in request.items:
        snapshot = by_handle.get(item.dimension_handle.casefold())
        if snapshot is None:
            raise ValueError(f"dimension not found: {item.dimension_handle}")
        if snapshot.current_override != item.expected_current_override:
            raise ValueError(
                f"dimension override changed for {snapshot.handle}: expected "
                f"{item.expected_current_override!r}, got {snapshot.current_override!r}"
            )
        operations.append(
            DimensionOverrideDetachOperation(
                dimension_handle=snapshot.handle,
                expected_current_override=item.expected_current_override,
                replacement_override=item.replacement_override,
                detached_text=DetachedTextSpec(
                    text=item.detached_text,
                    insertion_point=item.insertion_point,
                    rotation_degrees=item.rotation_degrees,
                    layer=item.output_layer or snapshot.layer,
                    text_style=item.output_text_style or snapshot.text_style,
                    text_height=item.output_text_height or snapshot.text_height,
                ),
            )
        )
    return DimensionOverrideDetachPlan(
        document_id=request.document_id,
        operations=tuple(operations),
        dry_run=request.dry_run,
    )


def execute_dimension_override_detach(
    request: DimensionOverrideDetachRequest,
    adapter: DimensionOverrideDetachAdapter,
) -> DimensionOverrideDetachResult:
    _require_document(adapter, request.document_id)
    handles = tuple(item.dimension_handle for item in request.items)
    dimensions = tuple(adapter.read_dimensions(handles))
    plan = plan_dimension_override_detach(request, dimensions)
    if request.dry_run:
        return DimensionOverrideDetachResult(
            plan=plan,
            created_text_handles=(),
            changed_dimension_handles=(),
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    created: list[str] = []
    changed: list[str] = []
    try:
        adapter.begin_undo_mark()
        opened = True
        for op in plan.operations:
            adapter.set_dimension_override(op.dimension_handle, op.replacement_override)
            changed.append(op.dimension_handle)
            created.append(adapter.create_text(op.detached_text))
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return DimensionOverrideDetachResult(
        plan=plan,
        created_text_handles=tuple(created),
        changed_dimension_handles=tuple(changed),
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


# ---------------------------------------------------------------------------
# DVD / xiDivideDim and JD / xiJDims
# Shared deterministic linear-dimension geometry core.
# ---------------------------------------------------------------------------


class LinearDimensionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    extension_start: Point3D
    extension_end: Point3D
    dimension_line_point: Point3D
    style_name: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    text_override: str = ""

    @model_validator(mode="after")
    def validate_nonzero(self) -> LinearDimensionSnapshot:
        _unit(self.extension_start, self.extension_end)
        return self


class LinearDimensionSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    extension_start: Point3D
    extension_end: Point3D
    dimension_line_point: Point3D
    style_name: str
    layer: str
    text_override: str = ""


class DivideDimensionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handle: str = Field(min_length=1)
    divisions: int = Field(ge=2, le=1000)
    source_policy: SourcePolicy
    allow_source_text_override: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DivideDimensionRequest:
        if not self.dry_run and not self.approval.approved:
            raise ValueError("DVD execution requires explicit approval")
        return self


class DivideDimensionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "DVD"
    legacy_symbol: str = "xiDivideDim"
    shared_core_key: str = "linear_dimension_segments"
    document_id: str
    source_handle: str
    output_dimensions: tuple[LinearDimensionSpec, ...]
    source_policy: SourcePolicy
    destructive: bool
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class DivideDimensionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: DivideDimensionPlan
    created_handles: tuple[str, ...]
    erased_source_handle: str | None
    undo_mark_opened: bool
    undo_mark_closed: bool


class DivideDimensionAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def read_linear_dimension(self, handle: str) -> LinearDimensionSnapshot: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def create_linear_dimension(self, spec: LinearDimensionSpec) -> str: ...
    def erase_entities(self, handles: Sequence[str]) -> None: ...


def plan_divide_dimension(
    request: DivideDimensionRequest,
    source: LinearDimensionSnapshot,
) -> DivideDimensionPlan:
    if source.handle.casefold() != request.source_handle.casefold():
        raise ValueError("adapter dimension handle does not match request")
    if source.text_override and not request.allow_source_text_override:
        raise ValueError("source dimension has a text override; explicit opt-in is required")
    points = tuple(
        _point_at(source.extension_start, source.extension_end, i / request.divisions)
        for i in range(request.divisions + 1)
    )
    specs = tuple(
        LinearDimensionSpec(
            extension_start=points[i],
            extension_end=points[i + 1],
            dimension_line_point=source.dimension_line_point,
            style_name=source.style_name,
            layer=source.layer,
            text_override="",
        )
        for i in range(request.divisions)
    )
    return DivideDimensionPlan(
        document_id=request.document_id,
        source_handle=source.handle,
        output_dimensions=specs,
        source_policy=request.source_policy,
        destructive=request.source_policy is SourcePolicy.REPLACE,
        dry_run=request.dry_run,
    )


def execute_divide_dimension(
    request: DivideDimensionRequest,
    adapter: DivideDimensionAdapter,
) -> DivideDimensionResult:
    _require_document(adapter, request.document_id)
    source = adapter.read_linear_dimension(request.source_handle)
    plan = plan_divide_dimension(request, source)
    if request.dry_run:
        return DivideDimensionResult(
            plan=plan,
            created_handles=(),
            erased_source_handle=None,
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    created: list[str] = []
    erased: str | None = None
    try:
        adapter.begin_undo_mark()
        opened = True
        for spec in plan.output_dimensions:
            created.append(adapter.create_linear_dimension(spec))
        if request.source_policy is SourcePolicy.REPLACE:
            adapter.erase_entities((plan.source_handle,))
            erased = plan.source_handle
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return DivideDimensionResult(
        plan=plan,
        created_handles=tuple(created),
        erased_source_handle=erased,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


class JoinDimensionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=2)
    source_policy: SourcePolicy
    tolerance: float = Field(default=1e-6, gt=0, le=1.0)
    allow_gaps: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> JoinDimensionRequest:
        folded = [h.casefold() for h in self.source_handles]
        if len(folded) != len(set(folded)):
            raise ValueError("source_handles must be unique")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("JD execution requires explicit approval")
        return self


class JoinDimensionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "JD"
    legacy_symbol: str = "xiJDims"
    shared_core_key: str = "linear_dimension_segments"
    document_id: str
    source_handles: tuple[str, ...]
    output_dimension: LinearDimensionSpec
    source_policy: SourcePolicy
    gaps_detected: tuple[float, ...]
    destructive: bool
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class JoinDimensionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: JoinDimensionPlan
    created_handle: str | None
    erased_source_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool


class JoinDimensionAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def read_linear_dimensions(self, handles: Sequence[str]) -> Sequence[LinearDimensionSnapshot]: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def create_linear_dimension(self, spec: LinearDimensionSpec) -> str: ...
    def erase_entities(self, handles: Sequence[str]) -> None: ...


def plan_join_dimensions(
    request: JoinDimensionRequest,
    dimensions: Sequence[LinearDimensionSnapshot],
) -> JoinDimensionPlan:
    if len(dimensions) != len(request.source_handles):
        raise ValueError("adapter did not return the requested number of dimensions")
    requested = {h.casefold() for h in request.source_handles}
    returned = {d.handle.casefold() for d in dimensions}
    if requested != returned:
        raise ValueError("adapter dimension handles do not match request")

    first = dimensions[0]
    if first.text_override:
        raise ValueError("joined source dimensions must not contain text overrides")
    ux, uy = _unit(first.extension_start, first.extension_end)
    style = first.style_name
    layer = first.layer
    dim_line = first.dimension_line_point

    projected_segments: list[tuple[float, float, LinearDimensionSnapshot]] = []
    ox, oy = first.extension_start.x, first.extension_start.y
    for dim in dimensions:
        if dim.style_name != style or dim.layer != layer:
            raise ValueError("all joined dimensions must use the same style and layer")
        if dim.text_override:
            raise ValueError("joined source dimensions must not contain text overrides")
        if _cross_distance(first.extension_start, ux, uy, dim.extension_start) > request.tolerance:
            raise ValueError("dimension extension points are not collinear")
        if _cross_distance(first.extension_start, ux, uy, dim.extension_end) > request.tolerance:
            raise ValueError("dimension extension points are not collinear")
        a = (dim.extension_start.x - ox) * ux + (dim.extension_start.y - oy) * uy
        b = (dim.extension_end.x - ox) * ux + (dim.extension_end.y - oy) * uy
        projected_segments.append((min(a, b), max(a, b), dim))

    projected_segments.sort(key=lambda row: (row[0], row[1], row[2].handle.casefold()))
    gaps: list[float] = []
    current_end = projected_segments[0][1]
    for start, end, _ in projected_segments[1:]:
        gap = start - current_end
        if gap > request.tolerance:
            gaps.append(gap)
        current_end = max(current_end, end)
    if gaps and not request.allow_gaps:
        raise ValueError("dimension chain contains gaps; explicit allow_gaps is required")

    min_t = projected_segments[0][0]
    max_t = max(row[1] for row in projected_segments)
    start = Point3D(x=ox + ux * min_t, y=oy + uy * min_t, z=first.extension_start.z)
    end = Point3D(x=ox + ux * max_t, y=oy + uy * max_t, z=first.extension_end.z)
    spec = LinearDimensionSpec(
        extension_start=start,
        extension_end=end,
        dimension_line_point=dim_line,
        style_name=style,
        layer=layer,
        text_override="",
    )
    return JoinDimensionPlan(
        document_id=request.document_id,
        source_handles=tuple(row[2].handle for row in projected_segments),
        output_dimension=spec,
        source_policy=request.source_policy,
        gaps_detected=tuple(gaps),
        destructive=request.source_policy is SourcePolicy.REPLACE,
        dry_run=request.dry_run,
    )


def execute_join_dimensions(
    request: JoinDimensionRequest,
    adapter: JoinDimensionAdapter,
) -> JoinDimensionResult:
    _require_document(adapter, request.document_id)
    dimensions = tuple(adapter.read_linear_dimensions(request.source_handles))
    plan = plan_join_dimensions(request, dimensions)
    if request.dry_run:
        return JoinDimensionResult(
            plan=plan,
            created_handle=None,
            erased_source_handles=(),
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    created: str | None = None
    erased: tuple[str, ...] = ()
    try:
        adapter.begin_undo_mark()
        opened = True
        created = adapter.create_linear_dimension(plan.output_dimension)
        if request.source_policy is SourcePolicy.REPLACE:
            adapter.erase_entities(plan.source_handles)
            erased = plan.source_handles
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return JoinDimensionResult(
        plan=plan,
        created_handle=created,
        erased_source_handles=erased,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


# ---------------------------------------------------------------------------
# SCC / xiSC and SCD / xiSCD
# Shared deterministic section-mark geometry plan.
# ---------------------------------------------------------------------------


class SectionMarkMode(StrEnum):
    SINGLE = "single"
    DOUBLE = "double"


class SectionNormalSide(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class SectionMarkRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    mode: SectionMarkMode
    cut_start: Point3D
    cut_end: Point3D
    normal_side: SectionNormalSide
    label_start: str = Field(min_length=1, max_length=32)
    label_end: str = Field(min_length=1, max_length=32)
    tail_length: float = Field(gt=0)
    double_line_gap: float | None = Field(default=None, gt=0)
    text_offset: float = Field(gt=0)
    layer: str = Field(min_length=1)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SectionMarkRequest:
        _unit(self.cut_start, self.cut_end)
        if self.mode is SectionMarkMode.DOUBLE and self.double_line_gap is None:
            raise ValueError("SCD double-line mode requires double_line_gap")
        if self.mode is SectionMarkMode.SINGLE and self.double_line_gap is not None:
            raise ValueError("SCC single-line mode must not set double_line_gap")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("section-mark execution requires explicit approval")
        return self


class LineSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    start: Point3D
    end: Point3D
    layer: str


class TextSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    insertion_point: Point3D
    rotation_degrees: float
    layer: str
    text_style: str
    text_height: float


class SectionMarkPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    shared_core_key: str = "section_mark"
    document_id: str
    mode: SectionMarkMode
    cut_lines: tuple[LineSpec, ...]
    tail_lines: tuple[LineSpec, ...]
    labels: tuple[TextSpec, ...]
    destructive: bool = False
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class SectionMarkResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: SectionMarkPlan
    created_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool


class SectionMarkAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def create_lines(self, specs: Sequence[LineSpec]) -> Sequence[str]: ...
    def create_texts(self, specs: Sequence[TextSpec]) -> Sequence[str]: ...


def _offset_point(point: Point3D, nx: float, ny: float, distance: float) -> Point3D:
    return Point3D(x=point.x + nx * distance, y=point.y + ny * distance, z=point.z)


def plan_section_mark(request: SectionMarkRequest) -> SectionMarkPlan:
    ux, uy = _unit(request.cut_start, request.cut_end)
    # left normal = (-uy, ux); reverse for right
    sign = 1.0 if request.normal_side is SectionNormalSide.LEFT else -1.0
    nx, ny = -uy * sign, ux * sign
    rotation = degrees(atan2(uy, ux))

    cut_lines: list[LineSpec] = [LineSpec(start=request.cut_start, end=request.cut_end, layer=request.layer)]
    if request.mode is SectionMarkMode.DOUBLE:
        assert request.double_line_gap is not None
        cut_lines.append(
            LineSpec(
                start=_offset_point(request.cut_start, nx, ny, request.double_line_gap),
                end=_offset_point(request.cut_end, nx, ny, request.double_line_gap),
                layer=request.layer,
            )
        )

    start_tail_end = _offset_point(request.cut_start, nx, ny, request.tail_length)
    end_tail_end = _offset_point(request.cut_end, nx, ny, request.tail_length)
    tails = (
        LineSpec(start=request.cut_start, end=start_tail_end, layer=request.layer),
        LineSpec(start=request.cut_end, end=end_tail_end, layer=request.layer),
    )
    labels = (
        TextSpec(
            text=request.label_start,
            insertion_point=_offset_point(start_tail_end, nx, ny, request.text_offset),
            rotation_degrees=rotation,
            layer=request.layer,
            text_style=request.text_style,
            text_height=request.text_height,
        ),
        TextSpec(
            text=request.label_end,
            insertion_point=_offset_point(end_tail_end, nx, ny, request.text_offset),
            rotation_degrees=rotation,
            layer=request.layer,
            text_style=request.text_style,
            text_height=request.text_height,
        ),
    )
    alias = "SCC" if request.mode is SectionMarkMode.SINGLE else "SCD"
    symbol = "xiSC" if request.mode is SectionMarkMode.SINGLE else "xiSCD"
    return SectionMarkPlan(
        command_alias=alias,
        legacy_symbol=symbol,
        document_id=request.document_id,
        mode=request.mode,
        cut_lines=tuple(cut_lines),
        tail_lines=tails,
        labels=labels,
        dry_run=request.dry_run,
    )


def execute_section_mark(
    request: SectionMarkRequest,
    adapter: SectionMarkAdapter,
) -> SectionMarkResult:
    _require_document(adapter, request.document_id)
    plan = plan_section_mark(request)
    if request.dry_run:
        return SectionMarkResult(
            plan=plan,
            created_handles=(),
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    created: list[str] = []
    try:
        adapter.begin_undo_mark()
        opened = True
        created.extend(adapter.create_lines((*plan.cut_lines, *plan.tail_lines)))
        created.extend(adapter.create_texts(plan.labels))
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return SectionMarkResult(
        plan=plan,
        created_handles=tuple(created),
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


# ---------------------------------------------------------------------------
# TBM / xiTBstyleMK
# Deterministic XI_TB_N table-style contract. No property is silently inferred.
# ---------------------------------------------------------------------------


class ExistingStylePolicy(StrEnum):
    ERROR = "error"
    KEEP = "keep"
    UPDATE = "update"


class TableStyleSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    style_name: str = Field(default="XI_TB_N", min_length=1, max_length=255)
    title_text_style: str = Field(min_length=1)
    header_text_style: str = Field(min_length=1)
    data_text_style: str = Field(min_length=1)
    title_text_height: float = Field(gt=0)
    header_text_height: float = Field(gt=0)
    data_text_height: float = Field(gt=0)
    horizontal_cell_margin: float = Field(ge=0)
    vertical_cell_margin: float = Field(ge=0)
    flow_direction: str = Field(pattern="^(down|up)$")


class TableStyleSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    exists: bool
    spec: TableStyleSpec | None = None

    @model_validator(mode="after")
    def validate_snapshot(self) -> TableStyleSnapshot:
        if self.exists and self.spec is None:
            raise ValueError("existing table style requires a spec")
        if not self.exists and self.spec is not None:
            raise ValueError("missing table style must not contain a spec")
        return self


class TableStyleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    desired: TableStyleSpec
    existing_policy: ExistingStylePolicy
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TableStyleRequest:
        if not self.dry_run and not self.approval.approved:
            raise ValueError("TBM execution requires explicit approval")
        return self


class TableStyleAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    KEEP = "keep"
    NOOP = "noop"


class TableStylePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "TBM"
    legacy_symbol: str = "xiTBstyleMK"
    document_id: str
    desired: TableStyleSpec
    existing: TableStyleSnapshot
    action: TableStyleAction
    destructive: bool
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class TableStyleResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: TableStylePlan
    changed: bool
    undo_mark_opened: bool
    undo_mark_closed: bool


class TableStyleAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def read_table_style(self, style_name: str) -> TableStyleSnapshot: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def create_table_style(self, spec: TableStyleSpec) -> None: ...
    def update_table_style(self, spec: TableStyleSpec) -> None: ...


def plan_table_style(
    request: TableStyleRequest,
    existing: TableStyleSnapshot,
) -> TableStylePlan:
    if not existing.exists:
        action = TableStyleAction.CREATE
    elif existing.spec == request.desired:
        action = TableStyleAction.NOOP
    elif request.existing_policy is ExistingStylePolicy.ERROR:
        raise ValueError(f"table style already exists with different settings: {request.desired.style_name}")
    elif request.existing_policy is ExistingStylePolicy.KEEP:
        action = TableStyleAction.KEEP
    else:
        action = TableStyleAction.UPDATE
    return TableStylePlan(
        document_id=request.document_id,
        desired=request.desired,
        existing=existing,
        action=action,
        destructive=action is TableStyleAction.UPDATE,
        dry_run=request.dry_run,
    )


def execute_table_style(
    request: TableStyleRequest,
    adapter: TableStyleAdapter,
) -> TableStyleResult:
    _require_document(adapter, request.document_id)
    existing = adapter.read_table_style(request.desired.style_name)
    plan = plan_table_style(request, existing)
    if request.dry_run or plan.action in {TableStyleAction.NOOP, TableStyleAction.KEEP}:
        return TableStyleResult(
            plan=plan,
            changed=False,
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    try:
        adapter.begin_undo_mark()
        opened = True
        if plan.action is TableStyleAction.CREATE:
            adapter.create_table_style(plan.desired)
        elif plan.action is TableStyleAction.UPDATE:
            adapter.update_table_style(plan.desired)
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return TableStyleResult(
        plan=plan,
        changed=True,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


def register_headless_core_batch2_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Headless Core Batch 2",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="xicad_plan_dimension_override_detach",
        description="Build a dialog-free DTD plan from explicit dimension snapshots and detached annotation text. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_dimension_override_detach(
        request: DimensionOverrideDetachRequest,
        dimensions: list[DimensionTextSnapshot],
    ) -> DimensionOverrideDetachPlan:
        return plan_dimension_override_detach(request, dimensions)

    @mcp.tool(
        name="xicad_plan_divide_dimension",
        description="Build a dialog-free DVD linear-dimension division plan. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_divide_dimension(
        request: DivideDimensionRequest,
        source: LinearDimensionSnapshot,
    ) -> DivideDimensionPlan:
        return plan_divide_dimension(request, source)

    @mcp.tool(
        name="xicad_plan_join_dimensions",
        description="Build a dialog-free JD collinear dimension-chain join plan. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_join_dimensions(
        request: JoinDimensionRequest,
        dimensions: list[LinearDimensionSnapshot],
    ) -> JoinDimensionPlan:
        return plan_join_dimensions(request, dimensions)

    @mcp.tool(
        name="xicad_plan_section_mark",
        description="Build a shared SCC/SCD section-mark geometry plan from explicit points and style inputs. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_section_mark(request: SectionMarkRequest) -> SectionMarkPlan:
        return plan_section_mark(request)

    @mcp.tool(
        name="xicad_plan_table_style",
        description="Build a deterministic TBM XI_TB_N table-style create/update plan. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_table_style(
        request: TableStyleRequest,
        existing: TableStyleSnapshot,
    ) -> TableStylePlan:
        return plan_table_style(request, existing)
