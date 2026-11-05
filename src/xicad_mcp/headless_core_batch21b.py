"""Evidence-bounded dialog-free planners for xiCAD Multi batch 21B."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from math import cos, radians, sin
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D

Matrix4 = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]


class EvidenceLevel(StrEnum):
    DCL_AND_CONFIG_RECOVERED = "dcl_and_config_recovered"
    SHORTCUT_ONLY_EXPLICIT_POLICY = "shortcut_only_explicit_policy_not_legacy_equivalent"


class SourceDisposition(StrEnum):
    PRESERVE = "preserve"
    REPLACE = "replace"


class ContractRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"dry_run", "approval"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    @model_validator(mode="after")
    def validate_approval(self) -> ContractRequest:
        if not self.dry_run and (not self.approval.approved or self.approval.fingerprint != self.fingerprint()):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch21bPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    semantic_evidence: str
    evidence_level: EvidenceLevel
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class MeasureRequest(ContractRequest):
    source_handle: str = Field(min_length=1)
    start_point: Point3D
    interval: float = Field(gt=0)
    placement_points: tuple[Point3D, ...] = Field(min_length=1)


class MeasurePlan(Batch21bPlan):
    command_alias: str = "MM"
    legacy_symbol: str = "xiMeasure"
    semantic_evidence: str = "current/frozen shortcut: 시작점에서의 길이 지정 Measure; placements explicit"
    evidence_level: EvidenceLevel = EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY
    source_handle: str
    start_point: Point3D
    interval: float
    placement_points: tuple[Point3D, ...]


def plan_measure(request: MeasureRequest) -> MeasurePlan:
    return MeasurePlan(
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        source_handle=request.source_handle,
        start_point=request.start_point,
        interval=request.interval,
        placement_points=request.placement_points,
    )


class AlignTargetMode(StrEnum):
    POINT = "point"
    SELECTED_OBJECT = "selected_object"


class MoveAxis(StrEnum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class AnchorPosition(StrEnum):
    LEFT_TOP = "left_top"
    CENTER_TOP = "center_top"
    RIGHT_TOP = "right_top"
    LEFT_MIDDLE = "left_middle"
    MIDDLE = "middle"
    RIGHT_MIDDLE = "right_middle"
    LEFT_BOTTOM = "left_bottom"
    CENTER_BOTTOM = "center_bottom"
    RIGHT_BOTTOM = "right_bottom"


class AlignItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    source_anchor: Point3D
    source_angle_degrees: float = 0


class ObjectAlignRequest(ContractRequest):
    items: tuple[AlignItem, ...] = Field(min_length=1)
    target_mode: AlignTargetMode
    target_point: Point3D
    target_angle_degrees: float | None = None
    rotate_to_target_angle: bool
    move_axis: MoveAxis
    anchor_position: AnchorPosition
    copy_entities: bool

    @model_validator(mode="after")
    def validate_target(self) -> ObjectAlignRequest:
        _unique(tuple(item.handle for item in self.items), "OA")
        if self.rotate_to_target_angle and self.target_angle_degrees is None:
            raise ValueError("OA rotation requires target_angle_degrees")
        return self


class TransformSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    transform: Matrix4
    copy_entity: bool


class AlignPlan(Batch21bPlan):
    target_mode: AlignTargetMode
    move_axis: MoveAxis | None
    anchor_position: AnchorPosition | None
    transforms: tuple[TransformSpec, ...]


def plan_object_align(request: ObjectAlignRequest) -> AlignPlan:
    transforms = tuple(
        TransformSpec(
            source_handle=item.handle,
            transform=_align_matrix(
                item,
                request.target_point,
                request.move_axis,
                request.target_angle_degrees if request.rotate_to_target_angle else None,
            ),
            copy_entity=request.copy_entities,
        )
        for item in request.items
    )
    return AlignPlan(
        command_alias="OA",
        legacy_symbol="xiObjectsAlign",
        semantic_evidence="shortcut plus ACAD_xi0451_d.01.dcl and /xiObjectsAlign config",
        evidence_level=EvidenceLevel.DCL_AND_CONFIG_RECOVERED,
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        target_mode=request.target_mode,
        move_axis=request.move_axis,
        anchor_position=request.anchor_position,
        transforms=transforms,
    )


class ObjectAlignAngleRequest(ContractRequest):
    items: tuple[AlignItem, ...] = Field(min_length=1)
    target_point: Point3D
    target_object_handle: str = Field(min_length=1)
    target_angle_degrees: float
    copy_entities: bool

    @model_validator(mode="after")
    def validate_handles(self) -> ObjectAlignAngleRequest:
        _unique(tuple(item.handle for item in self.items), "OAA")
        if self.target_object_handle.casefold() in {item.handle.casefold() for item in self.items}:
            raise ValueError("OAA target object must differ from aligned items")
        return self


def plan_object_align_angle(request: ObjectAlignAngleRequest) -> AlignPlan:
    return AlignPlan(
        command_alias="OAA",
        legacy_symbol="xiObjectsAlignAngle",
        semantic_evidence="current/frozen shortcut: 객체를 객체각도에 정렬; target angle and anchors explicit",
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        target_mode=AlignTargetMode.SELECTED_OBJECT,
        move_axis=None,
        anchor_position=None,
        transforms=tuple(
            TransformSpec(
                source_handle=item.handle,
                transform=_align_matrix(item, request.target_point, None, request.target_angle_degrees),
                copy_entity=request.copy_entities,
            )
            for item in request.items
        ),
    )


class OffsetOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handles: tuple[str, ...] = Field(min_length=1)
    vertices: tuple[Point3D, ...] = Field(min_length=2)
    closed: bool = False
    layer: str = Field(min_length=1)


class BothSidesOffsetRequest(ContractRequest):
    source_handle: str = Field(min_length=1)
    distance: float = Field(gt=0)
    positive_side: OffsetOutput
    negative_side: OffsetOutput

    @model_validator(mode="after")
    def validate_outputs(self) -> BothSidesOffsetRequest:
        expected = {self.source_handle.casefold()}
        if {value.casefold() for value in self.positive_side.source_handles} != expected or {
            value.casefold() for value in self.negative_side.source_handles
        } != expected:
            raise ValueError("OB outputs must be bound to source_handle")
        return self


class OffsetPlan(Batch21bPlan):
    distance: float
    creates: tuple[OffsetOutput, ...]
    delete_handles: tuple[str, ...]


def plan_both_sides_offset(request: BothSidesOffsetRequest) -> OffsetPlan:
    return OffsetPlan(
        command_alias="OB",
        legacy_symbol="xiofbs",
        semantic_evidence="current/frozen shortcut: 양쪽으로 등간격 옵셋하기; result vertices explicit",
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        distance=request.distance,
        creates=(request.positive_side, request.negative_side),
        delete_handles=(),
    )


class OffsetEraseRequest(ContractRequest):
    source_handle: str = Field(min_length=1)
    distance: float = Field(gt=0)
    result: OffsetOutput

    @model_validator(mode="after")
    def validate_result(self) -> OffsetEraseRequest:
        if {value.casefold() for value in self.result.source_handles} != {self.source_handle.casefold()}:
            raise ValueError("OE result must be bound to source_handle")
        return self


def plan_offset_erase(request: OffsetEraseRequest) -> OffsetPlan:
    return OffsetPlan(
        command_alias="OE",
        legacy_symbol="xiofe",
        semantic_evidence="current/frozen shortcut: 옵셋 후 원본삭제; result vertices explicit",
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        distance=request.distance,
        creates=(request.result,),
        delete_handles=(request.source_handle,),
    )


class IntegratedOffsetRequest(ContractRequest):
    connected_source_handles: tuple[str, ...] = Field(min_length=2)
    distance: float = Field(gt=0)
    outputs: tuple[OffsetOutput, ...] = Field(min_length=1)
    source_disposition: SourceDisposition

    @model_validator(mode="after")
    def validate_sources(self) -> IntegratedOffsetRequest:
        _unique(self.connected_source_handles, "OI")
        expected = {handle.casefold() for handle in self.connected_source_handles}
        if any(not {handle.casefold() for handle in output.source_handles} <= expected for output in self.outputs):
            raise ValueError("OI output references a handle outside connected_source_handles")
        return self


def plan_integrated_offset(request: IntegratedOffsetRequest) -> OffsetPlan:
    return OffsetPlan(
        command_alias="OI",
        legacy_symbol="xiOffsetIntegrate",
        semantic_evidence="current/frozen shortcut: 붙어 있는 선까지 모두 함께 간격띄우기; connectivity/results explicit",
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        distance=request.distance,
        creates=request.outputs,
        delete_handles=request.connected_source_handles
        if request.source_disposition is SourceDisposition.REPLACE
        else (),
    )


def _unique(handles: tuple[str, ...], alias: str) -> None:
    folded = [handle.casefold() for handle in handles]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{alias} handles must be unique")


def _align_matrix(
    item: AlignItem,
    target: Point3D,
    axis: MoveAxis | None,
    target_angle: float | None,
) -> Matrix4:
    angle = 0.0 if target_angle is None else target_angle - item.source_angle_degrees
    c, s = cos(radians(angle)), sin(radians(angle))
    rotated_x = c * item.source_anchor.x - s * item.source_anchor.y
    rotated_y = s * item.source_anchor.x + c * item.source_anchor.y
    tx, ty, tz = target.x - rotated_x, target.y - rotated_y, target.z - item.source_anchor.z
    if axis is MoveAxis.HORIZONTAL:
        ty, tz = 0.0, 0.0
    elif axis is MoveAxis.VERTICAL:
        tx, tz = 0.0, 0.0
    return ((c, -s, 0, tx), (s, c, 0, ty), (0, 0, 1, tz), (0, 0, 0, 1))


def register_headless_core_batch21b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 21B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_mm", plan_measure),
        ("xicad_plan_oa", plan_object_align),
        ("xicad_plan_oaa", plan_object_align_angle),
        ("xicad_plan_ob", plan_both_sides_offset),
        ("xicad_plan_oe", plan_offset_erase),
        ("xicad_plan_oi", plan_integrated_offset),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
