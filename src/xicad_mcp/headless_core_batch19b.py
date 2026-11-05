"""Evidence-bounded, dialog-free planning contracts for xiCAD Cut batch 19B.

The compiled FAS/ZELX bodies are not source code.  BAT and CUT have recoverable
DCL/config inputs; BB, BRO, CB and DTP have shortcut descriptions only.  Those
four commands therefore require explicit geometry decisions from the caller
and are not claimed to reproduce undocumented legacy prompts.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


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


class Batch19bPlan(BaseModel):
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


class BatPlacementMode(StrEnum):
    POSITION = "position"
    REPEAT_DISTANCE = "repeat_distance"
    MIDDLE = "middle"
    USER_POINT = "user_point"
    EXISTING_TEXT = "existing_text"


class TextAngleMode(StrEnum):
    ZERO = "zero"
    PARALLEL = "parallel_to_source"
    PERPENDICULAR = "perpendicular_to_source"


class BreakTextStation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    break_center: Point3D
    text_point: Point3D
    rotation_degrees: float


class BreakAndTextRequest(ContractRequest):
    placement_mode: BatPlacementMode
    stations: tuple[BreakTextStation, ...] = Field(min_length=1)
    repeat_distance: float | None = Field(default=None, gt=0)
    first_at_half_spacing: bool
    break_gap: float = Field(gt=0)
    angle_mode: TextAngleMode
    text: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    text_layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_repeat_mode(self) -> BreakAndTextRequest:
        if self.placement_mode is BatPlacementMode.REPEAT_DISTANCE and self.repeat_distance is None:
            raise ValueError("BAT repeat_distance mode requires repeat_distance")
        handles = [station.source_handle.casefold() for station in self.stations]
        points = [(station.break_center.x, station.break_center.y, station.break_center.z) for station in self.stations]
        if len(set(zip(handles, points, strict=True))) != len(self.stations):
            raise ValueError("BAT stations must identify unique source/point pairs")
        return self


class BreakGapSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    center: Point3D
    gap: float


class TextCreateSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    insertion_point: Point3D
    text: str
    height: float
    rotation_degrees: float
    layer: str


class BreakAndTextPlan(Batch19bPlan):
    command_alias: str = "BAT"
    legacy_symbol: str = "xiBreakAndText"
    semantic_evidence: str = "current/frozen shortcut plus ZWCAD_xi0487_d.01.dcl and xiConfig /xiBreakAndText"
    evidence_level: EvidenceLevel = EvidenceLevel.DCL_AND_CONFIG_RECOVERED
    breaks: tuple[BreakGapSpec, ...]
    texts: tuple[TextCreateSpec, ...]


def plan_break_and_text(request: BreakAndTextRequest) -> BreakAndTextPlan:
    return BreakAndTextPlan(
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        breaks=tuple(
            BreakGapSpec(source_handle=item.source_handle, center=item.break_center, gap=request.break_gap)
            for item in request.stations
        ),
        texts=tuple(
            TextCreateSpec(
                source_handle=item.source_handle,
                insertion_point=item.text_point,
                text=request.text,
                height=request.text_height,
                rotation_degrees=item.rotation_degrees,
                layer=request.text_layer,
            )
            for item in request.stations
        ),
    )


class BreakToCurrentRequest(ContractRequest):
    source_handle: str = Field(min_length=1)
    first_break_point: Point3D
    second_break_point: Point3D
    current_layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_points(self) -> BreakToCurrentRequest:
        if self.first_break_point == self.second_break_point:
            raise ValueError("BB break points must be distinct")
        return self


class BreakToCurrentPlan(Batch19bPlan):
    command_alias: str = "BB"
    legacy_symbol: str = "xiBreakToCurrent"
    semantic_evidence: str = "shortcut description: cut and put on current layer; exact segment is caller-selected"
    evidence_level: EvidenceLevel = EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY
    source_handle: str
    isolated_segment: tuple[Point3D, Point3D]
    target_layer: str


def plan_break_to_current(request: BreakToCurrentRequest) -> BreakToCurrentPlan:
    return BreakToCurrentPlan(
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        source_handle=request.source_handle,
        isolated_segment=(request.first_break_point, request.second_break_point),
        target_layer=request.current_layer,
    )


class BreakOverRequest(ContractRequest):
    target_handle: str = Field(min_length=1)
    cutter_handles: tuple[str, ...] = Field(min_length=1)
    intersection_points: tuple[Point3D, ...] = Field(min_length=1)
    gap: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_inputs(self) -> BreakOverRequest:
        folded = [value.casefold() for value in self.cutter_handles]
        if self.target_handle.casefold() in folded or len(folded) != len(set(folded)):
            raise ValueError("BRO target and cutter handles must be distinct")
        return self


class BreakOverPlan(Batch19bPlan):
    command_alias: str = "BRO"
    legacy_symbol: str = "xiBreakO"
    semantic_evidence: str = (
        "shortcut description: break an object at objects over it; intersections are caller-supplied"
    )
    evidence_level: EvidenceLevel = EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY
    target_handle: str
    cutter_handles: tuple[str, ...]
    breaks: tuple[BreakGapSpec, ...]


def plan_break_over(request: BreakOverRequest) -> BreakOverPlan:
    return BreakOverPlan(
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        target_handle=request.target_handle,
        cutter_handles=request.cutter_handles,
        breaks=tuple(
            BreakGapSpec(source_handle=request.target_handle, center=point, gap=request.gap)
            for point in request.intersection_points
        ),
    )


class CircleKeep(StrEnum):
    ARC_START_TO_END = "arc_start_to_end"
    COMPLEMENT = "complement"


class CircleBreakRequest(ContractRequest):
    source_handle: str = Field(min_length=1)
    center: Point3D
    radius: float = Field(gt=0)
    start_angle_degrees: float
    end_angle_degrees: float
    keep: CircleKeep
    target_layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_angles(self) -> CircleBreakRequest:
        if (self.end_angle_degrees - self.start_angle_degrees) % 360 == 0:
            raise ValueError("CB break angles must define a non-full arc")
        return self


class ArcCreateSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    center: Point3D
    radius: float
    start_angle_degrees: float
    end_angle_degrees: float
    layer: str


class CircleBreakPlan(Batch19bPlan):
    command_alias: str = "CB"
    legacy_symbol: str = "xiCircleBreak"
    semantic_evidence: str = "shortcut description only: break circle; explicit kept-arc policy required"
    evidence_level: EvidenceLevel = EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY
    create_arc: ArcCreateSpec
    delete_handles: tuple[str, ...]


def plan_circle_break(request: CircleBreakRequest) -> CircleBreakPlan:
    start, end = request.start_angle_degrees, request.end_angle_degrees
    if request.keep is CircleKeep.COMPLEMENT:
        start, end = end, start + 360
    return CircleBreakPlan(
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        create_arc=ArcCreateSpec(
            center=request.center,
            radius=request.radius,
            start_angle_degrees=start,
            end_angle_degrees=end,
            layer=request.target_layer,
        ),
        delete_handles=(request.source_handle,),
    )


class CandidateKind(StrEnum):
    PRIMITIVE = "primitive"
    BLOCK_REFERENCE = "block_reference"
    HATCH = "hatch"
    SOLID = "solid"


class CutCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    kind: CandidateKind
    entirely_inside: bool
    locked_layer: bool = False
    is_xref: bool = False


class CutterRequest(ContractRequest):
    boundary_handle: str = Field(min_length=1)
    candidates: tuple[CutCandidate, ...]
    include_locked: bool
    delete_all_inside: bool
    explode_blocks: bool
    explode_hatches: bool
    convert_solids_to_hatch: bool
    hatch_pattern: str = Field(min_length=1)
    hatch_scale: float = Field(gt=0)
    hatch_angle_degrees: float

    @model_validator(mode="after")
    def validate_candidates(self) -> CutterRequest:
        handles = [item.handle.casefold() for item in self.candidates]
        if self.boundary_handle.casefold() in handles or len(handles) != len(set(handles)):
            raise ValueError("CUT boundary and candidate handles must be distinct")
        return self


class CutterPlan(Batch19bPlan):
    command_alias: str = "CUT"
    legacy_symbol: str = "xiCutter"
    semantic_evidence: str = "current/frozen shortcut plus ACAD_xi0413_d.01.dcl and xiConfig /xiCutter"
    evidence_level: EvidenceLevel = EvidenceLevel.DCL_AND_CONFIG_RECOVERED
    boundary_handle: str
    delete_handles: tuple[str, ...]
    explode_block_handles: tuple[str, ...]
    explode_hatch_handles: tuple[str, ...]
    solid_to_hatch_handles: tuple[str, ...]
    hatch_pattern: str
    hatch_scale: float
    hatch_angle_degrees: float
    containment_preclassified_by_caller: bool = True


def plan_cutter(request: CutterRequest) -> CutterPlan:
    usable = tuple(
        item
        for item in request.candidates
        if item.entirely_inside and not item.is_xref and (request.include_locked or not item.locked_layer)
    )
    return CutterPlan(
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        boundary_handle=request.boundary_handle,
        delete_handles=tuple(item.handle for item in usable) if request.delete_all_inside else (),
        explode_block_handles=tuple(
            item.handle for item in usable if request.explode_blocks and item.kind is CandidateKind.BLOCK_REFERENCE
        ),
        explode_hatch_handles=tuple(
            item.handle for item in usable if request.explode_hatches and item.kind is CandidateKind.HATCH
        ),
        solid_to_hatch_handles=tuple(
            item.handle for item in usable if request.convert_solids_to_hatch and item.kind is CandidateKind.SOLID
        ),
        hatch_pattern=request.hatch_pattern,
        hatch_scale=request.hatch_scale,
        hatch_angle_degrees=request.hatch_angle_degrees,
    )


class CurveSample(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_entity_type: str = Field(min_length=1)
    sampled_vertices: tuple[Point3D, ...] = Field(min_length=2)
    layer: str = Field(min_length=1)
    closed: bool = False


class DivideToPolylineRequest(ContractRequest):
    curves: tuple[CurveSample, ...] = Field(min_length=1)
    max_chord_error: float = Field(gt=0)
    source_disposition: SourceDisposition

    @model_validator(mode="after")
    def validate_curves(self) -> DivideToPolylineRequest:
        handles = [curve.source_handle.casefold() for curve in self.curves]
        if len(handles) != len(set(handles)):
            raise ValueError("DTP source handles must be unique")
        return self


class SegmentCreateSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    start: Point3D
    end: Point3D
    layer: str


class DivideToPolylinePlan(Batch19bPlan):
    command_alias: str = "DTP"
    legacy_symbol: str = "xiDivideToPoly"
    semantic_evidence: str = "shortcut description only: divide curves into lines; caller supplies sampled vertices"
    evidence_level: EvidenceLevel = EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY
    creates: tuple[SegmentCreateSpec, ...]
    delete_handles: tuple[str, ...]
    max_chord_error: float


def plan_divide_to_polyline(request: DivideToPolylineRequest) -> DivideToPolylinePlan:
    creates = []
    for curve in request.curves:
        vertices = curve.sampled_vertices + ((curve.sampled_vertices[0],) if curve.closed else ())
        creates.extend(
            SegmentCreateSpec(source_handle=curve.source_handle, start=start, end=end, layer=curve.layer)
            for start, end in zip(vertices, vertices[1:], strict=False)
            if start != end
        )
    return DivideToPolylinePlan(
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        creates=tuple(creates),
        delete_handles=(
            tuple(curve.source_handle for curve in request.curves)
            if request.source_disposition is SourceDisposition.REPLACE
            else ()
        ),
        max_chord_error=request.max_chord_error,
    )


def register_headless_core_batch19b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 19B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    tools = (
        ("xicad_plan_bat", plan_break_and_text),
        ("xicad_plan_bb", plan_break_to_current),
        ("xicad_plan_bro", plan_break_over),
        ("xicad_plan_cb", plan_circle_break),
        ("xicad_plan_cut", plan_cutter),
        ("xicad_plan_dtp", plan_divide_to_polyline),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
