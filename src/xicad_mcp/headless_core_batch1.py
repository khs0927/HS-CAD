from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from math import isfinite
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DrawingSpace(StrEnum):
    MODEL = "model"
    PAPER = "paper"


class Approval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    approved: bool = False
    fingerprint: str | None = None

    @model_validator(mode="after")
    def validate_approval(self) -> Approval:
        if self.approved and not self.fingerprint:
            raise ValueError("approved mutations require an approval fingerprint")
        return self


class Point3D(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    x: float
    y: float
    z: float = 0.0

    @model_validator(mode="after")
    def validate_finite(self) -> Point3D:
        if not all(isfinite(v) for v in (self.x, self.y, self.z)):
            raise ValueError("point coordinates must be finite")
        return self


# ---------------------------------------------------------------------------
# * / xiMultiplication
# ---------------------------------------------------------------------------


class MultiplicationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    operands: tuple[Decimal, ...] = Field(min_length=2)
    decimal_places: int | None = Field(default=None, ge=0, le=12)


class MultiplicationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "*"
    legacy_symbol: str = "xiMultiplication"
    operands: tuple[Decimal, ...]
    exact_product: Decimal
    result: Decimal
    deterministic: bool = True
    cad_required: bool = False
    dialog_required: bool = False
    production_usable: bool = False


def multiply_numbers(request: MultiplicationRequest) -> MultiplicationResult:
    product = Decimal(1)
    for operand in request.operands:
        product *= operand
    result = product
    if request.decimal_places is not None:
        quantum = Decimal(1).scaleb(-request.decimal_places)
        result = product.quantize(quantum, rounding=ROUND_HALF_UP)
    return MultiplicationResult(
        operands=request.operands,
        exact_product=product,
        result=result,
    )


# ---------------------------------------------------------------------------
# CP / xiCP -> deterministic arc-to-circle replacement
# Current xiCAD semantic candidate: ATC / xiArcToCircle
# ---------------------------------------------------------------------------


class SourcePolicy(StrEnum):
    PRESERVE = "preserve"
    REPLACE = "replace"


class ArcGeometry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    center: Point3D
    radius: float = Field(gt=0)
    normal: Point3D = Point3D(x=0.0, y=0.0, z=1.0)
    layer: str = Field(min_length=1)


class CircleGeometry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    center: Point3D
    radius: float = Field(gt=0)
    normal: Point3D
    layer: str


class ArcToCircleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    arc_handle: str = Field(min_length=1)
    source_policy: SourcePolicy
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_execution(self) -> ArcToCircleRequest:
        if not self.dry_run and not self.approval.approved:
            raise ValueError("CP execution requires explicit approval")
        return self


class ArcToCirclePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "CP"
    legacy_symbol: str = "xiCP"
    current_semantic_candidate_alias: str = "ATC"
    current_semantic_candidate_symbol: str = "xiArcToCircle"
    document_id: str
    source_handle: str
    output: CircleGeometry
    source_policy: SourcePolicy
    destructive: bool
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class ArcToCircleResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: ArcToCirclePlan
    created_handle: str | None
    erased_source_handle: str | None
    undo_mark_opened: bool
    undo_mark_closed: bool


class ArcToCircleAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def read_arc(self, handle: str) -> ArcGeometry: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def create_circle(self, geometry: CircleGeometry) -> str: ...
    def erase_entities(self, handles: Sequence[str]) -> None: ...


def _require_document(adapter: Any, document_id: str) -> None:
    active = adapter.active_document_id()
    if active != document_id:
        raise ValueError(f"active document mismatch: expected {document_id}, got {active}")


def plan_arc_to_circle(request: ArcToCircleRequest, arc: ArcGeometry) -> ArcToCirclePlan:
    if arc.handle != request.arc_handle:
        raise ValueError("adapter arc handle does not match request")
    circle = CircleGeometry(
        center=arc.center,
        radius=arc.radius,
        normal=arc.normal,
        layer=arc.layer,
    )
    return ArcToCirclePlan(
        document_id=request.document_id,
        source_handle=arc.handle,
        output=circle,
        source_policy=request.source_policy,
        destructive=request.source_policy is SourcePolicy.REPLACE,
        dry_run=request.dry_run,
    )


def execute_arc_to_circle(request: ArcToCircleRequest, adapter: ArcToCircleAdapter) -> ArcToCircleResult:
    _require_document(adapter, request.document_id)
    arc = adapter.read_arc(request.arc_handle)
    plan = plan_arc_to_circle(request, arc)
    if request.dry_run:
        return ArcToCircleResult(
            plan=plan,
            created_handle=None,
            erased_source_handle=None,
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    created: str | None = None
    erased: str | None = None
    try:
        adapter.begin_undo_mark()
        opened = True
        created = adapter.create_circle(plan.output)
        if request.source_policy is SourcePolicy.REPLACE:
            adapter.erase_entities((request.arc_handle,))
            erased = request.arc_handle
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return ArcToCircleResult(
        plan=plan,
        created_handle=created,
        erased_source_handle=erased,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


# ---------------------------------------------------------------------------
# RC / xiRC -> deterministic rotate-copy replacement
# Current xiCAD semantic candidate: CR / xiCopyRotate
# ---------------------------------------------------------------------------


class RotateCopyRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=1)
    base_point: Point3D
    angle_degrees: float
    copies: int = Field(default=1, ge=1, le=100)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> RotateCopyRequest:
        if not isfinite(self.angle_degrees):
            raise ValueError("angle_degrees must be finite")
        if len(set(self.source_handles)) != len(self.source_handles):
            raise ValueError("source_handles must be unique")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("RC execution requires explicit approval")
        return self


class RotateCopyPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "RC"
    legacy_symbol: str = "xiRC"
    current_semantic_candidate_alias: str = "CR"
    current_semantic_candidate_symbol: str = "xiCopyRotate"
    document_id: str
    source_handles: tuple[str, ...]
    base_point: Point3D
    angle_degrees: float
    copies: int
    preserve_originals: bool = True
    destructive: bool = False
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class RotateCopyResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: RotateCopyPlan
    created_handle_groups: tuple[tuple[str, ...], ...]
    undo_mark_opened: bool
    undo_mark_closed: bool


class RotateCopyAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def validate_entity_handles(self, handles: Sequence[str]) -> None: ...
    def clone_entities(self, handles: Sequence[str]) -> Sequence[str]: ...
    def rotate_entities(self, handles: Sequence[str], base_point: Point3D, angle_degrees: float) -> None: ...


def plan_rotate_copy(request: RotateCopyRequest) -> RotateCopyPlan:
    return RotateCopyPlan(
        document_id=request.document_id,
        source_handles=request.source_handles,
        base_point=request.base_point,
        angle_degrees=request.angle_degrees,
        copies=request.copies,
        dry_run=request.dry_run,
    )


def execute_rotate_copy(request: RotateCopyRequest, adapter: RotateCopyAdapter) -> RotateCopyResult:
    _require_document(adapter, request.document_id)
    adapter.validate_entity_handles(request.source_handles)
    plan = plan_rotate_copy(request)
    if request.dry_run:
        return RotateCopyResult(
            plan=plan,
            created_handle_groups=(),
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    groups: list[tuple[str, ...]] = []
    try:
        adapter.begin_undo_mark()
        opened = True
        for index in range(1, request.copies + 1):
            cloned = tuple(adapter.clone_entities(request.source_handles))
            if len(cloned) != len(request.source_handles):
                raise ValueError("adapter clone count does not match source count")
            adapter.rotate_entities(
                cloned,
                request.base_point,
                request.angle_degrees * index,
            )
            groups.append(cloned)
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return RotateCopyResult(
        plan=plan,
        created_handle_groups=tuple(groups),
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


# ---------------------------------------------------------------------------
# LPP / LPS -> shared layer-name affix core
# ---------------------------------------------------------------------------


class LayerAffixMode(StrEnum):
    PREFIX = "prefix"
    SUFFIX = "suffix"


class LayerNameRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    system: bool = False
    xref_dependent: bool = False


class LayerAffixRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    mode: LayerAffixMode
    affix: str = Field(min_length=1, max_length=128)
    target_names: tuple[str, ...] = Field(min_length=1)
    preserve_names: tuple[str, ...] = ("0", "Defpoints")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LayerAffixRequest:
        invalid = set('<>/\\":;?*|,=`')
        if any(ch in invalid for ch in self.affix):
            raise ValueError("affix contains characters invalid in CAD layer names")
        if len({name.casefold() for name in self.target_names}) != len(self.target_names):
            raise ValueError("target_names must be case-insensitively unique")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("layer rename execution requires explicit approval")
        return self


class LayerRenamePair(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source: str
    target: str


class LayerAffixPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    shared_core_key: str = "layer_name_affix"
    document_id: str
    mode: LayerAffixMode
    affix: str
    rename_pairs: tuple[LayerRenamePair, ...]
    skipped_names: tuple[str, ...]
    destructive: bool = True
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class LayerAffixResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: LayerAffixPlan
    renamed_pairs: tuple[LayerRenamePair, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool


class LayerAffixAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def list_layers(self) -> Sequence[LayerNameRef]: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def rename_layers(self, rename_map: dict[str, str]) -> None: ...


def plan_layer_affix(request: LayerAffixRequest, layers: Sequence[LayerNameRef]) -> LayerAffixPlan:
    by_name = {item.name.casefold(): item for item in layers}
    preserve = {name.casefold() for name in request.preserve_names}
    existing = set(by_name)
    targets_seen: set[str] = set()
    pairs: list[LayerRenamePair] = []
    skipped: list[str] = []

    for requested_name in request.target_names:
        item = by_name.get(requested_name.casefold())
        if item is None:
            raise ValueError(f"layer not found: {requested_name}")
        if item.system or item.xref_dependent or item.name.casefold() in preserve:
            skipped.append(item.name)
            continue
        target = (
            f"{request.affix}{item.name}" if request.mode is LayerAffixMode.PREFIX else f"{item.name}{request.affix}"
        )
        if len(target) > 255:
            raise ValueError(f"resulting layer name is too long: {target}")
        target_key = target.casefold()
        if target_key in existing and target_key != item.name.casefold():
            raise ValueError(f"layer rename collision: {item.name} -> {target}")
        if target_key in targets_seen:
            raise ValueError(f"multiple source layers map to the same target: {target}")
        targets_seen.add(target_key)
        pairs.append(LayerRenamePair(source=item.name, target=target))

    alias = "LPP" if request.mode is LayerAffixMode.PREFIX else "LPS"
    symbol = "xiLayerPrefix" if request.mode is LayerAffixMode.PREFIX else "xiLayerSuffix"
    return LayerAffixPlan(
        command_alias=alias,
        legacy_symbol=symbol,
        document_id=request.document_id,
        mode=request.mode,
        affix=request.affix,
        rename_pairs=tuple(pairs),
        skipped_names=tuple(sorted(set(skipped), key=str.casefold)),
        dry_run=request.dry_run,
    )


def execute_layer_affix(request: LayerAffixRequest, adapter: LayerAffixAdapter) -> LayerAffixResult:
    _require_document(adapter, request.document_id)
    plan = plan_layer_affix(request, adapter.list_layers())
    if request.dry_run or not plan.rename_pairs:
        return LayerAffixResult(
            plan=plan,
            renamed_pairs=(),
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    try:
        adapter.begin_undo_mark()
        opened = True
        adapter.rename_layers({p.source: p.target for p in plan.rename_pairs})
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return LayerAffixResult(
        plan=plan,
        renamed_pairs=plan.rename_pairs,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


# ---------------------------------------------------------------------------
# TCT / xiTextCount -> deterministic text grouping and optional drawing write
# ---------------------------------------------------------------------------


class TextGrouping(StrEnum):
    EXACT = "exact"
    TRIM = "trim"
    CASEFOLD = "casefold"
    TRIM_CASEFOLD = "trim_casefold"


class TextRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    text: str
    space: DrawingSpace = DrawingSpace.MODEL


class TextCountRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = ()
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL,)
    grouping: TextGrouping = TextGrouping.EXACT
    include_empty: bool = False
    write_summary: bool = False
    insertion_point: Point3D | None = None
    output_layer: str | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextCountRequest:
        if not self.spaces:
            raise ValueError("at least one drawing space is required")
        if self.write_summary and self.insertion_point is None:
            raise ValueError("write_summary requires insertion_point")
        if not self.dry_run and self.write_summary and not self.approval.approved:
            raise ValueError("TCT drawing write requires explicit approval")
        return self


class TextCountRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    value: str
    count: int = Field(ge=1)
    handles: tuple[str, ...]


class TextCountPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "TCT"
    legacy_symbol: str = "xiTextCount"
    document_id: str
    grouping: TextGrouping
    records: tuple[TextCountRecord, ...]
    total_entities: int
    distinct_values: int
    write_summary: bool
    insertion_point: Point3D | None
    output_layer: str | None
    destructive: bool = False
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class TextCountResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: TextCountPlan
    created_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool


class TextCountAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def list_text_entities(self, handles: Sequence[str], spaces: Sequence[DrawingSpace]) -> Sequence[TextRef]: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def create_text_count_summary(
        self,
        records: Sequence[TextCountRecord],
        insertion_point: Point3D,
        output_layer: str | None,
    ) -> Sequence[str]: ...


def _normalize_text(value: str, grouping: TextGrouping) -> str:
    if grouping is TextGrouping.TRIM:
        return value.strip()
    if grouping is TextGrouping.CASEFOLD:
        return value.casefold()
    if grouping is TextGrouping.TRIM_CASEFOLD:
        return value.strip().casefold()
    return value


def plan_text_count(request: TextCountRequest, texts: Sequence[TextRef]) -> TextCountPlan:
    allowed_handles = set(request.source_handles)
    allowed_spaces = set(request.spaces)
    grouped: dict[str, list[str]] = {}
    for item in texts:
        if allowed_handles and item.handle not in allowed_handles:
            continue
        if item.space not in allowed_spaces:
            continue
        key = _normalize_text(item.text, request.grouping)
        if not request.include_empty and key == "":
            continue
        grouped.setdefault(key, []).append(item.handle)
    records = tuple(
        TextCountRecord(value=value, count=len(handles), handles=tuple(sorted(handles)))
        for value, handles in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    )
    return TextCountPlan(
        document_id=request.document_id,
        grouping=request.grouping,
        records=records,
        total_entities=sum(record.count for record in records),
        distinct_values=len(records),
        write_summary=request.write_summary,
        insertion_point=request.insertion_point,
        output_layer=request.output_layer,
        dry_run=request.dry_run,
    )


def execute_text_count(request: TextCountRequest, adapter: TextCountAdapter) -> TextCountResult:
    _require_document(adapter, request.document_id)
    texts = tuple(adapter.list_text_entities(request.source_handles, request.spaces))
    plan = plan_text_count(request, texts)
    if request.dry_run or not request.write_summary or not plan.records:
        return TextCountResult(
            plan=plan,
            created_handles=(),
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    assert request.insertion_point is not None
    opened = False
    closed = False
    created: tuple[str, ...] = ()
    try:
        adapter.begin_undo_mark()
        opened = True
        created = tuple(
            adapter.create_text_count_summary(
                plan.records,
                request.insertion_point,
                request.output_layer,
            )
        )
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return TextCountResult(
        plan=plan,
        created_handles=created,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


def register_headless_core_batch1_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Headless Core Batch 1",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="xicad_multiply_numbers",
        description="Compute the deterministic replacement for legacy * / xiMultiplication without CAD or a dialog.",
        annotations=read_only,
    )
    def mcp_multiply_numbers(request: MultiplicationRequest) -> MultiplicationResult:
        return multiply_numbers(request)

    @mcp.tool(
        name="xicad_plan_arc_to_circle",
        description="Build a CP arc-to-circle plan from explicit arc geometry. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_arc_to_circle(request: ArcToCircleRequest, arc: ArcGeometry) -> ArcToCirclePlan:
        return plan_arc_to_circle(request, arc)

    @mcp.tool(
        name="xicad_plan_rotate_copy",
        description="Build a dialog-free RC rotate-copy plan. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_rotate_copy(request: RotateCopyRequest) -> RotateCopyPlan:
        return plan_rotate_copy(request)

    @mcp.tool(
        name="xicad_plan_layer_affix",
        description="Build a shared LPP/LPS layer prefix or suffix rename plan from an explicit layer inventory. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_layer_affix(request: LayerAffixRequest, layers: list[LayerNameRef]) -> LayerAffixPlan:
        return plan_layer_affix(request, layers)

    @mcp.tool(
        name="xicad_compute_text_count",
        description="Compute the deterministic TCT text-count plan from explicit text entities. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_compute_text_count(request: TextCountRequest, texts: list[TextRef]) -> TextCountPlan:
        return plan_text_count(request, texts)
