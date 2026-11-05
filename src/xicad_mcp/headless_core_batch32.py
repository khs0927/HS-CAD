"""Evidence-bounded dialog-free planners for the final xiCAD coverage aliases."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval

DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


class EvidenceLevel(StrEnum):
    DCL_HELP_WRAPPER = "dcl_help_wrapper_backed_not_legacy_equivalent"
    HELP_WRAPPER = "help_wrapper_backed_not_legacy_equivalent"
    HELP_RENAME = "help_rename_backed_not_runtime_equivalent"
    SHORTCUT_WRAPPER = "shortcut_wrapper_backed_explicit_result_only"
    PLATFORM_GUARD = "shortcut_platform_guard_only"


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


class Point3D(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    x: float
    y: float
    z: float = 0.0


class EntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class ExactEntityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    result_id: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class ExactChangeSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_revisions: tuple[str, ...] = Field(min_length=1)
    created_or_updated: tuple[ExactEntityResult, ...] = Field(min_length=1)
    erased_handles: tuple[str, ...] = ()
    manifest_digest: str = Field(pattern=DIGEST_PATTERN)

    @model_validator(mode="after")
    def unique_identifiers(self) -> ExactChangeSet:
        ids = [item.result_id.casefold() for item in self.created_or_updated]
        if len(ids) != len(set(ids)):
            raise ValueError("exact result ids must be unique")
        erased = [handle.casefold() for handle in self.erased_handles]
        if len(erased) != len(set(erased)):
            raise ValueError("erased handles must be unique")
        return self


class Batch32Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    current_alias: str
    current_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    evidence_level: EvidenceLevel
    semantic_evidence: str
    semantic_gaps: tuple[str, ...]
    exact_changes: ExactChangeSet | None = None
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def _base(
    request: ContractRequest,
    alias: str,
    legacy_symbol: str,
    current_alias: str,
    current_symbol: str,
    level: EvidenceLevel,
    evidence: str,
    gaps: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "legacy_symbol": legacy_symbol,
        "current_alias": current_alias,
        "current_symbol": current_symbol,
        "document_id": request.document_id,
        "dry_run": request.dry_run,
        "request_fingerprint": request.fingerprint(),
        "evidence_level": level,
        "semantic_evidence": evidence,
        "semantic_gaps": gaps,
    }


def _validate_changes(sources: tuple[EntitySnapshot, ...], changes: ExactChangeSet) -> None:
    revisions = tuple(item.revision for item in sources)
    if changes.source_revisions != revisions:
        raise ValueError("exact changes must cite every source revision in request order")


class CenterMode(StrEnum):
    SINGLE = "single_entity"
    PAIR = "entity_pair"
    MULTI = "multi_pair_detection"


class CenterlineRequest(ContractRequest):
    sources: tuple[EntitySnapshot, ...] = Field(min_length=1)
    mode: CenterMode
    create_polyline: bool
    extension_length: float = Field(ge=0)
    maximum_recognition_distance: float = Field(gt=0)
    output_layer: str = Field(min_length=1)
    exact_changes: ExactChangeSet

    @model_validator(mode="after")
    def validate_centerline(self) -> CenterlineRequest:
        if self.mode is CenterMode.SINGLE and len(self.sources) != 1:
            raise ValueError("single center mode requires exactly one entity")
        if self.mode is CenterMode.PAIR and len(self.sources) != 2:
            raise ValueError("pair center mode requires exactly two entities")
        if self.mode is CenterMode.MULTI and len(self.sources) < 2:
            raise ValueError("multi center mode requires at least two entities")
        _validate_changes(self.sources, self.exact_changes)
        return self


def plan_centerline(request: CenterlineRequest) -> Batch32Plan:
    return Batch32Plan(
        **_base(
            request,
            "CE",
            "xiCenter",
            "CEN",
            "xiCenter",
            EvidenceLevel.DCL_HELP_WRAPPER,
            "legacy/current shortcuts, compatibility wrapper, current DCL/config, and official CEN help",
            (
                "compiled pairing, center geometry, nested-reference traversal, and property rules are unavailable",
                "caller supplies complete revision-bound output; CAD equivalence remains unverified",
            ),
        ),
        exact_changes=request.exact_changes,
    )


class BreakMode(StrEnum):
    ONE_POINT = "one_point"
    TWO_POINT = "two_point"
    MULTIPLE_POINTS_ONE_CURVE = "multiple_points_one_curve"


class BreakMultiRequest(ContractRequest):
    sources: tuple[EntitySnapshot, ...] = Field(min_length=1)
    mode: BreakMode
    break_points: tuple[Point3D, ...] = Field(min_length=1)
    exact_changes: ExactChangeSet

    @model_validator(mode="after")
    def validate_break(self) -> BreakMultiRequest:
        if self.mode is BreakMode.ONE_POINT and len(self.break_points) != 1:
            raise ValueError("one-point break requires exactly one point")
        if self.mode is BreakMode.TWO_POINT and len(self.break_points) != 2:
            raise ValueError("two-point break requires exactly two points")
        if self.mode is BreakMode.MULTIPLE_POINTS_ONE_CURVE and len(self.sources) != 1:
            raise ValueError("multiple-point break accepts exactly one source curve")
        if self.mode is BreakMode.MULTIPLE_POINTS_ONE_CURVE and len(self.break_points) < 2:
            raise ValueError("multiple-point break requires at least two points")
        _validate_changes(self.sources, self.exact_changes)
        return self


def plan_break_multi(request: BreakMultiRequest) -> Batch32Plan:
    return Batch32Plan(
        **_base(
            request,
            "BBB",
            "xiBreakMulti",
            "B",
            "xiBreakMulti",
            EvidenceLevel.HELP_WRAPPER,
            "legacy/current shortcuts, compatibility wrapper, and official B help define three break modes",
            (
                "curve projection, tolerance, segment ordering, and unsupported curve behavior are compiled",
                "the exact replacement entities and erased handles must be supplied",
            ),
        ),
        exact_changes=request.exact_changes,
    )


class FilletLRequest(ContractRequest):
    sources: tuple[EntitySnapshot, ...] = Field(min_length=2)
    selection_corner_a: Point3D
    selection_corner_b: Point3D
    excluded_centerline_handles: tuple[str, ...] = ()
    exact_changes: ExactChangeSet

    @model_validator(mode="after")
    def validate_fillet(self) -> FilletLRequest:
        if self.selection_corner_a == self.selection_corner_b:
            raise ValueError("FF crossing selection corners must differ")
        source_handles = {item.handle.casefold() for item in self.sources}
        if not set(map(str.casefold, self.excluded_centerline_handles)) <= source_handles:
            raise ValueError("excluded centerlines must belong to the source selection")
        _validate_changes(self.sources, self.exact_changes)
        return self


def plan_fillet_l(request: FilletLRequest) -> Batch32Plan:
    return Batch32Plan(
        **_base(
            request,
            "FF",
            "xiFilletL",
            "FL",
            "xiFilletL",
            EvidenceLevel.HELP_WRAPPER,
            "shortcuts/wrapper and official FL help define inside-to-outside crossing selection and centerline exclusion",
            (
                "wall classification, intersection grouping, zero-radius fillet topology, and centerline recognition are compiled",
                "caller identifies exclusions and supplies every exact edit",
            ),
        ),
        exact_changes=request.exact_changes,
    )


class OffsetCloseRequest(ContractRequest):
    source: EntitySnapshot
    offset_distance: float
    side_point: Point3D
    output_layer: str = Field(min_length=1)
    exact_changes: ExactChangeSet

    @model_validator(mode="after")
    def validate_offset(self) -> OffsetCloseRequest:
        if self.offset_distance == 0:
            raise ValueError("WQ offset distance must be non-zero")
        _validate_changes((self.source,), self.exact_changes)
        return self


def plan_offset_close(request: OffsetCloseRequest) -> Batch32Plan:
    return Batch32Plan(
        **_base(
            request,
            "WQ",
            "xiOffsetAndClose",
            "OC",
            "xiOffsetAndClose",
            EvidenceLevel.HELP_WRAPPER,
            "shortcuts/wrapper and official OC help define offset-and-close for line, arc, or polyline",
            (
                "side selection, joins, arc handling, end caps, and source retention are compiled",
                "caller supplies the complete closed result rather than inferred geometry",
            ),
        ),
        exact_changes=request.exact_changes,
    )


class EndpointPair(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    first_handle: str = Field(min_length=1)
    first_point: Point3D
    second_handle: str = Field(min_length=1)
    second_point: Point3D
    measured_distance: float = Field(ge=0)


class EndConnectRequest(ContractRequest):
    sources: tuple[EntitySnapshot, ...] = Field(min_length=2)
    maximum_distance: float = Field(gt=0)
    require_parallel: bool
    endpoint_pairs: tuple[EndpointPair, ...] = Field(min_length=1)
    exact_changes: ExactChangeSet

    @model_validator(mode="after")
    def validate_connections(self) -> EndConnectRequest:
        handles = {item.handle.casefold() for item in self.sources}
        for pair in self.endpoint_pairs:
            if pair.first_handle.casefold() not in handles or pair.second_handle.casefold() not in handles:
                raise ValueError("WE endpoint pair handles must belong to sources")
            if pair.first_handle.casefold() == pair.second_handle.casefold():
                raise ValueError("WE endpoint pair must reference two different sources")
            if pair.measured_distance > self.maximum_distance:
                raise ValueError("WE endpoint distance exceeds maximum_distance")
        _validate_changes(self.sources, self.exact_changes)
        return self


def plan_end_connect(request: EndConnectRequest) -> Batch32Plan:
    return Batch32Plan(
        **_base(
            request,
            "WE",
            "xiPolyEndTab",
            "PET",
            "xiPolyEndTab",
            EvidenceLevel.HELP_WRAPPER,
            "shortcuts/wrapper and official PET help define line/polyline/arc endpoint joining by distance and optional parallelism",
            (
                "endpoint discovery, parallel tolerance, pairing conflicts, duplicates, and cleanup are compiled",
                "caller supplies measured pairs and exact connecting entities; help warns duplicates may remain",
            ),
        ),
        exact_changes=request.exact_changes,
    )


class XSymbolRequest(ContractRequest):
    first_corner: Point3D
    opposite_corner: Point3D
    output_layer: str = Field(min_length=1)
    exact_changes: ExactChangeSet

    @model_validator(mode="after")
    def validate_symbol(self) -> XSymbolRequest:
        if self.first_corner == self.opposite_corner:
            raise ValueError("XX symbol corners must differ")
        if self.exact_changes.source_revisions != ("drawing-input",):
            raise ValueError("XX exact changes must use the drawing-input revision marker")
        return self


def plan_x_symbol(request: XSymbolRequest) -> Batch32Plan:
    return Batch32Plan(
        **_base(
            request,
            "XX",
            "xiX",
            "X",
            "xiX",
            EvidenceLevel.HELP_WRAPPER,
            "shortcuts/wrapper and official X help identify a void X symbol and configurable layer",
            (
                "the help image does not define point acquisition, diagonal count, bounds, properties, or scale",
                "two corners and the complete exact output are explicit; no image geometry is reconstructed",
            ),
        ),
        exact_changes=request.exact_changes,
    )


class LibraryOperation(StrEnum):
    INSERT = "insert"
    ADD = "add"
    DELETE = "delete"
    REGENERATE_SLIDES = "regenerate_slides"
    IMPORT_FILES = "import_files"


class FileSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    content_digest: str = Field(pattern=DIGEST_PATTERN)


class LibraryResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_revisions: tuple[str, ...] = Field(min_length=1)
    result_files: tuple[FileSnapshot, ...]
    inserted_entities: tuple[ExactEntityResult, ...]
    manifest_digest: str = Field(pattern=DIGEST_PATTERN)


class BlockLibraryRequest(ContractRequest):
    operation: LibraryOperation
    library_root: str = Field(min_length=1)
    sources: tuple[FileSnapshot, ...] = Field(min_length=1)
    search_term: str = ""
    insertion_point: Point3D | None = None
    scale: float | None = Field(default=None, gt=0)
    rotation_degrees: float | None = None
    output_layer: str | None = None
    exact_result: LibraryResult

    @model_validator(mode="after")
    def validate_library(self) -> BlockLibraryRequest:
        revisions = tuple(item.revision for item in self.sources)
        if self.exact_result.source_revisions != revisions:
            raise ValueError("Q11 result must cite all file revisions in request order")
        if self.operation is LibraryOperation.INSERT and (
            self.insertion_point is None or self.scale is None or not self.exact_result.inserted_entities
        ):
            raise ValueError("Q11 insert requires point, scale, and exact inserted entities")
        if self.operation is not LibraryOperation.INSERT and self.exact_result.inserted_entities:
            raise ValueError("only Q11 insert may declare inserted entities")
        return self


class BlockLibraryPlan(Batch32Plan):
    operation: LibraryOperation
    file_result: LibraryResult


def plan_block_library(request: BlockLibraryRequest) -> BlockLibraryPlan:
    return BlockLibraryPlan(
        **_base(
            request,
            "Q11",
            "xiBlockLibrary",
            "Q1",
            "xiBlockLibrary",
            EvidenceLevel.HELP_WRAPPER,
            "shortcuts/wrapper and official Q1 help define insert, add, delete, slide regeneration, import, search, favorites, and layer settings",
            (
                "dynamic/auto-scale folder behavior, slide rendering, block creation, filesystem recovery, and special-character rules are compiled",
                "delete/import/regenerate are represented only as content-addressed plans; this read-only planner performs no file or CAD I/O",
            ),
        ),
        operation=request.operation,
        file_result=request.exact_result,
    )


class MaskRequest(ContractRequest):
    sources: tuple[EntitySnapshot, ...] = Field(min_length=1)
    enabled: bool
    border_offset_factor: float = Field(ge=0)
    use_drawing_background_color: bool = True
    exact_changes: ExactChangeSet

    @model_validator(mode="after")
    def validate_mask(self) -> MaskRequest:
        if any(item.entity_type.casefold() not in {"mtext", "acdbmtext"} for item in self.sources):
            raise ValueError("MK/MSK help limits the contract to multiline text")
        _validate_changes(self.sources, self.exact_changes)
        return self


def plan_mask(request: MaskRequest) -> Batch32Plan:
    return Batch32Plan(
        **_base(
            request,
            "MK",
            "xiMask",
            "MSK",
            "xiMask",
            EvidenceLevel.HELP_WRAPPER,
            "shortcuts/wrapper and official MSK help identify background masking of multiline text",
            (
                "the help does not define offset, color override, toggle behavior, or unsupported MText variants",
                "caller explicitly supplies mask policy and complete exact entity states",
            ),
        ),
        exact_changes=request.exact_changes,
    )


class ReferenceRotateRequest(ContractRequest):
    sources: tuple[EntitySnapshot, ...] = Field(min_length=1)
    base_point: Point3D
    reference_start: Point3D
    reference_end: Point3D
    destination_start: Point3D
    destination_end: Point3D
    exact_changes: ExactChangeSet

    @model_validator(mode="after")
    def validate_rotation(self) -> ReferenceRotateRequest:
        if self.reference_start == self.reference_end:
            raise ValueError("RR reference direction requires two distinct points")
        if self.destination_start == self.destination_end:
            raise ValueError("RR destination direction requires two distinct points")
        _validate_changes(self.sources, self.exact_changes)
        return self


def plan_reference_rotate(request: ReferenceRotateRequest) -> Batch32Plan:
    return Batch32Plan(
        **_base(
            request,
            "RR",
            "xiRR",
            "RR",
            "xiRefRotate",
            EvidenceLevel.HELP_RENAME,
            "semantic reconciliation and official RR help identify reference rotation with independent reference and destination starts",
            (
                "official help spells the full symbol xiRefRotage while local current reconciliation resolves xiRefRotate",
                "transform conventions, locked/nested objects, and CAD equivalence remain unverified",
            ),
        ),
        exact_changes=request.exact_changes,
    )


class ObjectInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    selected_handle: str = Field(min_length=1)
    container_path: tuple[str, ...]
    external_reference_path: str | None = None
    effective_color: str = Field(min_length=1)
    layer_color: str = Field(min_length=1)
    effective_linetype: str = Field(min_length=1)
    layer_linetype: str = Field(min_length=1)
    result_digest: str = Field(pattern=DIGEST_PATTERN)


class ObjectInfoRequest(ContractRequest):
    source: EntitySnapshot
    nested_pick_path: tuple[str, ...]
    exact_info: ObjectInfo

    @model_validator(mode="after")
    def validate_info(self) -> ObjectInfoRequest:
        if self.exact_info.selected_handle.casefold() != self.source.handle.casefold():
            raise ValueError("LII info must identify the selected source handle")
        if self.exact_info.container_path != self.nested_pick_path:
            raise ValueError("LII exact container path must match the nested pick path")
        return self


class ObjectInfoPlan(Batch32Plan):
    exact_info: ObjectInfo


def plan_object_info(request: ObjectInfoRequest) -> ObjectInfoPlan:
    return ObjectInfoPlan(
        **_base(
            request,
            "LII",
            "xLi",
            "LII",
            "xiListInBlk",
            EvidenceLevel.HELP_RENAME,
            "semantic reconciliation, current menu, and official LII help define nested block/xref path and effective/layer color and linetype reporting",
            (
                "nested selection traversal, ByBlock/ByLayer resolution, proxy entities, and filesystem reveal behavior are compiled",
                "the caller supplies the exact report; the planner opens neither CAD nor Explorer",
            ),
        ),
        exact_info=request.exact_info,
    )


class CadProduct(StrEnum):
    AUTOCAD = "autocad"
    ZWCAD = "zwcad"
    GSTARCAD = "gstarcad"
    BRICSCAD = "bricscad"


class ScaleListDeleteRequest(ContractRequest):
    os_family: str
    cad_product: CadProduct
    cad_version: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    scale_names: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_platform(self) -> ScaleListDeleteRequest:
        if self.os_family.casefold() != "windows":
            raise ValueError("SLD is a Windows CAD command")
        if self.cad_product is CadProduct.ZWCAD and not self.dry_run:
            raise ValueError("SLD execution is explicitly unsupported on ZWCAD")
        names = [name.casefold() for name in self.scale_names]
        if len(names) != len(set(names)):
            raise ValueError("SLD scale names must be unique")
        return self


class PlatformStatus(StrEnum):
    BLOCKED_UNSUPPORTED = "blocked_unsupported"
    REQUIRES_PLATFORM_ADAPTER = "requires_platform_adapter"


class ScaleListDeletePlan(Batch32Plan):
    platform_status: PlatformStatus
    cad_product: CadProduct
    cad_version: str
    source_revision: str
    scale_names: tuple[str, ...]


def plan_scale_list_delete(request: ScaleListDeleteRequest) -> ScaleListDeletePlan:
    unsupported = request.cad_product is CadProduct.ZWCAD
    return ScaleListDeletePlan(
        **_base(
            request,
            "SLD",
            "xiScaleListDelete",
            "SLD",
            "xiScaleListDelete",
            EvidenceLevel.PLATFORM_GUARD,
            "current/frozen shortcuts explicitly mark SLD unsupported on ZWCAD",
            (
                "ZWCAD requests remain blocked and cannot be approved into a mutation",
                "other Windows CAD products still require a separately reviewed adapter and exact postcondition evidence",
            ),
        ),
        platform_status=(
            PlatformStatus.BLOCKED_UNSUPPORTED
            if unsupported
            else PlatformStatus.REQUIRES_PLATFORM_ADAPTER
        ),
        cad_product=request.cad_product,
        cad_version=request.cad_version,
        source_revision=request.source_revision,
        scale_names=request.scale_names,
    )


def register_headless_core_batch32_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 32 Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_ce", plan_centerline),
        ("xicad_plan_bbb", plan_break_multi),
        ("xicad_plan_ff", plan_fillet_l),
        ("xicad_plan_wq", plan_offset_close),
        ("xicad_plan_we", plan_end_connect),
        ("xicad_plan_xx", plan_x_symbol),
        ("xicad_plan_q11", plan_block_library),
        ("xicad_plan_mk", plan_mask),
        ("xicad_plan_rr", plan_reference_rotate),
        ("xicad_plan_lii", plan_object_info),
        ("xicad_plan_sld", plan_scale_list_delete),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
