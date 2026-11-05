"""Evidence-bounded deterministic planners for xiCAD Multi batch 22A."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


class ContractRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    document_id: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"dry_run", "approval"})
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def validate_approval(self) -> ContractRequest:
        if not self.dry_run and (not self.approval.approved or self.approval.fingerprint != self.fingerprint()):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch22APlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    semantic_evidence: str
    semantic_gaps: tuple[str, ...]
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class OffsetBasis(StrEnum):
    ORIGINAL = "original"
    PREVIOUS_RESULT = "previous_result"


class OffsetOperation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    signed_distance: float
    target_layer: str | None = None
    result_token: str = Field(min_length=1)


class OffsetMultiRequest(ContractRequest):
    source_handle: str = Field(min_length=1)
    signed_distances: tuple[float, ...] = Field(min_length=1)
    basis: OffsetBasis
    target_layer: str | None = None

    @model_validator(mode="after")
    def validate_distances(self) -> OffsetMultiRequest:
        if any(distance == 0 for distance in self.signed_distances):
            raise ValueError("OM offset distances must be non-zero")
        return self


class OffsetPlan(Batch22APlan):
    operations: tuple[OffsetOperation, ...]


def plan_offset_multi(request: OffsetMultiRequest) -> OffsetPlan:
    operations = []
    previous = request.source_handle
    for index, distance in enumerate(request.signed_distances, start=1):
        source = request.source_handle if request.basis is OffsetBasis.ORIGINAL else previous
        token = f"OM:{index}"
        operations.append(
            OffsetOperation(
                source_handle=source,
                signed_distance=distance,
                target_layer=request.target_layer,
                result_token=token,
            )
        )
        previous = token
    return OffsetPlan(
        command_alias="OM",
        legacy_symbol="xiOffsetMulti",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current+frozen shortcut: 연속 간격띄우기; offset sequence policy is caller-supplied",
        semantic_gaps=("legacy distance prompt repetition", "side selection", "supported curve types"),
        operations=tuple(operations),
    )


class OffsetCurrentLayerRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    signed_distance: float
    current_layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_request(self) -> OffsetCurrentLayerRequest:
        _unique(self.source_handles, "OO")
        if self.signed_distance == 0:
            raise ValueError("OO offset distance must be non-zero")
        return self


def plan_offset_current_layer(request: OffsetCurrentLayerRequest) -> OffsetPlan:
    return OffsetPlan(
        command_alias="OO",
        legacy_symbol="xiofc",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current+frozen shortcut: 현재 layer로 offset하기; current layer is captured explicitly",
        semantic_gaps=("legacy side-point interaction", "source retention default", "supported curve types"),
        operations=tuple(
            OffsetOperation(
                source_handle=handle,
                signed_distance=request.signed_distance,
                target_layer=request.current_layer,
                result_token=f"OO:{index}",
            )
            for index, handle in enumerate(request.source_handles, start=1)
        ),
    )


class ToleranceOffsetRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    lower_signed_distance: float
    upper_signed_distance: float
    target_layer: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> ToleranceOffsetRequest:
        _unique(self.source_handles, "OT")
        if self.lower_signed_distance == 0 or self.upper_signed_distance == 0:
            raise ValueError("OT tolerance distances must be non-zero")
        if self.lower_signed_distance == self.upper_signed_distance:
            raise ValueError("OT lower and upper signed distances must differ")
        return self


def plan_offset_tolerance(request: ToleranceOffsetRequest) -> OffsetPlan:
    distances = (request.lower_signed_distance, request.upper_signed_distance)
    return OffsetPlan(
        command_alias="OT",
        legacy_symbol="xiOffsetTolerance",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current+frozen shortcut: 허용공차선 띄우기; two signed tolerance offsets are explicit",
        semantic_gaps=("tolerance source/units", "legacy symmetric/asymmetric default", "side selection"),
        operations=tuple(
            OffsetOperation(
                source_handle=handle,
                signed_distance=distance,
                target_layer=request.target_layer,
                result_token=f"OT:{handle}:{index}",
            )
            for handle in request.source_handles
            for index, distance in enumerate(distances, start=1)
        ),
    )


class BoundingBox3D(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    minimum: Point3D
    maximum: Point3D

    @model_validator(mode="after")
    def validate_extent(self) -> BoundingBox3D:
        if not (
            self.minimum.x < self.maximum.x
            and self.minimum.y < self.maximum.y
            and self.minimum.z <= self.maximum.z
        ):
            raise ValueError("RDC bounds must increase in X/Y and not decrease in Z")
        return self


class CopyPlacement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    destination: Point3D
    rotation_degrees: float


class RandomCopyRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    bounds: BoundingBox3D
    copy_count: int = Field(gt=0, le=10000)
    seed: str = Field(min_length=1)
    minimum_rotation_degrees: float = 0
    maximum_rotation_degrees: float = 0

    @model_validator(mode="after")
    def validate_request(self) -> RandomCopyRequest:
        _unique(self.source_handles, "RDC")
        if self.minimum_rotation_degrees > self.maximum_rotation_degrees:
            raise ValueError("RDC rotation range is reversed")
        return self


class RandomCopyPlan(Batch22APlan):
    placements: tuple[CopyPlacement, ...]


def _unit(seed: str, index: int, channel: str) -> float:
    digest = hashlib.sha256(f"{seed}\0{index}\0{channel}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / (2**64 - 1)


def plan_random_copy(request: RandomCopyRequest) -> RandomCopyPlan:
    low, high = request.bounds.minimum, request.bounds.maximum
    placements = []
    for index in range(request.copy_count):
        destination = Point3D(
            x=low.x + (high.x - low.x) * _unit(request.seed, index, "x"),
            y=low.y + (high.y - low.y) * _unit(request.seed, index, "y"),
            z=low.z + (high.z - low.z) * _unit(request.seed, index, "z"),
        )
        rotation = request.minimum_rotation_degrees + (
            request.maximum_rotation_degrees - request.minimum_rotation_degrees
        ) * _unit(request.seed, index, "rotation")
        handle = request.source_handles[index % len(request.source_handles)]
        placements.append(CopyPlacement(source_handle=handle, destination=destination, rotation_degrees=rotation))
    return RandomCopyPlan(
        command_alias="RDC",
        legacy_symbol="xiRandomCopy",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current+frozen shortcut: 무작위 복사하기; SHA-256 seeded placement policy is explicit",
        semantic_gaps=("legacy random generator", "selection distribution", "base-point and rotation defaults"),
        placements=tuple(placements),
    )


class RotationTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    center: Point3D


class RotateMultiRequest(ContractRequest):
    targets: tuple[RotationTarget, ...] = Field(min_length=1)
    angle_degrees: float
    keep_originals: bool

    @model_validator(mode="after")
    def validate_request(self) -> RotateMultiRequest:
        _unique(tuple(target.handle for target in self.targets), "RM")
        if self.angle_degrees == 0:
            raise ValueError("RM rotation angle must be non-zero")
        return self


class RotationOperation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    center: Point3D
    angle_degrees: float
    keep_original: bool


class RotateMultiPlan(Batch22APlan):
    operations: tuple[RotationOperation, ...]


def plan_rotate_multi(request: RotateMultiRequest) -> RotateMultiPlan:
    return RotateMultiPlan(
        command_alias="RM",
        legacy_symbol="xiRotMulti",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current+frozen shortcut: 자기 자리에서 회전; xiConfig.cfg stores Center|1",
        semantic_gaps=("meaning of config flag 1", "center derivation", "copy versus rotate prompt"),
        operations=tuple(
            RotationOperation(
                handle=target.handle,
                center=target.center,
                angle_degrees=request.angle_degrees,
                keep_original=request.keep_originals,
            )
            for target in request.targets
        ),
    )


class DrawOrderMode(StrEnum):
    BOTTOM = "bottom"
    BEHIND_REFERENCE = "behind_reference"


class SolidMoveBackRequest(ContractRequest):
    target_handles: tuple[str, ...] = Field(min_length=1)
    entity_types: dict[str, str]
    mode: DrawOrderMode
    reference_handle: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> SolidMoveBackRequest:
        _unique(self.target_handles, "SB")
        types = {handle.casefold(): value.upper() for handle, value in self.entity_types.items()}
        if any(handle.casefold() not in types for handle in self.target_handles):
            raise ValueError("SB requires an entity type for every target")
        if any(types[handle.casefold()] not in {"SOLID", "TRACE", "HATCH"} for handle in self.target_handles):
            raise ValueError("SB target types are restricted to explicitly supplied SOLID/TRACE/HATCH")
        if self.mode is DrawOrderMode.BEHIND_REFERENCE and not self.reference_handle:
            raise ValueError("SB behind_reference mode requires reference_handle")
        if self.mode is DrawOrderMode.BOTTOM and self.reference_handle is not None:
            raise ValueError("SB bottom mode does not accept reference_handle")
        return self


class SolidMoveBackPlan(Batch22APlan):
    target_handles: tuple[str, ...]
    mode: DrawOrderMode
    reference_handle: str | None


def plan_solid_move_back(request: SolidMoveBackRequest) -> SolidMoveBackPlan:
    return SolidMoveBackPlan(
        command_alias="SB",
        legacy_symbol="xiSolidMoveBack",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current+frozen shortcut: 솔리드 뒤로 보내기; target types and draw-order destination explicit",
        semantic_gaps=("legacy meaning of solid", "reference selection", "relative ordering among multiple targets"),
        target_handles=request.target_handles,
        mode=request.mode,
        reference_handle=request.reference_handle,
    )


def _unique(handles: tuple[str, ...], alias: str) -> None:
    folded = [handle.casefold() for handle in handles]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{alias} handles must be unique")


def register_headless_core_batch22a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 22A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_om", plan_offset_multi),
        ("xicad_plan_oo", plan_offset_current_layer),
        ("xicad_plan_ot", plan_offset_tolerance),
        ("xicad_plan_rdc", plan_random_copy),
        ("xicad_plan_rm", plan_rotate_multi),
        ("xicad_plan_sb", plan_solid_move_back),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
