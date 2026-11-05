"""Evidence-bounded dialog-free planners for xiCAD batch 31A commands."""

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
    DCL_EXACT_RESULT = "dcl_backed_explicit_result_not_legacy_equivalent"
    HELP_EXACT_RESULT = "help_backed_explicit_result_not_legacy_equivalent"


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


class Batch31APlan(BaseModel):
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


def _base(
    request: ContractRequest,
    alias: str,
    symbol: str,
    evidence: str,
    gaps: tuple[str, ...],
    level: EvidenceLevel = EvidenceLevel.HELP_EXACT_RESULT,
) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "legacy_symbol": symbol,
        "document_id": request.document_id,
        "dry_run": request.dry_run,
        "request_fingerprint": request.fingerprint(),
        "semantic_evidence": evidence,
        "semantic_gaps": gaps,
        "evidence_level": level,
    }


class DocumentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    revision: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class DocumentResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_revision: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    result_digest: str = Field(pattern=DIGEST_PATTERN)
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


class PurgeOperation(StrEnum):
    CAD_PURGE_ALL = "cad_purge_all"
    REGISTERED_APPLICATIONS = "registered_applications"
    ZERO_LENGTH_ENTITIES = "zero_length_entities"
    EMPTY_TEXT = "empty_text"
    EMPTY_GROUPS = "empty_groups"
    UNUSED_SCALE_LIST = "unused_scale_list"
    UNUSED_LAYER_FILTERS = "unused_layer_filters"
    DGN_LINETYPES = "dgn_linetypes"
    GHOST_ENTITIES = "ghost_entities"
    DRAW_ORDER = "text_dimension_solid_hatch_draw_order"


class PurgeAllRequest(ContractRequest):
    source: DocumentSnapshot
    operations: tuple[PurgeOperation, ...] = Field(min_length=1)
    operation_manifest_digest: str = Field(pattern=DIGEST_PATTERN)
    exact_result: DocumentResult

    @model_validator(mode="after")
    def validate_result(self) -> PurgeAllRequest:
        if len(set(self.operations)) != len(self.operations):
            raise ValueError("PUA operations must be unique")
        if self.exact_result.source_revision != self.source.revision:
            raise ValueError("PUA result must cite the exact source revision")
        return self


class PurgeAllPlan(Batch31APlan):
    source: DocumentSnapshot
    operations: tuple[PurgeOperation, ...]
    operation_manifest_digest: str
    result: DocumentResult


def plan_purge_all(request: PurgeAllRequest) -> PurgeAllPlan:
    return PurgeAllPlan(
        **_base(
            request,
            "PUA",
            "xiPurgeAll",
            "current/frozen shortcuts, ZWCAD menu, and official help identify selectable final-drawing purge/cleanup operations",
            (
                "the active PUA dialog/config and compiled operation order, eligibility, SB ordering, and failure behavior were not recovered",
                "caller chooses explicit operations and supplies a revision-bound exact document result; the planner mutates nothing",
                "the help-backed explicit-result contract does not claim CAD equivalence",
            ),
        ),
        source=request.source,
        operations=request.operations,
        operation_manifest_digest=request.operation_manifest_digest,
        result=request.exact_result,
    )


class FrameSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    frame_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    frame_block_name: str = Field(min_length=1)
    geometry_digest: str = Field(pattern=DIGEST_PATTERN)


class FileArtifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: str = Field(min_length=1)
    content_digest: str = Field(pattern=DIGEST_PATTERN)
    byte_length: int = Field(ge=0)


class FrameExportResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    frame_id: str = Field(min_length=1)
    frame_revision: str = Field(min_length=1)
    exact_artifact: FileArtifact
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


class SaveSeparateRequest(ContractRequest):
    source: DocumentSnapshot
    output_folder: str = Field(min_length=1)
    frames: tuple[FrameSnapshot, ...] = Field(min_length=1)
    settings_manifest_digest: str = Field(pattern=DIGEST_PATTERN)
    exact_results: tuple[FrameExportResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> SaveSeparateRequest:
        frames = {item.frame_id.casefold(): item for item in self.frames}
        results = {item.frame_id.casefold(): item for item in self.exact_results}
        if (
            len(frames) != len(self.frames)
            or len(results) != len(self.exact_results)
            or frames.keys() != results.keys()
        ):
            raise ValueError("SVS requires one unique exact artifact per frame")
        paths = [item.exact_artifact.path.casefold() for item in self.exact_results]
        if len(paths) != len(set(paths)):
            raise ValueError("SVS artifact paths must be unique")
        folder = PureWindowsPath(self.output_folder)
        for key, frame in frames.items():
            result = results[key]
            if result.frame_revision != frame.revision:
                raise ValueError("SVS result must cite the exact frame revision")
            if PureWindowsPath(result.exact_artifact.path).parent != folder:
                raise ValueError("SVS artifacts must be located in the declared output folder")
        return self


class SaveSeparatePlan(Batch31APlan):
    source: DocumentSnapshot
    output_folder: str
    frames: tuple[FrameSnapshot, ...]
    settings_manifest_digest: str
    results: tuple[FrameExportResult, ...]


def plan_save_separate(request: SaveSeparateRequest) -> SaveSeparatePlan:
    return SaveSeparatePlan(
        **_base(
            request,
            "SVS",
            "xiSaveSep",
            "current/frozen shortcuts, ZWCAD menu, current multi-page DCL/xiConfig, and official help identify WBLOCK export of individual block-framed drawings",
            (
                "frame discovery, title parsing, ordering icons, filename normalization/collision numbering, selection expansion, xref binding, scaling, and WBLOCK serialization remain compiled",
                "caller supplies versioned frames, an opaque settings manifest, and content-addressed exact DWG artifacts; no files are written",
                "official help excludes one enclosing block and warns of a ZWCAD 120-frame limit, but runtime equivalence is unverified",
            ),
            EvidenceLevel.DCL_EXACT_RESULT,
        ),
        source=request.source,
        output_folder=request.output_folder,
        frames=request.frames,
        settings_manifest_digest=request.settings_manifest_digest,
        results=request.exact_results,
    )


class WorkingAxisSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    revision: str = Field(min_length=1)
    snap_angle_radians: float
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class WorkingAxisResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    source_revision: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    snap_angle_radians: float
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class AxisMode(StrEnum):
    ENTITY = "entity"
    ANGLE = "angle"
    SLOPE_PERCENT = "slope_percent"


class AxisResetRequest(ContractRequest):
    source: WorkingAxisSnapshot
    exact_result: WorkingAxisResult

    @model_validator(mode="after")
    def validate_result(self) -> AxisResetRequest:
        if self.exact_result.source_revision != self.source.revision:
            raise ValueError("A0 result must cite the exact source revision")
        if self.exact_result.snap_angle_radians != 0:
            raise ValueError("A0 exact result must reset SNAPANG to zero")
        return self


class AxisChangeRequest(ContractRequest):
    source: WorkingAxisSnapshot
    mode: AxisMode
    reference_entity_revision: str | None = Field(default=None, min_length=1)
    input_value: float | None = None
    exact_result: WorkingAxisResult

    @model_validator(mode="after")
    def validate_result(self) -> AxisChangeRequest:
        if self.exact_result.source_revision != self.source.revision:
            raise ValueError("A1 result must cite the exact source revision")
        if (self.mode == AxisMode.ENTITY) != (self.reference_entity_revision is not None):
            raise ValueError("A1 entity mode requires exactly one reference entity revision")
        if (self.mode != AxisMode.ENTITY) != (self.input_value is not None):
            raise ValueError("A1 angle/slope modes require exactly one numeric input")
        return self


class WorkingAxisPlan(Batch31APlan):
    source: WorkingAxisSnapshot
    mode: AxisMode
    result: WorkingAxisResult


def plan_axis_reset(request: AxisResetRequest) -> WorkingAxisPlan:
    return WorkingAxisPlan(
        **_base(request, "A0", "xiSNGP", "shortcut and official A1 help identify A0 as resetting SNAPANG to orthogonal zero", ("display refresh and OSNAP side effects remain compiled", "the planner validates an exact system-state result and changes no CAD variable")),
        source=request.source,
        mode=AxisMode.ANGLE,
        result=request.exact_result,
    )


def plan_axis_change(request: AxisChangeRequest) -> WorkingAxisPlan:
    return WorkingAxisPlan(
        **_base(request, "A1", "xiSSNG", "current/frozen shortcuts and official help identify SNAPANG acquisition from an entity, numeric angle, or slope percent", ("entity traversal inside polylines/blocks, angle units/sign normalization, prompts, and OSNAP handling remain compiled", "caller supplies the complete exact SNAPANG result; no angle is inferred")),
        source=request.source,
        mode=request.mode,
        result=request.exact_result,
    )


class EntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class CurrentSetting(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    exact_value: str = Field(min_length=1)


class CopyValueRequest(ContractRequest):
    source: EntitySnapshot
    exact_settings: tuple[CurrentSetting, ...] = Field(min_length=1)
    result_state_digest: str = Field(pattern=DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_settings(self) -> CopyValueRequest:
        names = [item.name.casefold() for item in self.exact_settings]
        if len(names) != len(set(names)):
            raise ValueError("CV exact setting names must be unique")
        allowed = {
            "text": {"textstyle", "textsize", "layer"},
            "mtext": {"textstyle", "textsize", "layer"},
            "dimension": {"dimstyle", "textstyle", "layer"},
            "circle": {"filletrad", "layer"},
            "arc": {"filletrad", "layer"},
            "polyline": {"thickness", "layer"},
            "hatch": {"hpname", "hpscale"},
        }
        kind = self.source.entity_type.casefold()
        if kind not in allowed or set(names) != allowed[kind]:
            raise ValueError("CV exact settings must match the documented entity-type mapping")
        return self


class CopyValuePlan(Batch31APlan):
    source: EntitySnapshot
    settings: tuple[CurrentSetting, ...]
    result_state_digest: str


def plan_copy_value(request: CopyValueRequest) -> CopyValuePlan:
    return CopyValuePlan(
        **_base(request, "CV", "xiCopyValue", "current/frozen shortcuts, ZWCAD menu, and official help define exact current-value mappings for text, dimensions, circles/arcs, polylines, and hatches", ("entity subtype aliases, annotative styles, unavailable resources, units, and transaction ordering remain compiled", "caller supplies every documented exact setting value and a resulting environment digest")),
        source=request.source,
        settings=request.exact_settings,
        result_state_digest=request.result_state_digest,
    )


class ExactGeometryResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    result_id: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


def _validate_geometry(results: tuple[ExactGeometryResult, ...]) -> None:
    identities = [item.result_id.casefold() for item in results]
    if len(identities) != len(set(identities)):
        raise ValueError("exact geometry result identities must be unique")


class ElevationMarkRequest(ContractRequest):
    layer: str = Field(min_length=1)
    text_style: str = Field(min_length=1)
    prefix: str
    text_height: float = Field(gt=0)
    decimal_places: int = Field(ge=0, le=12)
    first_display_value: str = Field(min_length=1)
    insertion_points: tuple[Point3D, ...] = Field(min_length=1)
    settings_revision: str = Field(min_length=1)
    exact_results: tuple[ExactGeometryResult, ...] = Field(min_length=1)
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_results(self) -> ElevationMarkRequest:
        _validate_geometry(self.exact_results)
        return self


class HatchThicknessRequest(ContractRequest):
    first_point: Point3D
    second_point: Point3D
    thickness: float = Field(gt=0)
    hatch_pattern: str = Field(min_length=1)
    hatch_scale: float = Field(gt=0)
    settings_revision: str = Field(min_length=1)
    exact_results: tuple[ExactGeometryResult, ...] = Field(min_length=1)
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_results(self) -> HatchThicknessRequest:
        if self.first_point == self.second_point:
            raise ValueError("HT requires two distinct points")
        _validate_geometry(self.exact_results)
        return self


class KitchenInlineRequest(ContractRequest):
    points: tuple[Point3D, Point3D, Point3D]
    include_refrigerator: bool
    settings_revision: str = Field(min_length=1)
    exact_results: tuple[ExactGeometryResult, ...] = Field(min_length=1)
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_results(self) -> KitchenInlineRequest:
        if len({(point.x, point.y, point.z) for point in self.points}) != 3:
            raise ValueError("KCI requires three distinct points")
        _validate_geometry(self.exact_results)
        return self


class GeometryPlan(Batch31APlan):
    settings_revision: str
    results: tuple[ExactGeometryResult, ...]
    result_manifest_digest: str


def plan_elevation_mark(request: ElevationMarkRequest) -> GeometryPlan:
    return GeometryPlan(
        **_base(request, "ELM", "xiELMark", "current/frozen shortcuts, ZWCAD menu, local DCL, and official help identify continuous section/elevation level marks with layer/style/prefix/height/decimal/first-value settings", ("symbol geometry, scale multiplication, numeric increment, comma/leading-space formatting details, placement direction, and entity composition remain compiled", "caller supplies all exact entities for a versioned settings record"), EvidenceLevel.DCL_EXACT_RESULT),
        settings_revision=request.settings_revision,
        results=request.exact_results,
        result_manifest_digest=request.result_manifest_digest,
    )


def plan_hatch_thickness(request: HatchThicknessRequest) -> GeometryPlan:
    return GeometryPlan(
        **_base(request, "HT", "xiHatchThickness", "current/frozen shortcuts, ZWCAD menu, and official help identify a rectangular hatch of entered thickness along two selected points, with Earth as the documented default pattern", ("rectangle side choice, hatch origin/angle, associative boundary, skew handling, layer/properties, and settings dialog fields remain compiled", "caller supplies the complete exact boundary/hatch result; no geometry is inferred")),
        settings_revision=request.settings_revision,
        results=request.exact_results,
        result_manifest_digest=request.result_manifest_digest,
    )


def plan_kitchen_inline(request: KitchenInlineRequest) -> GeometryPlan:
    return GeometryPlan(
        **_base(request, "KCI", "xiKICI", "current/frozen shortcuts, ZWCAD menu, and official help identify an inline kitchen generated from three points with optional refrigerator and width-dependent composition", ("the meaning/order of three points, cabinet modules, thresholds, dimensions, layers, blocks, and refrigerator geometry remain compiled", "caller supplies the complete exact geometry result for an explicit settings revision")),
        settings_revision=request.settings_revision,
        results=request.exact_results,
        result_manifest_digest=request.result_manifest_digest,
    )


def register_headless_core_batch31a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 31A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_pua", plan_purge_all),
        ("xicad_plan_svs", plan_save_separate),
        ("xicad_plan_a0", plan_axis_reset),
        ("xicad_plan_a1", plan_axis_change),
        ("xicad_plan_cv", plan_copy_value),
        ("xicad_plan_elm", plan_elevation_mark),
        ("xicad_plan_ht", plan_hatch_thickness),
        ("xicad_plan_kci", plan_kitchen_inline),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
