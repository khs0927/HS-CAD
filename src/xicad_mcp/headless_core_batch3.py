from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import cos, isfinite, radians, sin
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch2 import LineSpec


def _require_document(adapter: Any, document_id: str) -> None:
    active = adapter.active_document_id()
    if active != document_id:
        raise ValueError(f"active document mismatch: expected {document_id}, got {active}")


def _unique_casefold(values: Sequence[str], field: str) -> None:
    folded = [v.casefold() for v in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{field} must be case-insensitively unique")


# ---------------------------------------------------------------------------
# BAR / xiABLRo
# Explicit adapter contract: rotate non-attribute block geometry while the
# caller chooses how attribute world transforms are preserved.
# ---------------------------------------------------------------------------


class RotationMode(StrEnum):
    DELTA = "delta"
    ABSOLUTE = "absolute"


class AttributePreservation(StrEnum):
    WORLD_POSITION_AND_ROTATION = "world_position_and_rotation"
    WORLD_ROTATION_ONLY = "world_rotation_only"
    FOLLOW_BLOCK = "follow_block"


class AttributeBlockSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    block_name: str = Field(min_length=1)
    current_rotation_degrees: float
    attribute_handles: tuple[str, ...]
    non_attribute_entity_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_snapshot(self) -> AttributeBlockSnapshot:
        if not isfinite(self.current_rotation_degrees):
            raise ValueError("current_rotation_degrees must be finite")
        _unique_casefold(self.attribute_handles, "attribute_handles")
        return self


class AttributeBlockRotateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    block_handles: tuple[str, ...] = Field(min_length=1)
    rotation_mode: RotationMode
    angle_degrees: float
    attribute_preservation: AttributePreservation
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> AttributeBlockRotateRequest:
        _unique_casefold(self.block_handles, "block_handles")
        if not isfinite(self.angle_degrees):
            raise ValueError("angle_degrees must be finite")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("BAR execution requires explicit approval")
        return self


class AttributeBlockRotateOperation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_handle: str
    block_name: str
    current_rotation_degrees: float
    target_rotation_degrees: float
    delta_degrees: float
    attribute_handles: tuple[str, ...]
    attribute_preservation: AttributePreservation


class AttributeBlockRotatePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "BAR"
    legacy_symbol: str = "xiABLRo"
    document_id: str
    operations: tuple[AttributeBlockRotateOperation, ...]
    destructive: bool = True
    dry_run: bool
    dialog_required: bool = False
    adapter_capability_required: str = "rotate_block_non_attribute_geometry"
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class AttributeBlockRotateResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: AttributeBlockRotatePlan
    changed_block_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool


class AttributeBlockRotateAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def read_attribute_blocks(self, handles: Sequence[str]) -> Sequence[AttributeBlockSnapshot]: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def rotate_block_non_attribute_geometry(
        self,
        block_handle: str,
        delta_degrees: float,
        attribute_preservation: AttributePreservation,
    ) -> None: ...


def plan_attribute_block_rotate(
    request: AttributeBlockRotateRequest,
    blocks: Sequence[AttributeBlockSnapshot],
) -> AttributeBlockRotatePlan:
    by_handle = {b.handle.casefold(): b for b in blocks}
    operations: list[AttributeBlockRotateOperation] = []
    for handle in request.block_handles:
        block = by_handle.get(handle.casefold())
        if block is None:
            raise ValueError(f"attribute block not found: {handle}")
        if block.non_attribute_entity_count == 0:
            raise ValueError(f"attribute block contains no non-attribute geometry: {block.handle}")
        target = (
            block.current_rotation_degrees + request.angle_degrees
            if request.rotation_mode is RotationMode.DELTA
            else request.angle_degrees
        )
        delta = target - block.current_rotation_degrees
        operations.append(
            AttributeBlockRotateOperation(
                block_handle=block.handle,
                block_name=block.block_name,
                current_rotation_degrees=block.current_rotation_degrees,
                target_rotation_degrees=target,
                delta_degrees=delta,
                attribute_handles=block.attribute_handles,
                attribute_preservation=request.attribute_preservation,
            )
        )
    return AttributeBlockRotatePlan(
        document_id=request.document_id,
        operations=tuple(operations),
        dry_run=request.dry_run,
    )


def execute_attribute_block_rotate(
    request: AttributeBlockRotateRequest,
    adapter: AttributeBlockRotateAdapter,
) -> AttributeBlockRotateResult:
    _require_document(adapter, request.document_id)
    blocks = tuple(adapter.read_attribute_blocks(request.block_handles))
    plan = plan_attribute_block_rotate(request, blocks)
    if request.dry_run:
        return AttributeBlockRotateResult(
            plan=plan,
            changed_block_handles=(),
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    changed: list[str] = []
    try:
        adapter.begin_undo_mark()
        opened = True
        for op in plan.operations:
            adapter.rotate_block_non_attribute_geometry(
                op.block_handle,
                op.delta_degrees,
                op.attribute_preservation,
            )
            changed.append(op.block_handle)
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return AttributeBlockRotateResult(
        plan=plan,
        changed_block_handles=tuple(changed),
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


# ---------------------------------------------------------------------------
# ABD / xiAllNullBlockDelete
# Conservative empty/unreferenced block-record cleanup only.
# ---------------------------------------------------------------------------


class BlockRecordSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    name: str = Field(min_length=1)
    reference_count: int = Field(ge=0)
    entity_count: int = Field(ge=0)
    is_layout: bool = False
    is_xref: bool = False
    is_dynamic_base: bool = False
    is_system: bool = False


class NullBlockCleanupRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_names: tuple[str, ...] = ()
    preserve_names: tuple[str, ...] = ("*Model_Space", "*Paper_Space")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> NullBlockCleanupRequest:
        _unique_casefold(self.target_names, "target_names")
        _unique_casefold(self.preserve_names, "preserve_names")
        if set(n.casefold() for n in self.target_names) & set(n.casefold() for n in self.preserve_names):
            raise ValueError("target_names and preserve_names overlap")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("ABD execution requires explicit approval")
        return self


class CleanupSkip(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    name: str
    reason: str


class NullBlockCleanupPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "ABD"
    legacy_symbol: str = "xiAllNullBlockDelete"
    document_id: str
    purge_handles: tuple[str, ...]
    purge_names: tuple[str, ...]
    skipped: tuple[CleanupSkip, ...]
    destructive: bool = True
    dry_run: bool
    dialog_required: bool = False
    candidate_rule: str = "empty_and_unreferenced_non_system_block_record"
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class CleanupResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: Any
    removed_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool


class NullBlockCleanupAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def list_block_records(self) -> Sequence[BlockRecordSnapshot]: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def purge_block_records(self, handles: Sequence[str]) -> Sequence[str]: ...


def plan_null_block_cleanup(
    request: NullBlockCleanupRequest,
    records: Sequence[BlockRecordSnapshot],
) -> NullBlockCleanupPlan:
    targets = {n.casefold() for n in request.target_names}
    preserve = {n.casefold() for n in request.preserve_names}
    purge: list[BlockRecordSnapshot] = []
    skipped: list[CleanupSkip] = []
    for record in records:
        if targets and record.name.casefold() not in targets:
            continue
        reason: str | None = None
        if record.name.casefold() in preserve:
            reason = "preserved_by_request"
        elif record.is_layout or record.is_xref or record.is_dynamic_base or record.is_system:
            reason = "protected_block_record"
        elif record.reference_count != 0:
            reason = "still_referenced"
        elif record.entity_count != 0:
            reason = "not_empty"
        if reason:
            skipped.append(CleanupSkip(handle=record.handle, name=record.name, reason=reason))
        else:
            purge.append(record)
    purge.sort(key=lambda r: (r.name.casefold(), r.handle))
    skipped.sort(key=lambda r: (r.name.casefold(), r.handle))
    return NullBlockCleanupPlan(
        document_id=request.document_id,
        purge_handles=tuple(r.handle for r in purge),
        purge_names=tuple(r.name for r in purge),
        skipped=tuple(skipped),
        dry_run=request.dry_run,
    )


def execute_null_block_cleanup(
    request: NullBlockCleanupRequest,
    adapter: NullBlockCleanupAdapter,
) -> CleanupResult:
    _require_document(adapter, request.document_id)
    plan = plan_null_block_cleanup(request, adapter.list_block_records())
    if request.dry_run or not plan.purge_handles:
        return CleanupResult(
            plan=plan,
            removed_handles=(),
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    removed: tuple[str, ...] = ()
    try:
        adapter.begin_undo_mark()
        opened = True
        removed = tuple(adapter.purge_block_records(plan.purge_handles))
        if set(removed) - set(plan.purge_handles):
            raise ValueError("adapter reported removal outside the approved block set")
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return CleanupResult(plan=plan, removed_handles=removed, undo_mark_opened=opened, undo_mark_closed=closed)


# ---------------------------------------------------------------------------
# AGD / xiAllGhostDelete
# The caller explicitly chooses accepted forensic classifications.
# ---------------------------------------------------------------------------


class GhostClassification(StrEnum):
    ORPHANED_OWNER = "orphaned_owner"
    ERASED_RESIDENT = "erased_resident"
    INVALID_DATABASE_OBJECT = "invalid_database_object"


class GhostObjectSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    classification: GhostClassification
    hard_reference_count: int = Field(ge=0)
    is_dictionary_entry: bool = False
    is_system_object: bool = False


class GhostCleanupRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    accepted_classifications: tuple[GhostClassification, ...] = Field(min_length=1)
    target_handles: tuple[str, ...] = ()
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> GhostCleanupRequest:
        _unique_casefold(self.target_handles, "target_handles")
        if len(set(self.accepted_classifications)) != len(self.accepted_classifications):
            raise ValueError("accepted_classifications must be unique")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("AGD execution requires explicit approval")
        return self


class GhostCleanupPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "AGD"
    legacy_symbol: str = "xiAllGhostDelete"
    document_id: str
    remove_handles: tuple[str, ...]
    skipped: tuple[CleanupSkip, ...]
    accepted_classifications: tuple[GhostClassification, ...]
    destructive: bool = True
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class GhostCleanupAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def inspect_ghost_objects(self) -> Sequence[GhostObjectSnapshot]: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def remove_database_objects(self, handles: Sequence[str]) -> Sequence[str]: ...


def plan_ghost_cleanup(
    request: GhostCleanupRequest,
    objects: Sequence[GhostObjectSnapshot],
) -> GhostCleanupPlan:
    accepted = set(request.accepted_classifications)
    targets = {h.casefold() for h in request.target_handles}
    remove: list[GhostObjectSnapshot] = []
    skipped: list[CleanupSkip] = []
    for obj in objects:
        if targets and obj.handle.casefold() not in targets:
            continue
        reason: str | None = None
        if obj.classification not in accepted:
            reason = "classification_not_accepted"
        elif obj.is_system_object or obj.is_dictionary_entry:
            reason = "protected_database_object"
        elif obj.hard_reference_count != 0:
            reason = "hard_referenced"
        if reason:
            skipped.append(CleanupSkip(handle=obj.handle, name=obj.object_type, reason=reason))
        else:
            remove.append(obj)
    remove.sort(key=lambda o: o.handle)
    skipped.sort(key=lambda o: o.handle)
    return GhostCleanupPlan(
        document_id=request.document_id,
        remove_handles=tuple(o.handle for o in remove),
        skipped=tuple(skipped),
        accepted_classifications=request.accepted_classifications,
        dry_run=request.dry_run,
    )


def execute_ghost_cleanup(
    request: GhostCleanupRequest,
    adapter: GhostCleanupAdapter,
) -> CleanupResult:
    _require_document(adapter, request.document_id)
    plan = plan_ghost_cleanup(request, adapter.inspect_ghost_objects())
    if request.dry_run or not plan.remove_handles:
        return CleanupResult(plan=plan, removed_handles=(), undo_mark_opened=False, undo_mark_closed=False)
    opened = False
    closed = False
    removed: tuple[str, ...] = ()
    try:
        adapter.begin_undo_mark()
        opened = True
        removed = tuple(adapter.remove_database_objects(plan.remove_handles))
        if set(removed) - set(plan.remove_handles):
            raise ValueError("adapter reported removal outside the approved ghost-object set")
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return CleanupResult(plan=plan, removed_handles=removed, undo_mark_opened=opened, undo_mark_closed=closed)


# ---------------------------------------------------------------------------
# LPU / xiDGNLineTypePurge
# ---------------------------------------------------------------------------


class LinetypeOrigin(StrEnum):
    DGN = "dgn"
    CAD = "cad"
    UNKNOWN = "unknown"


class LinetypeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    name: str = Field(min_length=1)
    origin: LinetypeOrigin
    in_use: bool
    dependent_resource_count: int = Field(ge=0)
    is_reserved: bool = False


class DgnLinetypePurgeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_names: tuple[str, ...] = ()
    include_all_dgn: bool = True
    allow_unknown_origin: bool = False
    preserve_names: tuple[str, ...] = ("ByLayer", "ByBlock", "Continuous")
    max_passes: int = Field(default=4, ge=1, le=20)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DgnLinetypePurgeRequest:
        _unique_casefold(self.target_names, "target_names")
        _unique_casefold(self.preserve_names, "preserve_names")
        if not self.include_all_dgn and not self.target_names:
            raise ValueError("LPU requires target_names when include_all_dgn is false")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("LPU execution requires explicit approval")
        return self


class DgnLinetypePurgePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "LPU"
    legacy_symbol: str = "xiDGNLineTypePurge"
    document_id: str
    purge_handles: tuple[str, ...]
    purge_names: tuple[str, ...]
    skipped: tuple[CleanupSkip, ...]
    max_passes: int
    destructive: bool = True
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class DgnLinetypePurgeAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def list_linetypes(self) -> Sequence[LinetypeSnapshot]: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def purge_linetypes(self, handles: Sequence[str]) -> Sequence[str]: ...


def plan_dgn_linetype_purge(
    request: DgnLinetypePurgeRequest,
    linetypes: Sequence[LinetypeSnapshot],
) -> DgnLinetypePurgePlan:
    targets = {n.casefold() for n in request.target_names}
    preserve = {n.casefold() for n in request.preserve_names}
    purge: list[LinetypeSnapshot] = []
    skipped: list[CleanupSkip] = []
    for lt in linetypes:
        selected = lt.name.casefold() in targets or (request.include_all_dgn and lt.origin is LinetypeOrigin.DGN)
        if not selected:
            continue
        reason: str | None = None
        if lt.name.casefold() in preserve or lt.is_reserved:
            reason = "reserved_or_preserved"
        elif lt.origin is LinetypeOrigin.CAD:
            reason = "not_dgn_origin"
        elif lt.origin is LinetypeOrigin.UNKNOWN and not request.allow_unknown_origin:
            reason = "unknown_origin_not_allowed"
        elif lt.in_use:
            reason = "linetype_in_use"
        elif lt.dependent_resource_count != 0:
            reason = "dependent_resources_exist"
        if reason:
            skipped.append(CleanupSkip(handle=lt.handle, name=lt.name, reason=reason))
        else:
            purge.append(lt)
    purge.sort(key=lambda lt: (lt.name.casefold(), lt.handle))
    skipped.sort(key=lambda lt: (lt.name.casefold(), lt.handle))
    return DgnLinetypePurgePlan(
        document_id=request.document_id,
        purge_handles=tuple(lt.handle for lt in purge),
        purge_names=tuple(lt.name for lt in purge),
        skipped=tuple(skipped),
        max_passes=request.max_passes,
        dry_run=request.dry_run,
    )


def execute_dgn_linetype_purge(
    request: DgnLinetypePurgeRequest,
    adapter: DgnLinetypePurgeAdapter,
) -> CleanupResult:
    _require_document(adapter, request.document_id)
    plan = plan_dgn_linetype_purge(request, adapter.list_linetypes())
    if request.dry_run or not plan.purge_handles:
        return CleanupResult(plan=plan, removed_handles=(), undo_mark_opened=False, undo_mark_closed=False)
    opened = False
    closed = False
    removed_total: list[str] = []
    pending = tuple(plan.purge_handles)
    try:
        adapter.begin_undo_mark()
        opened = True
        for _ in range(plan.max_passes):
            if not pending:
                break
            removed = tuple(adapter.purge_linetypes(pending))
            if set(removed) - set(pending):
                raise ValueError("adapter reported removal outside the approved linetype set")
            removed_total.extend(h for h in removed if h not in removed_total)
            pending = tuple(h for h in pending if h not in set(removed))
            if not removed:
                break
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return CleanupResult(
        plan=plan,
        removed_handles=tuple(removed_total),
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


# ---------------------------------------------------------------------------
# MTB1 / MTB2 -> shared explicit toilet-booth geometry core.
# No behavioral difference is inferred from the legacy alias alone.
# ---------------------------------------------------------------------------


class ToiletBoothLegacyVariant(StrEnum):
    MTB1 = "MTB1"
    MTB2 = "MTB2"


class DoorHinge(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class DoorSwing(StrEnum):
    INWARD = "inward"
    OUTWARD = "outward"


class ArcSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    center: Point3D
    radius: float = Field(gt=0)
    start_angle_degrees: float
    end_angle_degrees: float
    layer: str


class ToiletBoothRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    legacy_variant: ToiletBoothLegacyVariant
    origin: Point3D
    direction_degrees: float
    stall_count: int = Field(ge=1, le=100)
    stall_width: float = Field(gt=0)
    stall_depth: float = Field(gt=0)
    door_width: float = Field(gt=0)
    door_clearance_from_side: float = Field(ge=0)
    door_hinges: tuple[DoorHinge, ...]
    door_swing: DoorSwing
    include_left_end_panel: bool = True
    include_right_end_panel: bool = True
    layer: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ToiletBoothRequest:
        if not isfinite(self.direction_degrees):
            raise ValueError("direction_degrees must be finite")
        if len(self.door_hinges) != self.stall_count:
            raise ValueError("door_hinges length must match stall_count")
        if self.door_width + self.door_clearance_from_side > self.stall_width:
            raise ValueError("door opening does not fit within stall width")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("MTB execution requires explicit approval")
        return self


class ToiletBoothPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    shared_core_key: str = "toilet_booth_geometry"
    document_id: str
    legacy_variant: ToiletBoothLegacyVariant
    wall_lines: tuple[LineSpec, ...]
    door_leaf_lines: tuple[LineSpec, ...]
    door_swing_arcs: tuple[ArcSpec, ...]
    destructive: bool = False
    dry_run: bool
    dialog_required: bool = False
    legacy_variant_behavior_inferred: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class ToiletBoothResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: ToiletBoothPlan
    created_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool


class ToiletBoothAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def create_lines(self, specs: Sequence[LineSpec]) -> Sequence[str]: ...
    def create_arcs(self, specs: Sequence[ArcSpec]) -> Sequence[str]: ...


def _local_to_world(origin: Point3D, angle_degrees: float, x: float, y: float) -> Point3D:
    a = radians(angle_degrees)
    c, s = cos(a), sin(a)
    return Point3D(
        x=origin.x + x * c - y * s,
        y=origin.y + x * s + y * c,
        z=origin.z,
    )


def plan_toilet_booth(request: ToiletBoothRequest) -> ToiletBoothPlan:
    width_total = request.stall_count * request.stall_width
    wall_lines: list[LineSpec] = []
    door_lines: list[LineSpec] = []
    arcs: list[ArcSpec] = []

    def line(x1: float, y1: float, x2: float, y2: float) -> LineSpec:
        return LineSpec(
            start=_local_to_world(request.origin, request.direction_degrees, x1, y1),
            end=_local_to_world(request.origin, request.direction_degrees, x2, y2),
            layer=request.layer,
        )

    # back wall
    wall_lines.append(line(0, request.stall_depth, width_total, request.stall_depth))
    # end panels
    if request.include_left_end_panel:
        wall_lines.append(line(0, 0, 0, request.stall_depth))
    if request.include_right_end_panel:
        wall_lines.append(line(width_total, 0, width_total, request.stall_depth))
    # internal partitions
    for index in range(1, request.stall_count):
        x = index * request.stall_width
        wall_lines.append(line(x, 0, x, request.stall_depth))

    for index, hinge in enumerate(request.door_hinges):
        x0 = index * request.stall_width
        x1 = x0 + request.stall_width
        if hinge is DoorHinge.LEFT:
            hinge_x = x0 + request.door_clearance_from_side
            door_end_x = hinge_x + request.door_width
            wall_lines.append(line(x0, 0, hinge_x, 0))
            wall_lines.append(line(door_end_x, 0, x1, 0))
            leaf_y = request.door_width if request.door_swing is DoorSwing.INWARD else -request.door_width
            door_lines.append(line(hinge_x, 0, hinge_x, leaf_y))
            start_angle = request.direction_degrees
            end_angle = request.direction_degrees + (90 if request.door_swing is DoorSwing.INWARD else -90)
        else:
            hinge_x = x1 - request.door_clearance_from_side
            door_end_x = hinge_x - request.door_width
            wall_lines.append(line(x0, 0, door_end_x, 0))
            wall_lines.append(line(hinge_x, 0, x1, 0))
            leaf_y = request.door_width if request.door_swing is DoorSwing.INWARD else -request.door_width
            door_lines.append(line(hinge_x, 0, hinge_x, leaf_y))
            start_angle = request.direction_degrees + 180
            end_angle = request.direction_degrees + (90 if request.door_swing is DoorSwing.INWARD else 270)
        arcs.append(
            ArcSpec(
                center=_local_to_world(request.origin, request.direction_degrees, hinge_x, 0),
                radius=request.door_width,
                start_angle_degrees=start_angle,
                end_angle_degrees=end_angle,
                layer=request.layer,
            )
        )

    alias = request.legacy_variant.value
    symbol = "xiMakeToiletBooth1" if request.legacy_variant is ToiletBoothLegacyVariant.MTB1 else "xiMakeToiletBooth2"
    return ToiletBoothPlan(
        command_alias=alias,
        legacy_symbol=symbol,
        document_id=request.document_id,
        legacy_variant=request.legacy_variant,
        wall_lines=tuple(wall_lines),
        door_leaf_lines=tuple(door_lines),
        door_swing_arcs=tuple(arcs),
        dry_run=request.dry_run,
    )


def execute_toilet_booth(
    request: ToiletBoothRequest,
    adapter: ToiletBoothAdapter,
) -> ToiletBoothResult:
    _require_document(adapter, request.document_id)
    plan = plan_toilet_booth(request)
    if request.dry_run:
        return ToiletBoothResult(plan=plan, created_handles=(), undo_mark_opened=False, undo_mark_closed=False)
    opened = False
    closed = False
    created: list[str] = []
    try:
        adapter.begin_undo_mark()
        opened = True
        created.extend(adapter.create_lines((*plan.wall_lines, *plan.door_leaf_lines)))
        created.extend(adapter.create_arcs(plan.door_swing_arcs))
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return ToiletBoothResult(
        plan=plan, created_handles=tuple(created), undo_mark_opened=opened, undo_mark_closed=closed
    )


def register_headless_core_batch3_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Headless Core Batch 3",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="xicad_plan_attribute_block_rotate",
        description="Build a BAR plan that rotates non-attribute block geometry under an explicit attribute-preservation policy. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_attribute_block_rotate(
        request: AttributeBlockRotateRequest,
        blocks: list[AttributeBlockSnapshot],
    ) -> AttributeBlockRotatePlan:
        return plan_attribute_block_rotate(request, blocks)

    @mcp.tool(
        name="xicad_plan_null_block_cleanup",
        description="Build a conservative ABD empty/unreferenced block-record cleanup plan. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_null_block_cleanup(
        request: NullBlockCleanupRequest,
        records: list[BlockRecordSnapshot],
    ) -> NullBlockCleanupPlan:
        return plan_null_block_cleanup(request, records)

    @mcp.tool(
        name="xicad_plan_ghost_cleanup",
        description="Build an AGD cleanup plan from explicit forensic ghost-object classifications. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_ghost_cleanup(
        request: GhostCleanupRequest,
        objects: list[GhostObjectSnapshot],
    ) -> GhostCleanupPlan:
        return plan_ghost_cleanup(request, objects)

    @mcp.tool(
        name="xicad_plan_dgn_linetype_purge",
        description="Build a conservative LPU DGN-linetype purge plan. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_dgn_linetype_purge(
        request: DgnLinetypePurgeRequest,
        linetypes: list[LinetypeSnapshot],
    ) -> DgnLinetypePurgePlan:
        return plan_dgn_linetype_purge(request, linetypes)

    @mcp.tool(
        name="xicad_plan_toilet_booth",
        description="Build a shared MTB1/MTB2 toilet-booth geometry plan from complete explicit dimensions and door settings. This tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_toilet_booth(request: ToiletBoothRequest) -> ToiletBoothPlan:
        return plan_toilet_booth(request)
