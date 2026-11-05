"""Evidence-bounded dialog-free planners for xiCAD Multi batch 20B."""

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
    SHORTCUT_ONLY_EXPLICIT_POLICY = "shortcut_only_explicit_policy_not_legacy_equivalent"


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


class Batch20bPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    semantic_evidence: str
    evidence_level: EvidenceLevel = EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class CopySpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    transform: Matrix4
    target_layer: str | None = None


class ExplicitCopy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    transform: Matrix4

    @model_validator(mode="after")
    def validate_affine(self) -> ExplicitCopy:
        if self.transform[3] != (0.0, 0.0, 0.0, 1.0):
            raise ValueError("ARD transform must be an affine 4x4 matrix")
        return self


class DynamicArrayRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    copies: tuple[ExplicitCopy, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_sources(self) -> DynamicArrayRequest:
        sources = {handle.casefold() for handle in self.source_handles}
        if len(sources) != len(self.source_handles):
            raise ValueError("ARD source handles must be unique")
        if any(item.source_handle.casefold() not in sources for item in self.copies):
            raise ValueError("ARD copy references a handle outside source_handles")
        return self


class CopyPlan(Batch20bPlan):
    copies: tuple[CopySpec, ...]


def plan_dynamic_array(request: DynamicArrayRequest) -> CopyPlan:
    return CopyPlan(
        command_alias="ARD",
        legacy_symbol="xiDynamicArr",
        semantic_evidence="current/frozen shortcut: 입체 동적 배열; every 3D affine instance is caller-supplied",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        copies=tuple(CopySpec(source_handle=item.source_handle, transform=item.transform) for item in request.copies),
    )


class Axis(StrEnum):
    X = "x"
    Y = "y"
    Z = "z"


class PolarArrayRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    center: Point3D
    reference_point: Point3D
    axis: Axis
    item_count: int = Field(gt=0)
    total_angle_degrees: float
    rotate_items: bool
    source_is_first_item: bool = True

    @model_validator(mode="after")
    def validate_polar(self) -> PolarArrayRequest:
        if self.center == self.reference_point:
            raise ValueError("ARP reference_point must differ from center")
        if self.total_angle_degrees == 0:
            raise ValueError("ARP total angle must be non-zero")
        _unique(self.source_handles, "ARP")
        return self


def plan_polar_array(request: PolarArrayRequest) -> CopyPlan:
    denominator = request.item_count if abs(request.total_angle_degrees) == 360 else max(1, request.item_count - 1)
    indices = range(1, request.item_count) if request.source_is_first_item else range(request.item_count)
    copies = []
    for index in indices:
        angle = request.total_angle_degrees * index / denominator
        matrix = (
            _rotation_about(request.center, request.axis, angle)
            if request.rotate_items
            else _polar_translation(request.center, request.reference_point, request.axis, angle)
        )
        copies.extend(CopySpec(source_handle=handle, transform=matrix) for handle in request.source_handles)
    return CopyPlan(
        command_alias="ARP",
        legacy_symbol="xiArrP",
        semantic_evidence="current/frozen shortcut: 원형 동적 배열; center/axis/count/angle/rotation policy explicit",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        copies=tuple(copies),
    )


class LinearArrayRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    direction: Point3D
    item_count: int = Field(gt=0)
    spacing: float = Field(gt=0)
    source_is_first_item: bool = True

    @model_validator(mode="after")
    def validate_linear(self) -> LinearArrayRequest:
        if self.direction == Point3D(x=0, y=0, z=0):
            raise ValueError("ARV direction must be non-zero")
        _unique(self.source_handles, "ARV")
        return self


def plan_linear_array(request: LinearArrayRequest) -> CopyPlan:
    length = (request.direction.x**2 + request.direction.y**2 + request.direction.z**2) ** 0.5
    unit = Point3D(
        x=request.direction.x / length,
        y=request.direction.y / length,
        z=request.direction.z / length,
    )
    indices = range(1, request.item_count) if request.source_is_first_item else range(request.item_count)
    return CopyPlan(
        command_alias="ARV",
        legacy_symbol="xiArrV",
        semantic_evidence="current/frozen shortcut: 직선 동적 배열; 3D direction/count/spacing explicit",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        copies=tuple(
            CopySpec(
                source_handle=handle,
                transform=_translation(
                    unit.x * request.spacing * index, unit.y * request.spacing * index, unit.z * request.spacing * index
                ),
            )
            for index in indices
            for handle in request.source_handles
        ),
    )


class LayerDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    color: int = Field(ge=1, le=255)
    linetype: str = Field(min_length=1)
    lineweight: int


class CopyToNewLayerRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    displacement: Point3D
    new_layer: LayerDefinition

    @model_validator(mode="after")
    def validate_handles(self) -> CopyToNewLayerRequest:
        _unique(self.source_handles, "CNL")
        return self


class CopyToLayerPlan(CopyPlan):
    create_layer: LayerDefinition | None = None


def plan_copy_to_new_layer(request: CopyToNewLayerRequest) -> CopyToLayerPlan:
    matrix = _translation(request.displacement.x, request.displacement.y, request.displacement.z)
    return CopyToLayerPlan(
        command_alias="CNL",
        legacy_symbol="xiCopyToNewLayer",
        semantic_evidence="current/frozen shortcut: 새 켜로 복사; new-layer properties are explicit policy",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        create_layer=request.new_layer,
        copies=tuple(
            CopySpec(source_handle=handle, transform=matrix, target_layer=request.new_layer.name)
            for handle in request.source_handles
        ),
    )


class CopyRotateRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    base_point: Point3D
    destination_point: Point3D
    rotation_degrees: float

    @model_validator(mode="after")
    def validate_handles(self) -> CopyRotateRequest:
        _unique(self.source_handles, "CR")
        return self


def plan_copy_rotate(request: CopyRotateRequest) -> CopyPlan:
    matrix = _copy_rotate_matrix(
        request.base_point,
        request.destination_point,
        request.rotation_degrees,
    )
    return CopyPlan(
        command_alias="CR",
        legacy_symbol="xiCopyRotate",
        semantic_evidence="current/frozen shortcut: 복사 후 회전; base/destination/angle explicit",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        copies=tuple(CopySpec(source_handle=handle, transform=matrix) for handle in request.source_handles),
    )


class CopyToCurrentLayerRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    displacement: Point3D
    current_layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_handles(self) -> CopyToCurrentLayerRequest:
        _unique(self.source_handles, "CTL")
        return self


def plan_copy_to_current_layer(request: CopyToCurrentLayerRequest) -> CopyToLayerPlan:
    matrix = _translation(request.displacement.x, request.displacement.y, request.displacement.z)
    return CopyToLayerPlan(
        command_alias="CTL",
        legacy_symbol="xiCopyToCLayer",
        semantic_evidence="current/frozen shortcut: 현재켜로 복사; current layer captured explicitly",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        copies=tuple(
            CopySpec(source_handle=handle, transform=matrix, target_layer=request.current_layer)
            for handle in request.source_handles
        ),
    )


def _unique(handles: tuple[str, ...], alias: str) -> None:
    folded = [handle.casefold() for handle in handles]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{alias} source handles must be unique")


def _translation(x: float, y: float, z: float) -> Matrix4:
    return ((1, 0, 0, x), (0, 1, 0, y), (0, 0, 1, z), (0, 0, 0, 1))


def _axis_rotation(axis: Axis, angle_degrees: float) -> Matrix4:
    c, s = cos(radians(angle_degrees)), sin(radians(angle_degrees))
    if axis is Axis.X:
        return ((1, 0, 0, 0), (0, c, -s, 0), (0, s, c, 0), (0, 0, 0, 1))
    if axis is Axis.Y:
        return ((c, 0, s, 0), (0, 1, 0, 0), (-s, 0, c, 0), (0, 0, 0, 1))
    return ((c, -s, 0, 0), (s, c, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))


def _multiply(left: Matrix4, right: Matrix4) -> Matrix4:
    return tuple(
        tuple(sum(left[row][k] * right[k][column] for k in range(4)) for column in range(4)) for row in range(4)
    )


def _rotation_about(center: Point3D, axis: Axis, angle: float) -> Matrix4:
    return _multiply(
        _translation(center.x, center.y, center.z),
        _multiply(_axis_rotation(axis, angle), _translation(-center.x, -center.y, -center.z)),
    )


def _transform(point: Point3D, matrix: Matrix4) -> Point3D:
    values = (point.x, point.y, point.z, 1.0)
    return Point3D(
        x=sum(matrix[0][i] * values[i] for i in range(4)),
        y=sum(matrix[1][i] * values[i] for i in range(4)),
        z=sum(matrix[2][i] * values[i] for i in range(4)),
    )


def _polar_translation(center: Point3D, reference: Point3D, axis: Axis, angle: float) -> Matrix4:
    rotated = _transform(reference, _rotation_about(center, axis, angle))
    return _translation(rotated.x - reference.x, rotated.y - reference.y, rotated.z - reference.z)


def _copy_rotate_matrix(base: Point3D, destination: Point3D, angle: float) -> Matrix4:
    rotation = _axis_rotation(Axis.Z, angle)
    return _multiply(
        _translation(destination.x, destination.y, destination.z),
        _multiply(rotation, _translation(-base.x, -base.y, -base.z)),
    )


def register_headless_core_batch20b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 20B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_ard", plan_dynamic_array),
        ("xicad_plan_arp", plan_polar_array),
        ("xicad_plan_arv", plan_linear_array),
        ("xicad_plan_cnl", plan_copy_to_new_layer),
        ("xicad_plan_cr", plan_copy_rotate),
        ("xicad_plan_ctl", plan_copy_to_current_layer),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
