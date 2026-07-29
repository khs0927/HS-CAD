"""Evidence-bounded dialog-free planners for xiCAD batch 26B."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from itertools import pairwise
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


class EvidenceLevel(StrEnum):
    SHORTCUT_ONLY_EXPLICIT_RESULT = "shortcut_only_explicit_result_not_legacy_equivalent"
    SHORTCUT_ONLY_EXPLICIT_POLICY = "shortcut_only_explicit_policy_not_legacy_equivalent"


class ContractRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    document_id: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"dry_run", "approval"})
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    @model_validator(mode="after")
    def validate_approval(self) -> ContractRequest:
        if not self.dry_run and (
            not self.approval.approved or self.approval.fingerprint != self.fingerprint()
        ):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch26BPlan(BaseModel):
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


class PolylineSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    vertices: tuple[Point3D, ...] = Field(min_length=2)
    closed: bool
    geometry_revision: str = Field(min_length=1)


class ProposedPolyline(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    vertices: tuple[Point3D, ...] = Field(min_length=2)
    closed: bool
    layer: str = Field(min_length=1)
    constant_width: float | None = Field(default=None, gt=0)


class PolylineWidthResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    source_handle: str = Field(min_length=1)
    requested_width: float = Field(gt=0)
    wide_polyline: ProposedPolyline
    exact_outline_loops: tuple[ProposedPolyline, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_width_and_outlines(self) -> PolylineWidthResult:
        if self.wide_polyline.constant_width != self.requested_width:
            raise ValueError("PWD wide polyline must carry the exact requested width")
        if any(not outline.closed for outline in self.exact_outline_loops):
            raise ValueError("PWD exact outline results must be closed")
        return self


class PolylineWidthOutlineRequest(ContractRequest):
    sources: tuple[PolylineSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[PolylineWidthResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_one_result_per_source(self) -> PolylineWidthOutlineRequest:
        sources = [item.handle.casefold() for item in self.sources]
        results = [item.source_handle.casefold() for item in self.exact_results]
        if len(set(sources)) != len(sources) or len(set(results)) != len(results) or set(sources) != set(results):
            raise ValueError("PWD requires one unique exact result per source snapshot")
        return self


class PolylineWidthOutlinePlan(Batch26BPlan):
    sources: tuple[PolylineSnapshot, ...]
    results: tuple[PolylineWidthResult, ...]


def plan_polyline_width_outline(request: PolylineWidthOutlineRequest) -> PolylineWidthOutlinePlan:
    return PolylineWidthOutlinePlan(
        command_alias="PWD",
        legacy_symbol="xiPlineWidth",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify polyline width plus outline drawing",
        semantic_gaps=(
            "eligible polyline types, joins, caps, offsets, and source treatment are compiled",
            "caller supplies the exact wide polyline and every closed outline loop",
            "the explicit result contract does not claim legacy equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        sources=request.sources,
        results=request.exact_results,
    )


class ThreePointRectangleRequest(ContractRequest):
    picked_points: tuple[Point3D, Point3D, Point3D]
    exact_rectangle: ProposedPolyline

    @model_validator(mode="after")
    def validate_exact_rectangle(self) -> ThreePointRectangleRequest:
        if not self.exact_rectangle.closed or len(self.exact_rectangle.vertices) != 4:
            raise ValueError("R3 exact result must be a four-vertex closed polyline")
        if len({(point.x, point.y, point.z) for point in self.picked_points}) != 3:
            raise ValueError("R3 picked points must be distinct")
        return self


class ThreePointRectanglePlan(Batch26BPlan):
    picked_points: tuple[Point3D, Point3D, Point3D]
    rectangle: ProposedPolyline


def plan_three_point_rectangle(request: ThreePointRectangleRequest) -> ThreePointRectanglePlan:
    return ThreePointRectanglePlan(
        command_alias="R3",
        legacy_symbol="xiR3P",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify drawing a rectangle from three points",
        semantic_gaps=(
            "point order, orthogonal projection, elevation, and rectangle entity type are compiled",
            "caller supplies all four exact result vertices rather than relying on inferred point semantics",
            "the explicit result contract does not claim legacy equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        picked_points=request.picked_points,
        rectangle=request.exact_rectangle,
    )


class PrimitiveKind(StrEnum):
    LINE = "line"
    ARC = "arc"
    POLYLINE = "polyline"
    SPLINE = "spline"


class ProposedCurvePrimitive(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: PrimitiveKind
    exact_control_points: tuple[Point3D, ...] = Field(min_length=2)
    layer: str = Field(min_length=1)
    closed: bool = False


class RoundSurfaceRequest(ContractRequest):
    anchor_points: tuple[Point3D, ...] = Field(min_length=2)
    exact_components: tuple[ProposedCurvePrimitive, ...] = Field(min_length=1)


class RoundSurfacePlan(Batch26BPlan):
    anchor_points: tuple[Point3D, ...]
    components: tuple[ProposedCurvePrimitive, ...]


def plan_round_surface(request: RoundSurfaceRequest) -> RoundSurfacePlan:
    return RoundSurfacePlan(
        command_alias="RND",
        legacy_symbol="xiRound",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify expressing a curved surface",
        semantic_gaps=(
            "the shortcut description does not define the curve construction, view convention, or component count",
            "caller supplies exact typed curve components and control points",
            "the explicit result contract does not claim legacy equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        anchor_points=request.anchor_points,
        components=request.exact_components,
    )


class SolidRectangleRequest(ContractRequest):
    picked_points: tuple[Point3D, ...] = Field(min_length=2)
    exact_solid_vertices: tuple[Point3D, Point3D, Point3D, Point3D]
    layer: str = Field(min_length=1)
    color_index: int | None = Field(default=None, ge=0, le=256)

    @model_validator(mode="after")
    def validate_solid(self) -> SolidRectangleRequest:
        if len({(point.x, point.y, point.z) for point in self.exact_solid_vertices}) != 4:
            raise ValueError("RS exact solid vertices must be distinct")
        return self


class SolidRectanglePlan(Batch26BPlan):
    picked_points: tuple[Point3D, ...]
    solid_vertices: tuple[Point3D, Point3D, Point3D, Point3D]
    layer: str
    color_index: int | None


def plan_solid_rectangle(request: SolidRectangleRequest) -> SolidRectanglePlan:
    return SolidRectanglePlan(
        command_alias="RS",
        legacy_symbol="xiSolidBox",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify drawing a rectangular solid box",
        semantic_gaps=(
            "point acquisition, vertex order, SOLID versus hatch implementation, color, and layer defaults are compiled",
            "caller supplies the exact four SOLID vertices and explicit properties",
            "the explicit result contract does not claim legacy equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        picked_points=request.picked_points,
        solid_vertices=request.exact_solid_vertices,
        layer=request.layer,
        color_index=request.color_index,
    )


class UnfoldedPolylineResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    exact_vertices: tuple[Point3D, ...] = Field(min_length=2)
    layer: str = Field(min_length=1)


class UnfoldPolylineRequest(ContractRequest):
    sources: tuple[PolylineSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[UnfoldedPolylineResult, ...] = Field(min_length=1)
    length_tolerance: float = Field(default=1e-8, ge=0)

    @model_validator(mode="after")
    def validate_unfolded_lengths(self) -> UnfoldPolylineRequest:
        sources = {item.handle.casefold(): item for item in self.sources}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if len(sources) != len(self.sources) or len(results) != len(self.exact_results) or sources.keys() != results.keys():
            raise ValueError("UFD requires one unique exact result per source snapshot")
        for key, source in sources.items():
            result = results[key]
            if len(source.vertices) != len(result.exact_vertices):
                raise ValueError("UFD explicit policy preserves the source vertex count")
            source_lengths = tuple(_distance(a, b) for a, b in pairwise(source.vertices))
            result_lengths = tuple(_distance(a, b) for a, b in pairwise(result.exact_vertices))
            if any(abs(a - b) > self.length_tolerance for a, b in zip(source_lengths, result_lengths, strict=True)):
                raise ValueError("UFD explicit result must preserve each source segment length")
        return self


def _distance(a: Point3D, b: Point3D) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


class UnfoldPolylinePlan(Batch26BPlan):
    sources: tuple[PolylineSnapshot, ...]
    results: tuple[UnfoldedPolylineResult, ...]
    length_tolerance: float


def plan_unfold_polyline(request: UnfoldPolylineRequest) -> UnfoldPolylinePlan:
    return UnfoldPolylinePlan(
        command_alias="UFD",
        legacy_symbol="xiUnfoldPoly",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify unfolding a polyline",
        semantic_gaps=(
            "unfold direction, base point, arc/bulge treatment, closed-polyline seam, and source treatment are compiled",
            "the explicit policy preserves ordered straight-segment lengths in caller-supplied result vertices",
            "the explicit policy does not claim legacy equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        sources=request.sources,
        results=request.exact_results,
        length_tolerance=request.length_tolerance,
    )


class VSymbolRequest(ContractRequest):
    exact_vertices: tuple[Point3D, Point3D, Point3D]
    layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_v_shape(self) -> VSymbolRequest:
        left, tip, right = self.exact_vertices
        if len({(point.x, point.y, point.z) for point in self.exact_vertices}) != 3:
            raise ValueError("V exact vertices must be distinct")
        cross = (tip.x - left.x) * (right.y - left.y) - (tip.y - left.y) * (right.x - left.x)
        if math.isclose(cross, 0.0, abs_tol=1e-12):
            raise ValueError("V exact vertices must form two non-collinear legs")
        return self


class VSymbolPlan(Batch26BPlan):
    vertices: tuple[Point3D, Point3D, Point3D]
    layer: str


def plan_v_symbol(request: VSymbolRequest) -> VSymbolPlan:
    return VSymbolPlan(
        command_alias="V",
        legacy_symbol="xiV",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify drawing a V symbol",
        semantic_gaps=(
            "insertion convention, size, angle, orientation, entity type, and layer defaults are compiled",
            "caller supplies the exact left-tip-right vertices and layer",
            "the explicit result contract does not claim legacy equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT,
        vertices=request.exact_vertices,
        layer=request.layer,
    )


def register_headless_core_batch26b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 26B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_pwd", plan_polyline_width_outline),
        ("xicad_plan_r3", plan_three_point_rectangle),
        ("xicad_plan_rnd", plan_round_surface),
        ("xicad_plan_rs", plan_solid_rectangle),
        ("xicad_plan_ufd", plan_unfold_polyline),
        ("xicad_plan_v", plan_v_symbol),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
