"""Evidence-bounded dialog-free planners for xiCAD batch 29B viewport commands."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D

DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


class EvidenceLevel(StrEnum):
    SHORTCUT_EXACT_RESULT = "shortcut_only_explicit_result_not_legacy_equivalent"


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
        if not self.dry_run and (not self.approval.approved or self.approval.fingerprint != self.fingerprint()):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch29BPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    semantic_evidence: str
    semantic_gaps: tuple[str, ...]
    evidence_level: EvidenceLevel = EvidenceLevel.SHORTCUT_EXACT_RESULT
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class EntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class ViewportSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    entity: EntitySnapshot
    layout_name: str = Field(min_length=1)
    layout_revision: str = Field(min_length=1)
    center: Point3D
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    display_locked: bool
    is_paper_viewport: bool = False


class ViewportResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_viewport: ViewportSnapshot
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


def _validate_viewport_results(
    sources: tuple[ViewportSnapshot, ...], results: tuple[ViewportResult, ...]
) -> None:
    source_map = {item.entity.handle.casefold(): item for item in sources}
    result_map = {item.source_handle.casefold(): item for item in results}
    if (
        len(source_map) != len(sources)
        or len(result_map) != len(results)
        or source_map.keys() != result_map.keys()
    ):
        raise ValueError("requires one unique explicit result per viewport snapshot")
    for key, source in source_map.items():
        result = result_map[key]
        if result.source_revision != source.entity.revision:
            raise ValueError("viewport result must cite the exact source revision")
        if result.exact_viewport.entity.handle.casefold() != key:
            raise ValueError("viewport result must preserve the source handle")


class ViewportAlignRequest(ContractRequest):
    viewports: tuple[ViewportSnapshot, ...] = Field(min_length=2)
    exact_results: tuple[ViewportResult, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_results(self) -> ViewportAlignRequest:
        _validate_viewport_results(self.viewports, self.exact_results)
        if any(item.is_paper_viewport for item in self.viewports):
            raise ValueError("VA does not accept the layout paper viewport")
        return self


class ViewportAlignPlan(Batch29BPlan):
    viewports: tuple[ViewportSnapshot, ...]
    results: tuple[ViewportResult, ...]


def plan_viewport_align(request: ViewportAlignRequest) -> ViewportAlignPlan:
    return ViewportAlignPlan(
        command_alias="VA",
        legacy_symbol="xiVportAlign",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and menus identify vertically aligning viewports",
        semantic_gaps=(
            "alignment anchor, center/edge rule, selection order, and view transformation are compiled",
            "caller supplies the complete exact result for every versioned viewport",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        viewports=request.viewports,
        results=request.exact_results,
    )


class GeneratedEntityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_entities: tuple[EntitySnapshot, ...] = Field(min_length=1)
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


class ViewportGuideLineRequest(ContractRequest):
    viewports: tuple[ViewportSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[GeneratedEntityResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> ViewportGuideLineRequest:
        sources = {item.entity.handle.casefold(): item for item in self.viewports}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if len(sources) != len(self.viewports) or len(results) != len(self.exact_results) or sources.keys() != results.keys():
            raise ValueError("VGL requires one unique explicit entity result per viewport")
        for key, source in sources.items():
            if results[key].source_revision != source.entity.revision:
                raise ValueError("VGL result must cite the exact viewport revision")
        return self


class ViewportGuideLinePlan(Batch29BPlan):
    viewports: tuple[ViewportSnapshot, ...]
    results: tuple[GeneratedEntityResult, ...]


def plan_viewport_guide_line(request: ViewportGuideLineRequest) -> ViewportGuideLinePlan:
    return ViewportGuideLinePlan(
        command_alias="VGL",
        legacy_symbol="xiVportGuideLine",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify drawing model-space outlines for paper-space viewport areas",
        semantic_gaps=(
            "paper-to-model transform, clipping boundary handling, entity type, layer, and properties are compiled",
            "caller supplies every exact generated model-space entity against versioned viewport sources",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        viewports=request.viewports,
        results=request.exact_results,
    )


class ViewportLockRequest(ContractRequest):
    viewports: tuple[ViewportSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[ViewportResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> ViewportLockRequest:
        _validate_viewport_results(self.viewports, self.exact_results)
        if any(item.is_paper_viewport for item in self.viewports):
            raise ValueError("viewport locking excludes the layout paper viewport")
        if any(not item.exact_viewport.display_locked for item in self.exact_results):
            raise ValueError("lock results must set display_locked true")
        return self


class ViewportLockPlan(Batch29BPlan):
    scope: str
    viewports: tuple[ViewportSnapshot, ...]
    results: tuple[ViewportResult, ...]


def _lock_plan(request: ViewportLockRequest, alias: str, symbol: str, scope: str) -> ViewportLockPlan:
    return ViewportLockPlan(
        command_alias=alias,
        legacy_symbol=symbol,
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence=(
            "current/frozen shortcuts and menus identify locking selected viewports"
            if scope == "selected"
            else "current/frozen shortcuts and menus identify locking all viewports"
        ),
        semantic_gaps=(
            "viewport enumeration, eligibility, hidden/layout scope, and already-locked handling are compiled",
            "caller supplies a complete exact locked result for each versioned viewport in the declared scope",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        scope=scope,
        viewports=request.viewports,
        results=request.exact_results,
    )


def plan_viewport_lock(request: ViewportLockRequest) -> ViewportLockPlan:
    return _lock_plan(request, "VL", "xiVpLock", "selected")


class AllViewportLockRequest(ViewportLockRequest):
    layout_name: str = Field(min_length=1)
    layout_revision: str = Field(min_length=1)
    complete_viewport_handles: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_complete_scope(self) -> AllViewportLockRequest:
        supplied = [item.casefold() for item in self.complete_viewport_handles]
        actual = [item.entity.handle.casefold() for item in self.viewports]
        if len(supplied) != len(set(supplied)) or set(supplied) != set(actual):
            raise ValueError("VLL requires the complete unique viewport handle set for the layout revision")
        if any(
            item.layout_name.casefold() != self.layout_name.casefold()
            or item.layout_revision != self.layout_revision
            for item in self.viewports
        ):
            raise ValueError("VLL viewports must belong to the exact declared layout revision")
        return self


def plan_all_viewports_lock(request: AllViewportLockRequest) -> ViewportLockPlan:
    return _lock_plan(request, "VLL", "xiVpLockAll", "all_in_layout_revision")


class ModelGeometrySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    entity: EntitySnapshot
    closed_boundary: bool


class ViewportCreationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_viewport: ViewportSnapshot
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


class ViewportMakeObjectRequest(ContractRequest):
    target_layout_name: str = Field(min_length=1)
    target_layout_revision: str = Field(min_length=1)
    model_geometry: tuple[ModelGeometrySnapshot, ...] = Field(min_length=1)
    exact_results: tuple[ViewportCreationResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> ViewportMakeObjectRequest:
        sources = {item.entity.handle.casefold(): item for item in self.model_geometry}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if len(sources) != len(self.model_geometry) or len(results) != len(self.exact_results) or sources.keys() != results.keys():
            raise ValueError("VMO requires one unique explicit viewport result per model-space source")
        for key, source in sources.items():
            result = results[key]
            if not source.closed_boundary:
                raise ValueError("VMO sources must explicitly be closed boundaries")
            if result.source_revision != source.entity.revision:
                raise ValueError("VMO result must cite the exact source revision")
            if (
                result.exact_viewport.layout_name.casefold() != self.target_layout_name.casefold()
                or result.exact_viewport.layout_revision != self.target_layout_revision
            ):
                raise ValueError("VMO result must target the exact declared layout revision")
        return self


class ViewportMakeObjectPlan(Batch29BPlan):
    target_layout_name: str
    target_layout_revision: str
    model_geometry: tuple[ModelGeometrySnapshot, ...]
    results: tuple[ViewportCreationResult, ...]


def plan_viewport_make_object(request: ViewportMakeObjectRequest) -> ViewportMakeObjectPlan:
    return ViewportMakeObjectPlan(
        command_alias="VMO",
        legacy_symbol="xiVportMakeObject",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts identify making paper-space viewports from model-space geometry",
        semantic_gaps=(
            "eligible geometry, coordinate transform, clipping, view target/scale, and source retention are compiled",
            "caller supplies one exact viewport result per closed versioned model-space boundary",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        target_layout_name=request.target_layout_name,
        target_layout_revision=request.target_layout_revision,
        model_geometry=request.model_geometry,
        results=request.exact_results,
    )


class ViewportLayerSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    viewport_handle: str = Field(min_length=1)
    viewport_revision: str = Field(min_length=1)
    layer_name: str = Field(min_length=1)
    layer_revision: str = Field(min_length=1)
    override_state_digest: str = Field(pattern=DIGEST_PATTERN)


class ViewportLayerResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    viewport_handle: str = Field(min_length=1)
    viewport_revision: str = Field(min_length=1)
    layer_name: str = Field(min_length=1)
    layer_revision: str = Field(min_length=1)
    exact_override_state_digest: str = Field(pattern=DIGEST_PATTERN)
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


class ViewportLayerPropertyRequest(ContractRequest):
    states: tuple[ViewportLayerSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[ViewportLayerResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> ViewportLayerPropertyRequest:
        def key(item: ViewportLayerSnapshot | ViewportLayerResult) -> tuple[str, str]:
            return item.viewport_handle.casefold(), item.layer_name.casefold()

        sources = {key(item): item for item in self.states}
        results = {key(item): item for item in self.exact_results}
        if len(sources) != len(self.states) or len(results) != len(self.exact_results) or sources.keys() != results.keys():
            raise ValueError("VPP requires one unique explicit result per viewport-layer state")
        for item_key, source in sources.items():
            result = results[item_key]
            if result.viewport_revision != source.viewport_revision or result.layer_revision != source.layer_revision:
                raise ValueError("VPP result must cite the exact viewport and layer revisions")
        return self


class ViewportLayerPropertyPlan(Batch29BPlan):
    states: tuple[ViewportLayerSnapshot, ...]
    results: tuple[ViewportLayerResult, ...]


def plan_viewport_layer_property(request: ViewportLayerPropertyRequest) -> ViewportLayerPropertyPlan:
    return ViewportLayerPropertyPlan(
        command_alias="VPP",
        legacy_symbol="xiVPLayProperty",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and menus identify VPLAYER settings",
        semantic_gaps=(
            "property fields, override modes, layer/viewport selection, reset rules, and defaults are compiled",
            "caller supplies opaque before/after override-state digests bound to exact viewport and layer revisions",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        states=request.states,
        results=request.exact_results,
    )


def register_headless_core_batch29b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 29B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_va", plan_viewport_align),
        ("xicad_plan_vgl", plan_viewport_guide_line),
        ("xicad_plan_vl", plan_viewport_lock),
        ("xicad_plan_vll", plan_all_viewports_lock),
        ("xicad_plan_vmo", plan_viewport_make_object),
        ("xicad_plan_vpp", plan_viewport_layer_property),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
