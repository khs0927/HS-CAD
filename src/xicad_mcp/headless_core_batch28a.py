"""Evidence-bounded dialog-free planners for xiCAD batch 28A block/xref commands."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


class EvidenceLevel(StrEnum):
    DCL_EXACT_RESULT = "dcl_backed_explicit_result_not_legacy_equivalent"
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


class Batch28APlan(BaseModel):
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
    owner_revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    geometry_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    layer: str = Field(min_length=1)


class ExactEntity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    output_id: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    geometry_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    layer: str = Field(min_length=1)


class BlockDefinitionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    definition_revision: str = Field(min_length=1)
    base_point: Point3D
    members: tuple[EntitySnapshot, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_members(self) -> BlockDefinitionSnapshot:
        _unique(tuple(item.handle for item in self.members), "block member")
        return self


class ExactBlockDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    definition_revision: str = Field(min_length=1)
    base_point: Point3D
    members: tuple[ExactEntity, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_members(self) -> ExactBlockDefinition:
        _unique(tuple(item.output_id for item in self.members), "exact block member")
        return self


class BlockReferenceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    handle: str = Field(min_length=1)
    reference_revision: str = Field(min_length=1)
    block_name: str = Field(min_length=1)
    definition_revision: str = Field(min_length=1)
    insertion_point: Point3D
    rotation_radians: float
    scale_x: float
    scale_y: float
    scale_z: float
    layer: str = Field(min_length=1)
    count_key: str = Field(min_length=1)
    area_key: str | None = None
    dynamic_property_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def nonzero_scales(self) -> BlockReferenceSnapshot:
        if 0 in (self.scale_x, self.scale_y, self.scale_z):
            raise ValueError("block reference scales must be nonzero")
        return self


class ExactBlockReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    block_name: str = Field(min_length=1)
    insertion_point: Point3D
    rotation_radians: float
    scale_x: float
    scale_y: float
    scale_z: float
    layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def nonzero_scales(self) -> ExactBlockReference:
        if 0 in (self.scale_x, self.scale_y, self.scale_z):
            raise ValueError("exact block reference scales must be nonzero")
        return self


class ProposedBlockReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    output_id: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    block_name: str = Field(min_length=1)
    insertion_point: Point3D
    rotation_radians: float
    scale_x: float
    scale_y: float
    scale_z: float
    layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def nonzero_scales(self) -> ProposedBlockReference:
        if 0 in (self.scale_x, self.scale_y, self.scale_z):
            raise ValueError("proposed block reference scales must be nonzero")
        return self


def _unique(values: tuple[str, ...], label: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{label} values must be unique")


def _base(request: ContractRequest, alias: str, symbol: str, evidence: str, gaps: tuple[str, ...], level: EvidenceLevel) -> dict[str, Any]:
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


class MakeBlockInPlaceRequest(ContractRequest):
    sources: tuple[EntitySnapshot, ...] = Field(min_length=1)
    exact_definition: ExactBlockDefinition
    exact_reference: ProposedBlockReference
    delete_source_entities: bool = True

    @model_validator(mode="after")
    def validate_result(self) -> MakeBlockInPlaceRequest:
        _unique(tuple(item.handle for item in self.sources), "BLX source")
        if self.exact_reference.block_name != self.exact_definition.name:
            raise ValueError("BLX definition and reference names must match")
        if self.exact_reference.insertion_point != self.exact_definition.base_point:
            raise ValueError("BLX in-place reference must use the exact definition base point")
        if not self.delete_source_entities:
            raise ValueError("BLX replacement requires explicit source deletion")
        return self


class MakeBlockInPlacePlan(Batch28APlan):
    sources: tuple[EntitySnapshot, ...]
    definition: ExactBlockDefinition
    reference: ProposedBlockReference
    delete_handles: tuple[str, ...]


def plan_make_block_in_place(request: MakeBlockInPlaceRequest) -> MakeBlockInPlacePlan:
    return MakeBlockInPlacePlan(
        **_base(request, "BLX", "xiMakeBlock", "current/frozen shortcuts and ZWCAD menu identify making a block in its original place", (
            "base-point choice, naming, source-to-definition transforms, attributes, and dynamic behavior are compiled",
            "caller supplies the exact definition and replacement reference",
            "the shortcut-backed explicit result does not claim CAD equivalence",
        ), EvidenceLevel.SHORTCUT_EXACT_RESULT),
        sources=request.sources,
        definition=request.exact_definition,
        reference=request.exact_reference,
        delete_handles=tuple(item.handle for item in request.sources),
    )


class QuantityOutput(StrEnum):
    CAD_TABLE = "cad_table"
    LINE_TABLE = "line_table"
    CSV_FILE = "csv_file"
    COMMAND_LINE = "command_line"


class BlockQuantityOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    output: QuantityOutput
    delete_overlapping_before_count: bool
    target_count_keys: tuple[str, ...] = ()
    use_area_groups: bool = False
    window_mode: bool = True
    count_dynamic_properties: bool = False
    sort_by: str = Field(pattern=r"^(name|quantity)$")
    descending: bool = False
    decimal_places: int = Field(ge=0, le=12)
    text_height: float = Field(gt=0)


class QuantityRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    count_key: str = Field(min_length=1)
    area_key: str | None
    quantity: int = Field(ge=1)


class ExactOutputArtifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    artifact_kind: QuantityOutput
    target: str = Field(min_length=1)
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class BlockQuantityRequest(ContractRequest):
    references: tuple[BlockReferenceSnapshot, ...] = Field(min_length=1)
    options: BlockQuantityOptions
    excluded_duplicate_handles: tuple[str, ...] = ()
    exact_rows: tuple[QuantityRow, ...] = Field(min_length=1)
    exact_output: ExactOutputArtifact

    @model_validator(mode="after")
    def validate_rows(self) -> BlockQuantityRequest:
        handles = tuple(item.handle for item in self.references)
        _unique(handles, "BQT reference")
        _unique(self.excluded_duplicate_handles, "BQT duplicate")
        known = {item.casefold() for item in handles}
        excluded = {item.casefold() for item in self.excluded_duplicate_handles}
        if not excluded <= known or (excluded and not self.options.delete_overlapping_before_count):
            raise ValueError("BQT excluded duplicates must be known and duplicate deletion enabled")
        targets = {item.casefold() for item in self.options.target_count_keys}
        if len(targets) != len(self.options.target_count_keys):
            raise ValueError("BQT target count keys must be unique")
        counts: dict[tuple[str, str | None], int] = {}
        for ref in self.references:
            if ref.handle.casefold() in excluded or (targets and ref.count_key.casefold() not in targets):
                continue
            if self.options.use_area_groups and not ref.area_key:
                raise ValueError("BQT area grouping requires an area key on every counted reference")
            if self.options.count_dynamic_properties and not ref.dynamic_property_digest:
                raise ValueError("BQT dynamic-property counting requires a digest on every counted reference")
            area = ref.area_key if self.options.use_area_groups else None
            key = (ref.count_key.casefold(), area.casefold() if area else None)
            counts[key] = counts.get(key, 0) + 1
        rows = {(row.count_key.casefold(), row.area_key.casefold() if row.area_key else None): row.quantity for row in self.exact_rows}
        if len(rows) != len(self.exact_rows) or rows != counts:
            raise ValueError("BQT exact rows must equal counts from the versioned references and explicit filters")
        if self.exact_output.artifact_kind != self.options.output:
            raise ValueError("BQT output artifact kind must match the selected DCL output")
        return self


class BlockQuantityPlan(Batch28APlan):
    references: tuple[BlockReferenceSnapshot, ...]
    options: BlockQuantityOptions
    excluded_duplicate_handles: tuple[str, ...]
    rows: tuple[QuantityRow, ...]
    output: ExactOutputArtifact


def plan_block_quantity(request: BlockQuantityRequest) -> BlockQuantityPlan:
    return BlockQuantityPlan(
        **_base(request, "BQT", "xiBlkQty", "current/frozen shortcuts, xiBlkQty DCL, config defaults, and ZWCAD menu identify block counting/table output", (
            "overlap equality, area containment, dynamic-property grouping, table geometry, and CSV serialization are compiled",
            "caller supplies duplicate decisions and an exact output artifact digest",
            "rows are verified from versioned references but legacy CAD equivalence remains unverified",
        ), EvidenceLevel.DCL_EXACT_RESULT),
        references=request.references,
        options=request.options,
        excluded_duplicate_handles=request.excluded_duplicate_handles,
        rows=request.exact_rows,
        output=request.exact_output,
    )


class RemoveBlockMembersRequest(ContractRequest):
    definition: BlockDefinitionSnapshot
    remove_handles: tuple[str, ...] = Field(min_length=1)
    exact_definition: ExactBlockDefinition

    @model_validator(mode="after")
    def validate_result(self) -> RemoveBlockMembersRequest:
        _unique(self.remove_handles, "BRM removal")
        source = {item.handle.casefold() for item in self.definition.members}
        remove = {item.casefold() for item in self.remove_handles}
        if not remove < source:
            raise ValueError("BRM removals must be a proper subset that leaves a nonempty block")
        if self.exact_definition.name != self.definition.name or self.exact_definition.definition_revision == self.definition.definition_revision:
            raise ValueError("BRM exact definition must retain the name and use a new revision")
        remaining = source - remove
        exact = {item.output_id.casefold() for item in self.exact_definition.members}
        if exact != remaining:
            raise ValueError("BRM exact definition members must equal source members minus removals")
        return self


class RemoveBlockMembersPlan(Batch28APlan):
    definition: BlockDefinitionSnapshot
    remove_handles: tuple[str, ...]
    exact_definition: ExactBlockDefinition


def plan_remove_block_members(request: RemoveBlockMembersRequest) -> RemoveBlockMembersPlan:
    return RemoveBlockMembersPlan(
        **_base(request, "BRM", "xiREMB", "current/frozen shortcuts identify removing objects from a block", (
            "member selection, nested ownership, coordinate transforms, attributes, and reference refresh are compiled",
            "caller supplies the exact new definition",
            "no command-specific DCL/config/data/source or CAD equivalence was found",
        ), EvidenceLevel.SHORTCUT_EXACT_RESULT),
        definition=request.definition,
        remove_handles=request.remove_handles,
        exact_definition=request.exact_definition,
    )


class RenameResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_name: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    result_name: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)


class RenameBlocksRequest(ContractRequest):
    definitions: tuple[BlockDefinitionSnapshot, ...] = Field(min_length=1)
    copy_instead_of_rename: bool
    ignore_existing_name_collisions: bool
    exact_results: tuple[RenameResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> RenameBlocksRequest:
        sources = {item.name.casefold(): item for item in self.definitions}
        results = {item.source_name.casefold(): item for item in self.exact_results}
        if len(sources) != len(self.definitions) or len(results) != len(self.exact_results) or sources.keys() != results.keys():
            raise ValueError("BRN requires one unique exact rename result per definition")
        _unique(tuple(item.result_name for item in self.exact_results), "BRN result name")
        for key, source in sources.items():
            result = results[key]
            if result.source_revision != source.definition_revision or result.result_revision == source.definition_revision:
                raise ValueError("BRN result must cite the source and use a new revision")
            if result.result_name.casefold() == source.name.casefold():
                raise ValueError("BRN exact result name must change")
        return self


class RenameBlocksPlan(Batch28APlan):
    definitions: tuple[BlockDefinitionSnapshot, ...]
    copy_instead_of_rename: bool
    ignore_existing_name_collisions: bool
    results: tuple[RenameResult, ...]


def plan_rename_blocks(request: RenameBlocksRequest) -> RenameBlocksPlan:
    return RenameBlocksPlan(
        **_base(request, "BRN", "xiRenameBL", "current/frozen shortcuts, xiRenameBL DCL, config defaults, and ZWCAD menu identify block renaming/copying", (
            "scope selection, partial replacement, special-character normalization, serial ordering, and collision handling are compiled",
            "caller supplies final unique names and exact revisions after applying reviewed policies",
            "DCL-backed options do not establish runtime ordering or CAD equivalence",
        ), EvidenceLevel.DCL_EXACT_RESULT),
        definitions=request.definitions,
        copy_instead_of_rename=request.copy_instead_of_rename,
        ignore_existing_name_collisions=request.ignore_existing_name_collisions,
        results=request.exact_results,
    )


class ChangeBlockScaleRequest(ContractRequest):
    references: tuple[BlockReferenceSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[ExactBlockReference, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> ChangeBlockScaleRequest:
        sources = {item.handle.casefold(): item for item in self.references}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if len(sources) != len(self.references) or len(results) != len(self.exact_results) or sources.keys() != results.keys():
            raise ValueError("BSC requires one unique exact result per block reference")
        for key, source in sources.items():
            result = results[key]
            if result.source_revision != source.reference_revision or result.result_revision == source.reference_revision:
                raise ValueError("BSC result must cite the source and use a new revision")
            if (result.scale_x, result.scale_y, result.scale_z) == (source.scale_x, source.scale_y, source.scale_z):
                raise ValueError("BSC exact result must change at least one scale")
            if result.block_name != source.block_name:
                raise ValueError("BSC scale change cannot change the block name")
        return self


class ChangeBlockScalePlan(Batch28APlan):
    references: tuple[BlockReferenceSnapshot, ...]
    results: tuple[ExactBlockReference, ...]


def plan_change_block_scale(request: ChangeBlockScaleRequest) -> ChangeBlockScalePlan:
    return ChangeBlockScalePlan(
        **_base(request, "BSC", "xiBlkScaChange", "current/frozen shortcuts and ZWCAD menu identify changing block scale", (
            "uniform/axis policy, anchor compensation, annotation, dynamic blocks, and unit behavior are compiled",
            "caller supplies every exact resulting reference",
            "no command-specific DCL/config/data/source or CAD equivalence was found",
        ), EvidenceLevel.SHORTCUT_EXACT_RESULT),
        references=request.references,
        results=request.exact_results,
    )


class XrefFileSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    xref_name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    file_revision: str = Field(min_length=1)
    file_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    writable: bool


class CopyObjectsToXrefRequest(ContractRequest):
    xref: XrefFileSnapshot
    sources: tuple[EntitySnapshot, ...] = Field(min_length=1)
    exact_file_entities: tuple[ExactEntity, ...] = Field(min_length=1)
    exact_file_revision_after: str = Field(min_length=1)
    exact_file_sha256_after: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    retain_sources_in_host: bool = True

    @model_validator(mode="after")
    def validate_result(self) -> CopyObjectsToXrefRequest:
        _unique(tuple(item.handle for item in self.sources), "CX source")
        _unique(tuple(item.output_id for item in self.exact_file_entities), "CX output")
        if not self.xref.writable:
            raise ValueError("CX requires an explicitly writable xref file snapshot")
        if self.exact_file_revision_after == self.xref.file_revision or self.exact_file_sha256_after == self.xref.file_sha256:
            raise ValueError("CX exact xref file revision and digest must both change")
        if not self.retain_sources_in_host:
            raise ValueError("CX copy contract must explicitly retain host source objects")
        return self


class CopyObjectsToXrefPlan(Batch28APlan):
    xref: XrefFileSnapshot
    sources: tuple[EntitySnapshot, ...]
    file_entities: tuple[ExactEntity, ...]
    file_revision_after: str
    file_sha256_after: str
    retain_source_handles: tuple[str, ...]


def plan_copy_objects_to_xref(request: CopyObjectsToXrefRequest) -> CopyObjectsToXrefPlan:
    return CopyObjectsToXrefPlan(
        **_base(request, "CX", "xiCopy2xRef", "current/frozen shortcuts and ZWCAD menu identify copying host objects into an xref", (
            "xref selection, host-to-file transform, locking, save/reload, layers, and failure recovery are compiled",
            "caller supplies the exact writable file snapshot, transformed entities, revision, and digest",
            "the planner performs no file I/O and claims no CAD equivalence",
        ), EvidenceLevel.SHORTCUT_EXACT_RESULT),
        xref=request.xref,
        sources=request.sources,
        file_entities=request.exact_file_entities,
        file_revision_after=request.exact_file_revision_after,
        file_sha256_after=request.exact_file_sha256_after,
        retain_source_handles=tuple(item.handle for item in request.sources),
    )


def register_headless_core_batch28a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 28A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_blx", plan_make_block_in_place),
        ("xicad_plan_bqt", plan_block_quantity),
        ("xicad_plan_brm", plan_remove_block_members),
        ("xicad_plan_brn", plan_rename_blocks),
        ("xicad_plan_bsc", plan_change_block_scale),
        ("xicad_plan_cx", plan_copy_objects_to_xref),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
