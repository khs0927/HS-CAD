"""Evidence-bounded dialog-free planners for xiCAD batch 31B commands."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval

DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


class EvidenceLevel(StrEnum):
    DCL_HELP_EXACT_RESULT = "dcl_help_backed_explicit_result_not_legacy_equivalent"
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


class Point3D(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    x: float
    y: float
    z: float = 0.0


class GeometrySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    revision: str = Field(min_length=1)
    geometry_digest: str = Field(pattern=DIGEST_PATTERN)
    points: tuple[Point3D, ...] = Field(min_length=1)


class ResourceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    content_digest: str = Field(pattern=DIGEST_PATTERN)


class ExactEntityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    result_id: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class ExactGeometryResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    input_revision: str = Field(min_length=1)
    entities: tuple[ExactEntityResult, ...] = Field(min_length=1)
    manifest_digest: str = Field(pattern=DIGEST_PATTERN)

    @model_validator(mode="after")
    def unique_entities(self) -> ExactGeometryResult:
        ids = [item.result_id.casefold() for item in self.entities]
        if len(ids) != len(set(ids)):
            raise ValueError("exact result entity ids must be unique")
        return self


class Batch31BPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    semantic_evidence: str
    semantic_gaps: tuple[str, ...]
    evidence_level: EvidenceLevel
    source: GeometrySnapshot | None = None
    result: ExactGeometryResult | None = None
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
    level: EvidenceLevel,
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


def _validate_geometry(source: GeometrySnapshot, result: ExactGeometryResult, count: int | None) -> None:
    if count is not None and len(source.points) != count:
        raise ValueError(f"source geometry requires exactly {count} points")
    if result.input_revision != source.revision:
        raise ValueError("exact result must cite the input geometry revision")


class KitchenCornerRequest(ContractRequest):
    source: GeometrySnapshot
    refrigerator_width: float = Field(gt=0)
    result: ExactGeometryResult


def plan_kitchen_corner(request: KitchenCornerRequest) -> Batch31BPlan:
    _validate_geometry(request.source, request.result, 3)
    return Batch31BPlan(
        **_base(
            request,
            "KCL",
            "xiKICL",
            "current/frozen shortcuts, ZWCAD menu, and official help identify the kitchen-furniture command, three picked points, and a refrigerator-size setting",
            (
                "the official KCL article inconsistently says straight kitchen and tells the user to run KCI; title and full symbol say KCL/xiKICL",
                "cabinet layout, corner handedness, widths, component choice, and geometry are compiled; caller supplies the complete result",
                "no command-specific DCL, config, data, or readable source was found and CAD equivalence is unverified",
            ),
            EvidenceLevel.HELP_EXACT_RESULT,
        ),
        source=request.source,
        result=request.result,
    )


class PlaneLevelRequest(ContractRequest):
    source: GeometrySnapshot
    level_text: str = Field(min_length=1)
    prefix: str
    decimals: int = Field(ge=0, le=12)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    symbol_resource: ResourceSnapshot
    result: ExactGeometryResult


def plan_plane_level(request: PlaneLevelRequest) -> Batch31BPlan:
    _validate_geometry(request.source, request.result, 1)
    return Batch31BPlan(
        **_base(
            request,
            "PLM",
            "xiPLMark",
            "shortcuts/menu, current DCL/config, local xi_Lemark.dwg, and official help identify insertion point, prefix/value formatting, text settings, repetition, and the symbol block",
            (
                "block insertion transform, numeric parsing/increment, comma/leading-space propagation, attributes, and entity properties are compiled",
                "caller supplies a versioned symbol resource and complete exact result; the planner reads no DWG",
                "DCL/help-backed explicit output does not establish CAD equivalence",
            ),
            EvidenceLevel.DCL_HELP_EXACT_RESULT,
        ),
        source=request.source,
        result=request.result,
    )


class ReferenceMarkRequest(ContractRequest):
    source: GeometrySnapshot
    detail_number: str = Field(min_length=1)
    reference_drawing: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    line_type: str = Field(min_length=1)
    color: int = Field(ge=0, le=256)
    symbol_size: float = Field(gt=0)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    result: ExactGeometryResult


def plan_reference_mark(request: ReferenceMarkRequest) -> Batch31BPlan:
    _validate_geometry(request.source, request.result, 4)
    return Batch31BPlan(
        **_base(
            request,
            "PPB",
            "xiPPB",
            "shortcuts/menu, current DCL, and official help identify detail/reference text, four-corner picking order, layer/linetype/color, symbol size, and text settings",
            (
                "the help shows but does not numerically define corner order, rectangle construction, text placement, or scale transforms",
                "caller provides all four ordered points and the complete exact output rather than inferred geometry",
                "no config/data/readable source was found and CAD equivalence is unverified",
            ),
            EvidenceLevel.DCL_HELP_EXACT_RESULT,
        ),
        source=request.source,
        result=request.result,
    )


class RoofDrainRequest(ContractRequest):
    source: GeometrySnapshot
    diameter: float = Field(gt=0)
    layer: str = Field(min_length=1)
    symbol_resource: ResourceSnapshot
    result: ExactGeometryResult


def plan_roof_drain(request: RoofDrainRequest) -> Batch31BPlan:
    _validate_geometry(request.source, request.result, 1)
    return Batch31BPlan(
        **_base(
            request,
            "RD",
            "xiRoofDrain",
            "shortcuts/menu, current DCL/config, local xi_RoofDrain.dwg, and official help identify an insertion point, drain diameter, layer, and diameter-dependent symbol",
            (
                "block name, scale/rotation, resource decomposition, attributes, repeat behavior, and entity properties are compiled",
                "caller supplies the versioned block resource and exact result; no geometry is inferred from diameter",
                "DCL/help-backed explicit output does not establish CAD equivalence",
            ),
            EvidenceLevel.DCL_HELP_EXACT_RESULT,
        ),
        source=request.source,
        result=request.result,
    )


class RubbleRequest(ContractRequest):
    source: GeometrySnapshot
    symbol_resource: ResourceSnapshot
    result: ExactGeometryResult


def plan_rubble(request: RubbleRequest) -> Batch31BPlan:
    _validate_geometry(request.source, request.result, 2)
    return Batch31BPlan(
        **_base(
            request,
            "RUB",
            "xiRUB",
            "current/frozen shortcuts, ZWCAD menu, local rubble DWG candidates, and official help identify a two-point rubble-compaction symbol whose side depends on point order",
            (
                "the authoritative choice among RUB.dwg, RUBBLE.dwg, and xi_Rubble.dwg, repetition/spacing, clipping, and orientation transform is compiled",
                "caller must choose a content-addressed resource and provide the complete exact result; point order is preserved without deriving a side",
                "no command-specific DCL/config/data/readable source was found and CAD equivalence is unverified",
            ),
            EvidenceLevel.HELP_EXACT_RESULT,
        ),
        source=request.source,
        result=request.result,
    )


class DrawingFileSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    content_digest: str = Field(pattern=DIGEST_PATTERN)
    whole_document: bool


class SaveAsBlockResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_revision: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    output_revision: str = Field(min_length=1)
    output_digest: str = Field(pattern=DIGEST_PATTERN)
    moved_extent_corner_to_origin: bool
    base_point_at_origin: bool
    entities_on_layer_zero: bool
    entity_color_bylayer: bool
    entity_linetype_bylayer: bool
    standard_text_style: bool
    standard_dimension_style: bool
    purge_passes: int = Field(ge=0)


class SaveAsBlockRequest(ContractRequest):
    source: DrawingFileSnapshot
    result: SaveAsBlockResult


class SaveAsBlockPlan(Batch31BPlan):
    source_file: DrawingFileSnapshot
    file_result: SaveAsBlockResult


def plan_save_as_block(request: SaveAsBlockRequest) -> SaveAsBlockPlan:
    if not request.source.whole_document:
        raise ValueError("SAB help explicitly requires the whole drawing, not a partial WBlock selection")
    if request.result.source_revision != request.source.revision:
        raise ValueError("SAB output must cite the exact source revision")
    required = (
        request.result.moved_extent_corner_to_origin,
        request.result.base_point_at_origin,
        request.result.entities_on_layer_zero,
        request.result.entity_color_bylayer,
        request.result.entity_linetype_bylayer,
        request.result.standard_text_style,
        request.result.standard_dimension_style,
    )
    if not all(required) or request.result.purge_passes != 3:
        raise ValueError("SAB exact result must attest every help-defined normalization and three purges")
    return SaveAsBlockPlan(
        **_base(
            request,
            "SAB",
            "xiSaveAsBlock",
            "current/frozen shortcuts and official help define whole-drawing block-file cleanup: origin/base normalization, layer 0, ByLayer properties, Standard text/dimension styles, and three purge passes",
            (
                "the help explicitly says SAB is not a partial-object WBlock operation",
                "dependency reachability, unsupported entities, exact purge behavior, save version, errors, and transaction recovery are compiled",
                "caller supplies a versioned source and content-addressed exact file result; the planner performs no CAD or filesystem I/O and claims no equivalence",
            ),
            EvidenceLevel.HELP_EXACT_RESULT,
        ),
        source_file=request.source,
        file_result=request.result,
    )


class SectionSymbolRequest(ContractRequest):
    source: GeometrySnapshot
    layer: str = Field(min_length=1)
    line_type: str = Field(min_length=1)
    result: ExactGeometryResult


def plan_section_symbol(request: SectionSymbolRequest) -> Batch31BPlan:
    _validate_geometry(request.source, request.result, 2)
    return Batch31BPlan(
        **_base(
            request,
            "SSL",
            "xiSSL",
            "current/frozen shortcuts, ZWCAD menu, and official help identify a plan section-cut symbol with selectable layer and linetype",
            (
                "the help image is the only geometry evidence; point acquisition, direction, labels, marker shapes, sizes, colors, and text properties remain compiled",
                "caller supplies the ordered two-point snapshot and complete exact result without reconstructing the image",
                "no command-specific DCL/config/data/readable source was found and CAD equivalence is unverified",
            ),
            EvidenceLevel.HELP_EXACT_RESULT,
        ),
        source=request.source,
        result=request.result,
    )


class UtilityLineKind(StrEnum):
    RAIN = "rain"
    WASTE = "waste"


class UtilityLineRequest(ContractRequest):
    source: GeometrySnapshot
    kind: UtilityLineKind
    rain_layer: str = Field(min_length=1)
    waste_layer: str = Field(min_length=1)
    linetype_resource: ResourceSnapshot
    result: ExactGeometryResult


def plan_utility_line(request: UtilityLineRequest) -> Batch31BPlan:
    _validate_geometry(request.source, request.result, None)
    if len(request.source.points) < 2:
        raise ValueError("WU source geometry requires at least two points")
    expected_layer = request.rain_layer if request.kind == UtilityLineKind.RAIN else request.waste_layer
    if any(entity.layer.casefold() != expected_layer.casefold() for entity in request.result.entities):
        raise ValueError("WU exact result entities must use the selected rain/waste layer")
    return Batch31BPlan(
        **_base(
            request,
            "WU",
            "xiWU",
            "shortcuts/menu, current DCL/config, and official help identify rain/waste site lines, separate layers, and dependence on a xiCAD linetype resource",
            (
                "the help warns that using a different linetype file causes an error, but the exact file/name, vertices, widths, scale, and property assignment remain compiled",
                "caller supplies the ordered path, selected kind, versioned linetype resource, and complete exact result",
                "the planner loads no linetype and DCL/help-backed explicit output does not establish CAD equivalence",
            ),
            EvidenceLevel.DCL_HELP_EXACT_RESULT,
        ),
        source=request.source,
        result=request.result,
    )


def register_headless_core_batch31b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 31B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_kcl", plan_kitchen_corner),
        ("xicad_plan_plm", plan_plane_level),
        ("xicad_plan_ppb", plan_reference_mark),
        ("xicad_plan_rd", plan_roof_drain),
        ("xicad_plan_rub", plan_rubble),
        ("xicad_plan_sab", plan_save_as_block),
        ("xicad_plan_ssl", plan_section_symbol),
        ("xicad_plan_wu", plan_utility_line),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
