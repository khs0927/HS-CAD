"""Evidence-bounded dialog-free planners for xiCAD batch 23B."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


class EvidenceLevel(StrEnum):
    DCL_AND_SHORTCUT_RECOVERED = "dcl_and_shortcut_recovered"
    SHORTCUT_ONLY_EXPLICIT_RESULT = "shortcut_only_explicit_result_not_legacy_equivalent"


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


class Batch23bPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    semantic_evidence: str
    semantic_gaps: tuple[str, ...]
    evidence_level: EvidenceLevel
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class EntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    layer: str = Field(min_length=1)


class ObjectToBlockMode(StrEnum):
    PLOT_BOX_TO_FRAME_BLOCK = "Frame_rdo"
    OBJECT_TO_BLOCK = "Object_rdo"
    MANY_BLOCKS_TO_ONE = "OneBlk_rdo"


class FrameRotation(StrEnum):
    CLOCKWISE = "Cw_rdo"
    COUNTERCLOCKWISE = "Ccw_rdo"


class BlockReplacement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handles: tuple[str, ...] = Field(min_length=1)
    block_name: str = Field(min_length=1)
    insertion_point: Point3D
    scale_x: float = Field(gt=0)
    scale_y: float = Field(gt=0)
    scale_z: float = Field(gt=0)
    rotation_degrees: float
    layer: str = Field(min_length=1)


class ObjectToBlockRequest(ContractRequest):
    mode: ObjectToBlockMode
    source_entities: tuple[EntitySnapshot, ...] = Field(min_length=1)
    exact_replacements: tuple[BlockReplacement, ...] = Field(min_length=1)
    delete_originals: bool
    link_scale: bool
    link_rotation: bool
    frame_rotation: FrameRotation | None = None

    @model_validator(mode="after")
    def validate_replacements(self) -> ObjectToBlockRequest:
        source = tuple(item.handle for item in self.source_entities)
        _unique(source, "TOB source")
        consumed = tuple(handle for item in self.exact_replacements for handle in item.source_handles)
        _unique(consumed, "TOB replacement source")
        if {item.casefold() for item in source} != {item.casefold() for item in consumed}:
            raise ValueError("TOB replacements must consume every source exactly once")
        if self.mode is ObjectToBlockMode.MANY_BLOCKS_TO_ONE and len(self.exact_replacements) != 1:
            raise ValueError("TOB OneBlk_rdo requires one exact replacement")
        if self.mode is ObjectToBlockMode.PLOT_BOX_TO_FRAME_BLOCK and self.frame_rotation is None:
            raise ValueError("TOB Frame_rdo requires an explicit DCL frame rotation")
        if self.mode is not ObjectToBlockMode.PLOT_BOX_TO_FRAME_BLOCK and self.frame_rotation is not None:
            raise ValueError("TOB frame rotation applies only to Frame_rdo")
        return self


class ObjectToBlockPlan(Batch23bPlan):
    mode: ObjectToBlockMode
    link_scale: bool
    link_rotation: bool
    frame_rotation: FrameRotation | None
    creates: tuple[BlockReplacement, ...]
    delete_handles: tuple[str, ...]


def plan_object_to_block(request: ObjectToBlockRequest) -> ObjectToBlockPlan:
    return ObjectToBlockPlan(
        command_alias="TOB",
        legacy_symbol="xiObjToBlk",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut plus ACAD_xi0521_d.01.dcl recovered mode/delete/link/rotation controls",
        semantic_gaps=(
            "compiled plot-box recognition and block registration unavailable",
            "cuLay0_tgl meaning unavailable",
            "caller supplies every exact block result",
        ),
        evidence_level=EvidenceLevel.DCL_AND_SHORTCUT_RECOVERED,
        mode=request.mode,
        link_scale=request.link_scale,
        link_rotation=request.link_rotation,
        frame_rotation=request.frame_rotation,
        creates=request.exact_replacements,
        delete_handles=tuple(item.handle for item in request.source_entities) if request.delete_originals else (),
    )


class ZoomRecordScope(StrEnum):
    ONE_SHARED = "One_rdo"
    EACH_DRAWING = "Each_rdo"


class ZoomOperation(StrEnum):
    STORE = "store"
    RESTORE = "restore"


class ZoomRegionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    lower_left: Point3D
    upper_right: Point3D

    @model_validator(mode="after")
    def validate_extents(self) -> ZoomRegionSnapshot:
        if self.lower_left.x >= self.upper_right.x or self.lower_left.y >= self.upper_right.y:
            raise ValueError("zoom lower-left must be below upper-right")
        return self


class ZoomRememberRequest(ContractRequest):
    operation: ZoomOperation
    scope: ZoomRecordScope
    slot: int = Field(ge=1, le=9)
    persistence_key: str = Field(min_length=1)
    persisted_revision: str = Field(min_length=1)
    exact_region: ZoomRegionSnapshot


class ZoomRememberPlan(Batch23bPlan):
    operation: ZoomOperation
    scope: ZoomRecordScope
    slot: int
    persistence_key: str
    persisted_revision: str
    exact_region: ZoomRegionSnapshot


def plan_zoom_remember(request: ZoomRememberRequest) -> ZoomRememberPlan:
    return ZoomRememberPlan(
        command_alias="ZR",
        legacy_symbol="xiZoomRemember",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut plus ACAD_xi0512_d.02.dcl recovered One/Each scope and nine area slots",
        semantic_gaps=(
            "persistence file format and revision rules compiled",
            "DCL coordinate text serialization unavailable",
            "caller supplies exact persisted region and revision",
        ),
        evidence_level=EvidenceLevel.DCL_AND_SHORTCUT_RECOVERED,
        operation=request.operation,
        scope=request.scope,
        slot=request.slot,
        persistence_key=request.persistence_key,
        persisted_revision=request.persisted_revision,
        exact_region=request.exact_region,
    )


class AreaSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    area: float = Field(gt=0)
    geometry_revision: str = Field(min_length=1)


class ProposedAreaLabel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    reported_area: float = Field(gt=0)
    text: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)


class AreaElementsRequest(ContractRequest):
    source_areas: tuple[AreaSnapshot, ...] = Field(min_length=1)
    exact_labels: tuple[ProposedAreaLabel, ...] = Field(min_length=1)
    area_tolerance: float = Field(default=1e-6, gt=0)

    @model_validator(mode="after")
    def validate_labels(self) -> AreaElementsRequest:
        _unique(tuple(item.handle for item in self.source_areas), "AE source")
        _unique(tuple(item.source_handle for item in self.exact_labels), "AE label")
        snapshots = {item.handle.casefold(): item.area for item in self.source_areas}
        labels = {item.source_handle.casefold(): item.reported_area for item in self.exact_labels}
        if snapshots.keys() != labels.keys():
            raise ValueError("AE requires one exact label per area snapshot")
        if any(
            not math.isclose(area, labels[handle], abs_tol=self.area_tolerance, rel_tol=0)
            for handle, area in snapshots.items()
        ):
            raise ValueError("AE reported area must match its source snapshot")
        return self


class AreaElementsPlan(Batch23bPlan):
    source_areas: tuple[AreaSnapshot, ...]
    creates: tuple[ProposedAreaLabel, ...]


def plan_area_elements(request: AreaElementsRequest) -> AreaElementsPlan:
    return AreaElementsPlan(
        command_alias="AE",
        legacy_symbol="xiAE",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut and CAD menu identify multi-element area display",
        semantic_gaps=(
            "no command-specific DCL/config/readable source",
            "area extraction and text formatting compiled",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        source_areas=request.source_areas,
        creates=request.exact_labels,
    )


class ProposedAreaTriangle(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    a: Point3D
    b: Point3D
    c: Point3D
    layer: str = Field(min_length=1)

    def planar_area(self) -> float:
        return abs((self.b.x - self.a.x) * (self.c.y - self.a.y) - (self.c.x - self.a.x) * (self.b.y - self.a.y)) / 2

    @model_validator(mode="after")
    def validate_triangle(self) -> ProposedAreaTriangle:
        if self.planar_area() <= 0:
            raise ValueError("AHM proposed triangle must be non-degenerate")
        return self


class MapAreaRequest(ContractRequest):
    boundary: AreaSnapshot
    exact_triangles: tuple[ProposedAreaTriangle, ...] = Field(min_length=1)
    area_tolerance: float = Field(default=1e-6, gt=0)

    @model_validator(mode="after")
    def validate_decomposition(self) -> MapAreaRequest:
        if any(item.source_handle.casefold() != self.boundary.handle.casefold() for item in self.exact_triangles):
            raise ValueError("AHM triangles must bind to the supplied boundary snapshot")
        total = sum(item.planar_area() for item in self.exact_triangles)
        if not math.isclose(total, self.boundary.area, abs_tol=self.area_tolerance, rel_tol=0):
            raise ValueError("AHM triangle area sum must match the boundary snapshot")
        return self


class MapAreaPlan(Batch23bPlan):
    boundary: AreaSnapshot
    computed_triangle_area: float
    creates: tuple[ProposedAreaTriangle, ...]


def plan_map_area(request: MapAreaRequest) -> MapAreaPlan:
    return MapAreaPlan(
        command_alias="AHM",
        legacy_symbol="xiMapArea",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut and CAD menu identify drawing area-calculation triangles",
        semantic_gaps=(
            "no command-specific DCL/config/readable source",
            "triangulation and boundary recognition compiled",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        boundary=request.boundary,
        computed_triangle_area=sum(item.planar_area() for item in request.exact_triangles),
        creates=request.exact_triangles,
    )


class AllocationSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    recipient_id: str = Field(min_length=1)
    exclusive_area: float = Field(ge=0)
    allocation_weight: float = Field(gt=0)
    geometry_revision: str = Field(min_length=1)


class ProposedAllocationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    recipient_id: str = Field(min_length=1)
    reported_shared_area: float = Field(ge=0)
    reported_total_area: float = Field(ge=0)
    text: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)


class BunAreaRequest(ContractRequest):
    recipients: tuple[AllocationSource, ...] = Field(min_length=1)
    shared_area: float = Field(gt=0)
    exact_records: tuple[ProposedAllocationRecord, ...] = Field(min_length=1)
    area_tolerance: float = Field(default=1e-6, gt=0)

    @model_validator(mode="after")
    def validate_allocation(self) -> BunAreaRequest:
        _unique(tuple(item.recipient_id for item in self.recipients), "BA recipient")
        _unique(tuple(item.recipient_id for item in self.exact_records), "BA record")
        records = {item.recipient_id.casefold(): item for item in self.exact_records}
        if {item.recipient_id.casefold() for item in self.recipients} != records.keys():
            raise ValueError("BA requires one exact record per recipient")
        weight_sum = sum(item.allocation_weight for item in self.recipients)
        for item in self.recipients:
            record = records[item.recipient_id.casefold()]
            allocated = self.shared_area * item.allocation_weight / weight_sum
            if not math.isclose(record.reported_shared_area, allocated, abs_tol=self.area_tolerance, rel_tol=0):
                raise ValueError("BA reported shared area must match explicit proportional policy")
            if not math.isclose(
                record.reported_total_area, item.exclusive_area + allocated, abs_tol=self.area_tolerance, rel_tol=0
            ):
                raise ValueError("BA reported total must equal exclusive plus allocated area")
        return self


class BunAreaPlan(Batch23bPlan):
    shared_area: float
    allocation_policy: str
    creates: tuple[ProposedAllocationRecord, ...]


def plan_bun_area(request: BunAreaRequest) -> BunAreaPlan:
    return BunAreaPlan(
        command_alias="BA",
        legacy_symbol="xiBunArea",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut and CAD menu identify shared-area distribution and total recording",
        semantic_gaps=(
            "legacy allocation basis and rounding compiled",
            "planner uses only explicit proportional weights",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        shared_area=request.shared_area,
        allocation_policy="shared_area * recipient_weight / sum(weights)",
        creates=request.exact_records,
    )


class DistanceVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class BuildingDistanceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    building_a_id: str = Field(min_length=1)
    building_b_id: str = Field(min_length=1)
    closest_point_a: Point3D
    closest_point_b: Point3D
    geometry_revision_a: str = Field(min_length=1)
    geometry_revision_b: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_pair(self) -> BuildingDistanceSnapshot:
        if self.building_a_id.casefold() == self.building_b_id.casefold():
            raise ValueError("CDB requires two distinct buildings")
        if self.closest_point_a == self.closest_point_b:
            raise ValueError("CDB closest points must have positive separation")
        return self

    def distance(self) -> float:
        return math.dist(
            (self.closest_point_a.x, self.closest_point_a.y, self.closest_point_a.z),
            (self.closest_point_b.x, self.closest_point_b.y, self.closest_point_b.z),
        )


class ProposedDistanceReview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    reported_distance: float = Field(gt=0)
    required_minimum: float = Field(gt=0)
    verdict: DistanceVerdict
    text: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)


class BuildingDistanceRequest(ContractRequest):
    snapshot: BuildingDistanceSnapshot
    exact_review: ProposedDistanceReview
    distance_tolerance: float = Field(default=1e-6, gt=0)

    @model_validator(mode="after")
    def validate_review(self) -> BuildingDistanceRequest:
        measured = self.snapshot.distance()
        if not math.isclose(self.exact_review.reported_distance, measured, abs_tol=self.distance_tolerance, rel_tol=0):
            raise ValueError("CDB reported distance must match explicit closest-point evidence")
        expected = DistanceVerdict.PASS if measured >= self.exact_review.required_minimum else DistanceVerdict.FAIL
        if self.exact_review.verdict is not expected:
            raise ValueError("CDB verdict must match the explicit minimum threshold")
        return self


class BuildingDistancePlan(Batch23bPlan):
    measured_distance: float
    review: ProposedDistanceReview


def plan_building_distance(request: BuildingDistanceRequest) -> BuildingDistancePlan:
    return BuildingDistancePlan(
        command_alias="CDB",
        legacy_symbol="xiCalDistBuilding",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut and CAD menu identify inter-building distance review",
        semantic_gaps=(
            "no command-specific DCL/config/readable source",
            "building recognition, closest-pair search, and legal threshold selection compiled",
            "caller supplies closest points and required minimum; no regulatory conclusion is inferred",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        measured_distance=request.snapshot.distance(),
        review=request.exact_review,
    )


def _unique(values: tuple[str, ...], label: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{label} values must be unique")


def register_headless_core_batch23b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 23B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_tob", plan_object_to_block),
        ("xicad_plan_zr", plan_zoom_remember),
        ("xicad_plan_ae", plan_area_elements),
        ("xicad_plan_ahm", plan_map_area),
        ("xicad_plan_ba", plan_bun_area),
        ("xicad_plan_cdb", plan_building_distance),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
