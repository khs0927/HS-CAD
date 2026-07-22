"""Guarded topology contracts for shortcut-only xiCAD cut commands.

No DCL, configuration, or readable source implementation was found for this
batch.  The planners therefore validate caller-supplied result geometry; they
do not invent a legacy fillet/trim algorithm.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval fingerprint")


class CutAlias(StrEnum):
    FE = "FE"
    FM = "FM"
    FR = "FR"
    FT = "FT"
    FX = "FX"
    XT = "XT"


SYMBOLS = {
    CutAlias.FE: "xiFilletExtend",
    CutAlias.FM: "xiFilletMulti",
    CutAlias.FR: "xiFilletRadious",
    CutAlias.FT: "xiFilletT",
    CutAlias.FX: "xiFilletX",
    CutAlias.XT: "xiXT",
}

DESCRIPTIONS = {
    CutAlias.FE: "길이 남기고 모따기",
    CutAlias.FM: "여러 모서리 정리",
    CutAlias.FR: "곡면 모서리 벽체 정리",
    CutAlias.FT: "T 형태 벽체 정리",
    CutAlias.FX: "X 형태 벽체 정리",
    CutAlias.XT: "끊기와 연장을 한번에..",
}


class CurveKind(StrEnum):
    LINE = "line"
    ARC = "arc"
    LWPOLYLINE = "lwpolyline"


class CurveSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    kind: CurveKind
    vertices: tuple[Point3D, ...] = Field(min_length=2)
    layer: str = Field(min_length=1)
    is_xref: bool = False
    locked_layer: bool = False


class EditRole(StrEnum):
    TRIM = "trim"
    EXTEND = "extend"
    BREAK = "break"
    REPLACE = "replace"


class ProposedCurveEdit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    role: EditRole
    output_parts: tuple[tuple[Point3D, ...], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_parts(self) -> ProposedCurveEdit:
        if any(len(part) < 2 for part in self.output_parts):
            raise ValueError("each proposed curve part requires at least two vertices")
        if self.role is EditRole.BREAK and len(self.output_parts) < 2:
            raise ValueError("break edit requires at least two output parts")
        return self


class IntersectionEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    point: Point3D
    participating_handles: tuple[str, ...] = Field(min_length=2)


class CutRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    alias: CutAlias
    source_handles: tuple[str, ...] = Field(min_length=2)
    intersections: tuple[IntersectionEvidence, ...] = Field(min_length=1)
    proposed_edits: tuple[ProposedCurveEdit, ...] = Field(min_length=1)
    retained_length: float | None = Field(default=None, ge=0)
    wall_radius: float | None = Field(default=None, gt=0)
    topology_tolerance: float = Field(gt=0)
    delete_originals: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> CutRequest:
        folded = [handle.casefold() for handle in self.source_handles]
        if len(folded) != len(set(folded)):
            raise ValueError(f"{self.alias} source handles must be unique")
        expected = {CutAlias.FE: 2, CutAlias.FR: 2, CutAlias.FT: 3, CutAlias.FX: 4}
        if self.alias in expected and len(self.source_handles) != expected[self.alias]:
            raise ValueError(f"{self.alias} requires exactly {expected[self.alias]} source curves")
        if self.alias is CutAlias.FM and len(self.source_handles) < 2:
            raise ValueError("FM requires at least two source curves")
        if self.alias is CutAlias.FE and self.retained_length is None:
            raise ValueError("FE requires retained_length")
        if self.alias is CutAlias.FR and self.wall_radius is None:
            raise ValueError("FR requires wall_radius")
        if self.alias is CutAlias.XT:
            roles = {edit.role for edit in self.proposed_edits}
            if EditRole.BREAK not in roles or EditRole.EXTEND not in roles:
                raise ValueError("XT requires explicit break and extend edits")
        sources = set(folded)
        if any(edit.source_handle.casefold() not in sources for edit in self.proposed_edits):
            raise ValueError("proposed edit must reference a source handle")
        if any(
            any(handle.casefold() not in sources for handle in item.participating_handles)
            for item in self.intersections
        ):
            raise ValueError("intersection evidence must reference source handles")
        _approval(self.dry_run, self.approval, self.alias.value)
        return self


class CutPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: CutAlias
    legacy_symbol: str
    document_id: str
    dry_run: bool
    semantic_evidence: str
    semantic_gaps: tuple[str, ...]
    validated_sources: tuple[CurveSnapshot, ...]
    intersections: tuple[IntersectionEvidence, ...]
    proposed_edits: tuple[ProposedCurveEdit, ...]
    delete_handles: tuple[str, ...]
    retained_length: float | None
    wall_radius: float | None
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_cut(request: CutRequest, snapshots: tuple[CurveSnapshot, ...]) -> CutPlan:
    by = {item.handle.casefold(): item for item in snapshots}
    selected = []
    for handle in request.source_handles:
        item = by.get(handle.casefold())
        if item is None or item.is_xref or item.locked_layer:
            raise ValueError(f"{request.alias} source unavailable: {handle}")
        selected.append(item)
    return CutPlan(
        command_alias=request.alias,
        legacy_symbol=SYMBOLS[request.alias],
        document_id=request.document_id,
        dry_run=request.dry_run,
        semantic_evidence=f"current+frozen xiShortkey: {DESCRIPTIONS[request.alias]}; no command-specific DCL/config/source found",
        semantic_gaps=(
            "legacy selection order",
            "intersection choice",
            "trim/extend side",
            "result entity/property behavior",
        ),
        validated_sources=tuple(selected),
        intersections=request.intersections,
        proposed_edits=request.proposed_edits,
        delete_handles=request.source_handles if request.delete_originals else (),
        retained_length=request.retained_length,
        wall_radius=request.wall_radius,
    )


def register_headless_core_batch20a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 20A Guarded Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    def register(alias: CutAlias):
        return mcp.tool(name=f"xicad_plan_{alias.value.lower()}", annotations=annotations)

    @register(CutAlias.FE)
    def fe_tool(request: CutRequest, snapshots: tuple[CurveSnapshot, ...]) -> CutPlan:
        if request.alias is not CutAlias.FE:
            raise ValueError("FE tool requires alias=FE")
        return plan_cut(request, snapshots)

    @register(CutAlias.FM)
    def fm_tool(request: CutRequest, snapshots: tuple[CurveSnapshot, ...]) -> CutPlan:
        if request.alias is not CutAlias.FM:
            raise ValueError("FM tool requires alias=FM")
        return plan_cut(request, snapshots)

    @register(CutAlias.FR)
    def fr_tool(request: CutRequest, snapshots: tuple[CurveSnapshot, ...]) -> CutPlan:
        if request.alias is not CutAlias.FR:
            raise ValueError("FR tool requires alias=FR")
        return plan_cut(request, snapshots)

    @register(CutAlias.FT)
    def ft_tool(request: CutRequest, snapshots: tuple[CurveSnapshot, ...]) -> CutPlan:
        if request.alias is not CutAlias.FT:
            raise ValueError("FT tool requires alias=FT")
        return plan_cut(request, snapshots)

    @register(CutAlias.FX)
    def fx_tool(request: CutRequest, snapshots: tuple[CurveSnapshot, ...]) -> CutPlan:
        if request.alias is not CutAlias.FX:
            raise ValueError("FX tool requires alias=FX")
        return plan_cut(request, snapshots)

    @register(CutAlias.XT)
    def xt_tool(request: CutRequest, snapshots: tuple[CurveSnapshot, ...]) -> CutPlan:
        if request.alias is not CutAlias.XT:
            raise ValueError("XT tool requires alias=XT")
        return plan_cut(request, snapshots)
