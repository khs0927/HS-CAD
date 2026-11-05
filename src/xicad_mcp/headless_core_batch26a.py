"""Evidence-bounded dialog-free planners for xiCAD batch 26A.

The six commands are identified by current and frozen shortcut catalogs, but
their implementations are compiled and no command-specific DCL/config/data was
found.  Topology-changing planners therefore accept versioned source snapshots
and exact caller-supplied results; they never derive a join or vertex edit.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


class EvidenceLevel(StrEnum):
    SHORTCUT_ONLY_EXPLICIT_RESULT = "shortcut_only_explicit_result_not_legacy_equivalent"


class ContractRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    document_id: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"dry_run", "approval"})
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    @model_validator(mode="after")
    def validate_approval(self) -> ContractRequest:
        if not self.dry_run and (
            not self.approval.approved
            or self.approval.fingerprint != self.fingerprint()
        ):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch26APlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    semantic_evidence: str
    semantic_gaps: tuple[str, ...]
    evidence_level: EvidenceLevel = EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_RESULT
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class PolylineVertex(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    vertex_id: str = Field(min_length=1)
    point: Point3D
    bulge: float = 0
    start_width: float = Field(default=0, ge=0)
    end_width: float = Field(default=0, ge=0)


class PolylineSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    entity_type: str = Field(pattern="^(LWPOLYLINE|POLYLINE)$")
    geometry_revision: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    closed: bool
    vertices: tuple[PolylineVertex, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_vertices(self) -> PolylineSnapshot:
        ids = [item.vertex_id.casefold() for item in self.vertices]
        if len(ids) != len(set(ids)):
            raise ValueError("polyline snapshot vertex ids must be unique")
        return self


class ProposedPolylineResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    result_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=1)
    entity_type: str = Field(pattern="^(LWPOLYLINE|POLYLINE)$")
    layer: str = Field(min_length=1)
    closed: bool
    vertices: tuple[PolylineVertex, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_unique_references(self) -> ProposedPolylineResult:
        handles = [item.casefold() for item in self.source_handles]
        ids = [item.vertex_id.casefold() for item in self.vertices]
        if len(handles) != len(set(handles)):
            raise ValueError("result source handles must be unique")
        if len(ids) != len(set(ids)):
            raise ValueError("result vertex ids must be unique")
        return self


def _source_map(
    sources: tuple[PolylineSnapshot, ...], alias: str
) -> dict[str, PolylineSnapshot]:
    result = {item.handle.casefold(): item for item in sources}
    if len(result) != len(sources):
        raise ValueError(f"{alias} source handles must be unique")
    return result


def _vertex_ids(vertices: tuple[PolylineVertex, ...]) -> tuple[str, ...]:
    return tuple(item.vertex_id.casefold() for item in vertices)


class PolylineJoinRequest(ContractRequest):
    sources: tuple[PolylineSnapshot, ...] = Field(min_length=2)
    exact_result: ProposedPolylineResult
    delete_source_handles: tuple[str, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_exact_join(self) -> PolylineJoinRequest:
        sources = _source_map(self.sources, "PJ")
        expected = set(sources)
        result_sources = {item.casefold() for item in self.exact_result.source_handles}
        deletes = {item.casefold() for item in self.delete_source_handles}
        if result_sources != expected or deletes != expected:
            raise ValueError("PJ exact result and deletions must reference every source once")
        return self


class PolylineJoinPlan(Batch26APlan):
    sources: tuple[PolylineSnapshot, ...]
    exact_result: ProposedPolylineResult
    delete_source_handles: tuple[str, ...]


def plan_polyline_join(request: PolylineJoinRequest) -> PolylineJoinPlan:
    return PolylineJoinPlan(
        command_alias="PJ",
        legacy_symbol="xiPolylineJoin",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and CAD menus identify xiPolylineJoin as changing then joining polylines",
        semantic_gaps=(
            "no command-specific DCL/config/data/readable source was found",
            "join ordering, endpoint tolerance, curve conversion, and property retention are compiled",
            "the exact result and source deletions are caller supplied; no legacy equivalence is claimed",
        ),
        sources=request.sources,
        exact_result=request.exact_result,
        delete_source_handles=request.delete_source_handles,
    )


class SinglePolylineEditRequest(ContractRequest):
    source: PolylineSnapshot
    exact_result: ProposedPolylineResult

    def validate_single_result(self, alias: str) -> None:
        if tuple(item.casefold() for item in self.exact_result.source_handles) != (
            self.source.handle.casefold(),
        ):
            raise ValueError(f"{alias} exact result must reference only its source handle")


class VertexAddRequest(SinglePolylineEditRequest):
    @model_validator(mode="after")
    def validate_add(self) -> VertexAddRequest:
        self.validate_single_result("PV")
        before = _vertex_ids(self.source.vertices)
        after = _vertex_ids(self.exact_result.vertices)
        retained = tuple(item for item in after if item in set(before))
        if len(after) != len(before) + 1 or retained != before:
            raise ValueError("PV exact result must add exactly one vertex and retain source order")
        return self


class VertexRemoveCleanRequest(SinglePolylineEditRequest):
    @model_validator(mode="after")
    def validate_removal(self) -> VertexRemoveCleanRequest:
        self.validate_single_result("PVR")
        before = _vertex_ids(self.source.vertices)
        after = _vertex_ids(self.exact_result.vertices)
        if len(after) >= len(before) or tuple(item for item in before if item in set(after)) != after:
            raise ValueError("PVR exact result must remove vertices while retaining source order")
        return self


class VertexDeleteRequest(SinglePolylineEditRequest):
    @model_validator(mode="after")
    def validate_delete(self) -> VertexDeleteRequest:
        self.validate_single_result("PVV")
        before = _vertex_ids(self.source.vertices)
        after = _vertex_ids(self.exact_result.vertices)
        if len(after) != len(before) - 1 or tuple(item for item in before if item in set(after)) != after:
            raise ValueError("PVV exact result must delete exactly one vertex and retain source order")
        return self


class SinglePolylineEditPlan(Batch26APlan):
    source: PolylineSnapshot
    exact_result: ProposedPolylineResult


def _plan_single_edit(
    request: SinglePolylineEditRequest,
    alias: str,
    symbol: str,
    description: str,
) -> SinglePolylineEditPlan:
    return SinglePolylineEditPlan(
        command_alias=alias,
        legacy_symbol=symbol,
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence=f"current/frozen shortcuts and CAD menus identify {symbol} as {description}",
        semantic_gaps=(
            "no command-specific DCL/config/data/readable source was found",
            "selection, vertex eligibility, bulge/width interpolation, and tolerance behavior are compiled",
            "the versioned source and exact result are caller supplied; no legacy equivalence is claimed",
        ),
        source=request.source,
        exact_result=request.exact_result,
    )


def plan_vertex_add(request: VertexAddRequest) -> SinglePolylineEditPlan:
    return _plan_single_edit(request, "PV", "xiPlineVertexAdd", "adding a polyline vertex")


def plan_vertex_remove_clean(request: VertexRemoveCleanRequest) -> SinglePolylineEditPlan:
    return _plan_single_edit(request, "PVR", "xiPlineVertexRemove", "cleaning polyline vertices")


def plan_vertex_delete(request: VertexDeleteRequest) -> SinglePolylineEditPlan:
    return _plan_single_edit(request, "PVV", "xiPlineVertexV", "deleting a polyline vertex")


class ProposedVertexTableRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    vertex_id: str = Field(min_length=1)
    cells: tuple[str, ...] = Field(min_length=1)


class VertexListTableRequest(ContractRequest):
    sources: tuple[PolylineSnapshot, ...] = Field(min_length=1)
    columns: tuple[str, ...] = Field(min_length=1)
    exact_rows: tuple[ProposedVertexTableRow, ...] = Field(min_length=1)
    insertion_point: Point3D
    output_layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_exact_rows(self) -> VertexListTableRequest:
        sources = _source_map(self.sources, "PVL")
        expected = {
            (source.handle.casefold(), vertex.vertex_id.casefold())
            for source in sources.values()
            for vertex in source.vertices
        }
        actual = {
            (row.source_handle.casefold(), row.vertex_id.casefold())
            for row in self.exact_rows
        }
        if len(actual) != len(self.exact_rows) or actual != expected:
            raise ValueError("PVL requires one unique exact table row per source vertex")
        if any(len(row.cells) != len(self.columns) for row in self.exact_rows):
            raise ValueError("PVL row cell count must match the explicit columns")
        return self


class VertexListTablePlan(Batch26APlan):
    sources: tuple[PolylineSnapshot, ...]
    columns: tuple[str, ...]
    exact_rows: tuple[ProposedVertexTableRow, ...]
    insertion_point: Point3D
    output_layer: str
    text_height: float


def plan_vertex_list_table(request: VertexListTableRequest) -> VertexListTablePlan:
    return VertexListTablePlan(
        command_alias="PVL",
        legacy_symbol="xiPlineVertListTable",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and CAD menus identify xiPlineVertListTable as making a table from polyline vertices",
        semantic_gaps=(
            "no command-specific DCL/config/data/readable source was found",
            "legacy columns, coordinate system, formatting, ordering, and table geometry are compiled",
            "columns and exact rows are caller supplied; no legacy equivalence is claimed",
        ),
        sources=request.sources,
        columns=request.columns,
        exact_rows=request.exact_rows,
        insertion_point=request.insertion_point,
        output_layer=request.output_layer,
        text_height=request.text_height,
    )


class PolylineWidthRequest(ContractRequest):
    source: PolylineSnapshot
    exact_result: ProposedPolylineResult

    @model_validator(mode="after")
    def validate_width_only(self) -> PolylineWidthRequest:
        if tuple(item.casefold() for item in self.exact_result.source_handles) != (
            self.source.handle.casefold(),
        ):
            raise ValueError("PW exact result must reference only its source handle")
        if self.source.entity_type != self.exact_result.entity_type:
            raise ValueError("PW must preserve the polyline entity type")
        if self.source.layer != self.exact_result.layer or self.source.closed != self.exact_result.closed:
            raise ValueError("PW must preserve layer and closed state")
        before = self.source.vertices
        after = self.exact_result.vertices
        if len(before) != len(after):
            raise ValueError("PW must preserve vertex count")
        for old, new in zip(before, after, strict=True):
            if (
                old.vertex_id.casefold() != new.vertex_id.casefold()
                or old.point != new.point
                or old.bulge != new.bulge
            ):
                raise ValueError("PW may change only per-vertex start/end widths")
        return self


class PolylineWidthPlan(Batch26APlan):
    source: PolylineSnapshot
    exact_result: ProposedPolylineResult


def plan_polyline_width(request: PolylineWidthRequest) -> PolylineWidthPlan:
    return PolylineWidthPlan(
        command_alias="PW",
        legacy_symbol="xiPW",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and CAD menus identify xiPW as modifying polyline width",
        semantic_gaps=(
            "no command-specific DCL/config/data/readable source was found",
            "legacy uniform/segment width prompt, zero-width policy, and selection behavior are compiled",
            "exact per-vertex widths are caller supplied; no legacy equivalence is claimed",
        ),
        source=request.source,
        exact_result=request.exact_result,
    )


def register_headless_core_batch26a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 26A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_pj", plan_polyline_join),
        ("xicad_plan_pv", plan_vertex_add),
        ("xicad_plan_pvl", plan_vertex_list_table),
        ("xicad_plan_pvr", plan_vertex_remove_clean),
        ("xicad_plan_pvv", plan_vertex_delete),
        ("xicad_plan_pw", plan_polyline_width),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
