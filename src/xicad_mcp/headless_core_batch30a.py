"""Evidence-bounded dialog-free planners for xiCAD batch 30A commands."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D

DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


class EvidenceLevel(StrEnum):
    SHORTCUT_EXACT_RESULT = "shortcut_only_explicit_result_not_legacy_equivalent"
    DCL_EXACT_RESULT = "dcl_inputs_explicit_result_not_legacy_equivalent"


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


class Batch30APlan(BaseModel):
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


class ViewportState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    entity: EntitySnapshot
    layout_name: str = Field(min_length=1)
    layout_revision: str = Field(min_length=1)
    center: Point3D
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    view_twist_radians: float
    display_locked: bool
    is_paper_viewport: bool = False


class ViewportResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_viewport: ViewportState
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


def _validate_viewport_results(
    sources: tuple[ViewportState, ...], results: tuple[ViewportResult, ...]
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
        if result.exact_viewport.is_paper_viewport:
            raise ValueError("layout paper viewport is not an eligible source or result")


class ViewportRotateRequest(ContractRequest):
    viewport: ViewportState
    exact_result: ViewportResult

    @model_validator(mode="after")
    def validate_result(self) -> ViewportRotateRequest:
        _validate_viewport_results((self.viewport,), (self.exact_result,))
        if self.viewport.is_paper_viewport:
            raise ValueError("VR does not accept the layout paper viewport")
        return self


class ViewportRotatePlan(Batch30APlan):
    viewport: ViewportState
    result: ViewportResult


def plan_viewport_rotate(request: ViewportRotateRequest) -> ViewportRotatePlan:
    return ViewportRotatePlan(
        command_alias="VR",
        legacy_symbol="xiVportViewRotate",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and platform menus identify rotating a viewport view",
        semantic_gaps=(
            "angle acquisition, sign, base point, view target, UCS, clipping, and lock handling are compiled",
            "caller supplies the complete exact result including view twist for one versioned viewport",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        viewport=request.viewport,
        result=request.exact_result,
    )


class LayoutSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)
    is_model_layout: bool = False
    contains_objects: bool = True


class FileArtifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: str = Field(min_length=1)
    content_digest: str = Field(pattern=DIGEST_PATTERN)
    byte_length: int = Field(ge=0)


class LayoutFileResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_layout_name: str = Field(min_length=1)
    source_layout_revision: str = Field(min_length=1)
    exact_artifact: FileArtifact
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


class LayoutToDrawingsRequest(ContractRequest):
    drawing_revision: str = Field(min_length=1)
    drawing_digest: str = Field(pattern=DIGEST_PATTERN)
    output_folder: str = Field(min_length=1)
    filename_prefix: str
    prefix_starts_with_drawing_name: bool
    overwrite_same_name: bool
    layouts: tuple[LayoutSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[LayoutFileResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> LayoutToDrawingsRequest:
        if any(ord(char) < 32 or char in '<>:"/\\|?*' for char in self.filename_prefix):
            raise ValueError("VSD filename prefix contains a Windows-invalid filename character")
        sources = {item.name.casefold(): item for item in self.layouts}
        results = {item.source_layout_name.casefold(): item for item in self.exact_results}
        if (
            len(sources) != len(self.layouts)
            or len(results) != len(self.exact_results)
            or sources.keys() != results.keys()
        ):
            raise ValueError("VSD requires one unique explicit output artifact per layout")
        if any(item.is_model_layout for item in self.layouts):
            raise ValueError("VSD contract accepts paper-space layouts only")
        if any(not item.contains_objects for item in self.layouts):
            raise ValueError("VSD help states that only layouts containing objects are eligible")
        paths = [item.exact_artifact.path.casefold() for item in self.exact_results]
        if len(paths) != len(set(paths)):
            raise ValueError("VSD output artifact paths must be unique")
        output_folder = PureWindowsPath(self.output_folder)
        if any(PureWindowsPath(item.exact_artifact.path).parent != output_folder for item in self.exact_results):
            raise ValueError("VSD output artifacts must be located in the declared output folder")
        for key, source in sources.items():
            if results[key].source_layout_revision != source.revision:
                raise ValueError("VSD result must cite the exact layout revision")
        return self


class LayoutToDrawingsPlan(Batch30APlan):
    drawing_revision: str
    drawing_digest: str
    output_folder: str
    filename_prefix: str
    prefix_starts_with_drawing_name: bool
    overwrite_same_name: bool
    layouts: tuple[LayoutSnapshot, ...]
    results: tuple[LayoutFileResult, ...]


def plan_layout_to_drawings(request: LayoutToDrawingsRequest) -> LayoutToDrawingsPlan:
    return LayoutToDrawingsPlan(
        command_alias="VSD",
        legacy_symbol="xiLayoutToDwgs",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and platform menus identify splitting layouts into individual drawing files",
        semantic_gaps=(
            "layout scope, model inclusion, destination naming, overwrite, purge, references, and save format are compiled",
            "caller supplies one content-addressed exact output artifact per versioned paper-space layout",
            "the planner validates a file manifest and never writes files",
        ),
        drawing_revision=request.drawing_revision,
        drawing_digest=request.drawing_digest,
        output_folder=request.output_folder,
        filename_prefix=request.filename_prefix,
        prefix_starts_with_drawing_name=request.prefix_starts_with_drawing_name,
        overwrite_same_name=request.overwrite_same_name,
        layouts=request.layouts,
        results=request.exact_results,
    )


class ViewportUnlockRequest(ContractRequest):
    viewports: tuple[ViewportState, ...] = Field(min_length=1)
    exact_results: tuple[ViewportResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> ViewportUnlockRequest:
        _validate_viewport_results(self.viewports, self.exact_results)
        if any(item.is_paper_viewport for item in self.viewports):
            raise ValueError("viewport unlocking excludes the layout paper viewport")
        if any(item.exact_viewport.display_locked for item in self.exact_results):
            raise ValueError("unlock results must set display_locked false")
        return self


class ViewportUnlockPlan(Batch30APlan):
    scope: str
    viewports: tuple[ViewportState, ...]
    results: tuple[ViewportResult, ...]


def _unlock_plan(
    request: ViewportUnlockRequest, alias: str, symbol: str, scope: str
) -> ViewportUnlockPlan:
    return ViewportUnlockPlan(
        command_alias=alias,
        legacy_symbol=symbol,
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence=(
            "current/frozen shortcuts identify unlocking selected viewports"
            if scope == "selected"
            else "current/frozen shortcuts and platform menus identify unlocking all viewports"
        ),
        semantic_gaps=(
            "viewport enumeration, eligibility, hidden/layout scope, and already-unlocked handling are compiled",
            "caller supplies a complete exact unlocked result for each versioned viewport in the declared scope",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        scope=scope,
        viewports=request.viewports,
        results=request.exact_results,
    )


def plan_viewport_unlock(request: ViewportUnlockRequest) -> ViewportUnlockPlan:
    return _unlock_plan(request, "VU", "xiVpUnlock", "selected")


class AllViewportUnlockRequest(ViewportUnlockRequest):
    layout_name: str = Field(min_length=1)
    layout_revision: str = Field(min_length=1)
    complete_viewport_handles: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_complete_scope(self) -> AllViewportUnlockRequest:
        supplied = [item.casefold() for item in self.complete_viewport_handles]
        actual = [item.entity.handle.casefold() for item in self.viewports]
        if len(supplied) != len(set(supplied)) or set(supplied) != set(actual):
            raise ValueError("VUU requires the complete unique viewport handle set for the layout revision")
        if any(
            item.layout_name.casefold() != self.layout_name.casefold()
            or item.layout_revision != self.layout_revision
            for item in self.viewports
        ):
            raise ValueError("VUU viewports must belong to the exact declared layout revision")
        return self


def plan_all_viewports_unlock(request: AllViewportUnlockRequest) -> ViewportUnlockPlan:
    return _unlock_plan(request, "VUU", "xiVpUnlockAll", "all_in_layout_revision")


class ExistingDestinationPolicy(StrEnum):
    REQUIRE_ABSENT = "require_absent"
    REQUIRE_MATCHING_DIGEST = "require_matching_digest"


class DrawingBackupRequest(ContractRequest):
    source_path: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    source_digest: str = Field(pattern=DIGEST_PATTERN)
    local_timestamp: str = Field(pattern=r"^\d{4}\.\d{4}\.\d{4}$")
    destination_policy: ExistingDestinationPolicy
    existing_destination_digest: str | None = Field(default=None, pattern=DIGEST_PATTERN)
    exact_backup: FileArtifact
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_backup(self) -> DrawingBackupRequest:
        if self.source_path.casefold() == self.exact_backup.path.casefold():
            raise ValueError("BAK source and backup paths must differ")
        if self.exact_backup.content_digest != self.source_digest:
            raise ValueError("BAK exact backup must preserve the source content digest")
        source = PureWindowsPath(self.source_path)
        destination = PureWindowsPath(self.exact_backup.path)
        expected_name = f"{source.stem}_{self.local_timestamp}{source.suffix}"
        if destination.parent != source.parent or destination.name.casefold() != expected_name.casefold():
            raise ValueError("BAK help requires current folder and filename_YYYY.MMDD.HHMM naming")
        if (
            self.destination_policy is ExistingDestinationPolicy.REQUIRE_MATCHING_DIGEST
            and self.existing_destination_digest is None
        ):
            raise ValueError("matching-digest policy requires an existing destination digest")
        if (
            self.destination_policy is ExistingDestinationPolicy.REQUIRE_MATCHING_DIGEST
            and self.existing_destination_digest != self.source_digest
        ):
            raise ValueError("existing destination digest must match the exact source digest")
        if (
            self.destination_policy is ExistingDestinationPolicy.REQUIRE_ABSENT
            and self.existing_destination_digest is not None
        ):
            raise ValueError("require-absent policy cannot include an existing destination digest")
        return self


class DrawingBackupPlan(Batch30APlan):
    source_path: str
    source_revision: str
    source_digest: str
    local_timestamp: str
    destination_policy: ExistingDestinationPolicy
    existing_destination_digest: str | None
    exact_backup: FileArtifact
    result_manifest_digest: str


def plan_drawing_backup(request: DrawingBackupRequest) -> DrawingBackupPlan:
    return DrawingBackupPlan(
        command_alias="BAK",
        legacy_symbol="xiDwgBackUp",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and platform menus identify saving a drawing backup",
        semantic_gaps=(
            "destination derivation, extension, overwrite prompt, save format, dependencies, and timestamp policy are compiled",
            "caller supplies source identity, destination policy, and a content-addressed exact backup artifact",
            "the planner validates a backup manifest and never writes files",
        ),
        source_path=request.source_path,
        source_revision=request.source_revision,
        source_digest=request.source_digest,
        local_timestamp=request.local_timestamp,
        destination_policy=request.destination_policy,
        existing_destination_digest=request.existing_destination_digest,
        exact_backup=request.exact_backup,
        result_manifest_digest=request.result_manifest_digest,
    )


class CorrectionEntityType(StrEnum):
    LINE = "LINE"
    LWPOLYLINE = "LWPOLYLINE"
    POLYLINE = "POLYLINE"
    INSERT = "INSERT"
    DIMENSION = "DIMENSION"
    TEXT = "TEXT"
    MTEXT = "MTEXT"
    CIRCLE = "CIRCLE"
    ARC = "ARC"
    ELLIPSE = "ELLIPSE"


class CorrectionScope(StrEnum):
    SCREEN_SELECTION = "screen_selection"
    DECLARED_DOCUMENT_SCOPE = "declared_document_scope"


class CorrectionEntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    entity_type: CorrectionEntityType
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class CorrectionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_entity: EntitySnapshot
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


class CorrectErrorRequest(ContractRequest):
    selection_scope: CorrectionScope
    reference_point: Point3D
    exact_corrected_reference_point: Point3D
    enabled_entity_types: frozenset[CorrectionEntityType] = Field(min_length=1)
    tolerance: float = Field(gt=0)
    correct_circle_arc_radius: bool
    entities: tuple[CorrectionEntitySnapshot, ...] = Field(min_length=1)
    exact_results: tuple[CorrectionResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> CorrectErrorRequest:
        sources = {item.handle.casefold(): item for item in self.entities}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if (
            len(sources) != len(self.entities)
            or len(results) != len(self.exact_results)
            or sources.keys() != results.keys()
        ):
            raise ValueError("CER requires one unique explicit result per entity snapshot")
        for key, source in sources.items():
            if source.entity_type not in self.enabled_entity_types:
                raise ValueError("CER entity type must be enabled by the DCL-derived filter")
            result = results[key]
            if result.source_revision != source.revision:
                raise ValueError("CER result must cite the exact source revision")
            if result.exact_entity.handle.casefold() != key:
                raise ValueError("CER result must preserve the source handle")
        return self


class CorrectErrorPlan(Batch30APlan):
    selection_scope: CorrectionScope
    reference_point: Point3D
    exact_corrected_reference_point: Point3D
    enabled_entity_types: frozenset[CorrectionEntityType]
    tolerance: float
    correct_circle_arc_radius: bool
    entities: tuple[CorrectionEntitySnapshot, ...]
    results: tuple[CorrectionResult, ...]


def plan_correct_error(request: CorrectErrorRequest) -> CorrectErrorPlan:
    return CorrectErrorPlan(
        command_alias="CER",
        legacy_symbol="xiCorrectError",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence=(
            "ACAD_xi0089_d.01.dcl exposes selection scope, ten entity filters, circle/arc radius correction, and tolerance"
        ),
        semantic_gaps=(
            "coordinate/radius quantization rule, topology handling, property preservation, and correction ordering are compiled",
            "caller supplies one complete exact corrected entity per versioned source",
            "DCL/config inputs are preserved without claiming the explicit results match the compiled algorithm",
        ),
        evidence_level=EvidenceLevel.DCL_EXACT_RESULT,
        selection_scope=request.selection_scope,
        reference_point=request.reference_point,
        exact_corrected_reference_point=request.exact_corrected_reference_point,
        enabled_entity_types=request.enabled_entity_types,
        tolerance=request.tolerance,
        correct_circle_arc_radius=request.correct_circle_arc_radius,
        entities=request.entities,
        results=request.exact_results,
    )


def register_headless_core_batch30a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 30A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_vr", plan_viewport_rotate),
        ("xicad_plan_vsd", plan_layout_to_drawings),
        ("xicad_plan_vu", plan_viewport_unlock),
        ("xicad_plan_vuu", plan_all_viewports_unlock),
        ("xicad_plan_bak", plan_drawing_backup),
        ("xicad_plan_cer", plan_correct_error),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
