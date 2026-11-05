"""Evidence-bounded dialog-free planners for xiCAD batch 28B block/file commands."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D

DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


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


class Batch28BPlan(BaseModel):
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
    revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class DocumentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_uri: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    content_digest: str = Field(pattern=DIGEST_PATTERN)


class ExplicitDocumentResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_uri: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    expected_content_digest: str = Field(pattern=DIGEST_PATTERN)
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


def _validate_document_results(
    documents: tuple[DocumentSnapshot, ...], results: tuple[ExplicitDocumentResult, ...]
) -> None:
    sources = {item.source_uri.casefold(): item for item in documents}
    outputs = {item.source_uri.casefold(): item for item in results}
    if len(sources) != len(documents) or len(outputs) != len(results) or sources.keys() != outputs.keys():
        raise ValueError("requires one unique explicit result per document snapshot")
    for key, source in sources.items():
        if outputs[key].source_revision != source.revision:
            raise ValueError("document result must cite the exact source revision")


class AttributeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    tag: str = Field(min_length=1)
    text: str
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class AttributedBlockSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    reference: EntitySnapshot
    block_name: str = Field(min_length=1)
    attributes: tuple[AttributeSnapshot, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_attributes(self) -> AttributedBlockSnapshot:
        handles = [item.handle.casefold() for item in self.attributes]
        if len(handles) != len(set(handles)):
            raise ValueError("attribute handles must be unique")
        return self


class RetainedAttributeText(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_attribute_handle: str = Field(min_length=1)
    exact_text_entity: EntitySnapshot


class ExplodedBlockResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_entities: tuple[EntitySnapshot, ...] = Field(min_length=1)
    retained_attribute_texts: tuple[RetainedAttributeText, ...] = Field(min_length=1)


class ExplodeAttributesRetainingTextRequest(ContractRequest):
    blocks: tuple[AttributedBlockSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[ExplodedBlockResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> ExplodeAttributesRetainingTextRequest:
        sources = {item.reference.handle.casefold(): item for item in self.blocks}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if (
            len(sources) != len(self.blocks)
            or len(results) != len(self.exact_results)
            or sources.keys() != results.keys()
        ):
            raise ValueError("EAR requires one unique explicit explode result per block")
        for key, source in sources.items():
            result = results[key]
            if result.source_revision != source.reference.revision:
                raise ValueError("EAR result must cite the exact block revision")
            attributes = {item.handle.casefold() for item in source.attributes}
            retained = [item.source_attribute_handle.casefold() for item in result.retained_attribute_texts]
            if len(retained) != len(set(retained)) or set(retained) != attributes:
                raise ValueError("EAR requires exactly one retained text result per source attribute")
        return self


class ExplodeAttributesRetainingTextPlan(Batch28BPlan):
    blocks: tuple[AttributedBlockSnapshot, ...]
    results: tuple[ExplodedBlockResult, ...]


def plan_explode_attributes_retaining_text(
    request: ExplodeAttributesRetainingTextRequest,
) -> ExplodeAttributesRetainingTextPlan:
    return ExplodeAttributesRetainingTextPlan(
        command_alias="EAR",
        legacy_symbol="xiExpAttRemainTxt",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and menus identify exploding attributed blocks while retaining text",
        semantic_gaps=(
            "explode topology, attribute formatting, visibility, constants, and transforms are compiled",
            "caller supplies every exact exploded entity and retained text result against versioned sources",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXACT_RESULT,
        blocks=request.blocks,
        results=request.exact_results,
    )


class MultiInsertSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source: EntitySnapshot
    block_name: str = Field(min_length=1)
    rows: int = Field(ge=1)
    columns: int = Field(ge=1)
    row_spacing: float
    column_spacing: float

    @model_validator(mode="after")
    def actually_multiple(self) -> MultiInsertSnapshot:
        if self.rows * self.columns < 2:
            raise ValueError("M2B source must represent at least two insertions")
        return self


class OrdinaryBlockResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_references: tuple[EntitySnapshot, ...] = Field(min_length=2)


class MultiInsertToBlocksRequest(ContractRequest):
    multi_inserts: tuple[MultiInsertSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[OrdinaryBlockResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> MultiInsertToBlocksRequest:
        sources = {item.source.handle.casefold(): item for item in self.multi_inserts}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if (
            len(sources) != len(self.multi_inserts)
            or len(results) != len(self.exact_results)
            or sources.keys() != results.keys()
        ):
            raise ValueError("M2B requires one unique explicit result per multi-insert")
        for key, source in sources.items():
            result = results[key]
            if result.source_revision != source.source.revision:
                raise ValueError("M2B result must cite the exact source revision")
            if len(result.exact_references) != source.rows * source.columns:
                raise ValueError("M2B exact reference count must equal rows multiplied by columns")
        return self


class MultiInsertToBlocksPlan(Batch28BPlan):
    multi_inserts: tuple[MultiInsertSnapshot, ...]
    results: tuple[OrdinaryBlockResult, ...]


def plan_multi_insert_to_blocks(request: MultiInsertToBlocksRequest) -> MultiInsertToBlocksPlan:
    return MultiInsertToBlocksPlan(
        command_alias="M2B",
        legacy_symbol="xiMultiBlockChange",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and menus identify converting multi-inserts to ordinary blocks",
        semantic_gaps=(
            "array transform order, attributes, dynamic properties, and source deletion are compiled",
            "caller supplies every ordinary reference result and the exact array cardinality is enforced",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXACT_RESULT,
        multi_inserts=request.multi_inserts,
        results=request.exact_results,
    )


class BlockFileMethod(StrEnum):
    CHANGE = "change"
    DELETE = "delete"
    INSERT = "insert"
    EXPLODE = "explode"


class BlockChangeMode(StrEnum):
    CHANGE_EXISTING = "change_existing"
    REPLACE_INTERNAL = "replace_internal"
    REPLACE_EXTERNAL_FILE = "replace_external_file"
    REDEFINE = "redefine"


class ScaleBasis(StrEnum):
    RELATIVE_TO_EXISTING = "relative_to_existing"
    RELATIVE_TO_ORIGINAL = "relative_to_original"


class CoordinateBasis(StrEnum):
    RELATIVE = "relative"
    ABSOLUTE = "absolute"


class InsertionPointPolicy(StrEnum):
    KEEP_BLOCK_FIXED = "keep_block_fixed"
    KEEP_INSERTION_POINT_FIXED = "keep_insertion_point_fixed"


class InsertKind(StrEnum):
    BLOCK = "block"
    XREF = "xref"
    IMAGE = "image"


class MultiFileBlockOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    method: BlockFileMethod
    exclude_locked_layers: bool
    purge_after_replace_or_delete: bool
    change_mode: BlockChangeMode | None = None
    old_block_name: str | None = Field(default=None, min_length=1)
    new_block_name_or_uri: str | None = Field(default=None, min_length=1)
    outer_layer: str | None = Field(default=None, min_length=1)
    inner_layer: str | None = Field(default=None, min_length=1)
    scale_factor: float | None = Field(default=None, gt=0)
    scale_basis: ScaleBasis | None = None
    location: Point3D | None = None
    location_basis: CoordinateBasis | None = None
    new_insertion_point: Point3D | None = None
    insertion_point_policy: InsertionPointPolicy | None = None
    insert_kind: InsertKind | None = None
    insert_source_uri: str | None = Field(default=None, min_length=1)
    insert_source_digest: str | None = Field(default=None, pattern=DIGEST_PATTERN)
    insert_scale: float | None = Field(default=None, gt=0)
    insert_point: Point3D | None = None
    move_inserted_to_back: bool = False

    @model_validator(mode="after")
    def validate_option_groups(self) -> MultiFileBlockOptions:
        if (self.scale_factor is None) != (self.scale_basis is None):
            raise ValueError("scale factor and basis must be supplied together")
        if (self.location is None) != (self.location_basis is None):
            raise ValueError("location and basis must be supplied together")
        if (self.new_insertion_point is None) != (self.insertion_point_policy is None):
            raise ValueError("new insertion point and policy must be supplied together")
        insert_values = (
            self.insert_kind,
            self.insert_source_uri,
            self.insert_source_digest,
            self.insert_scale,
            self.insert_point,
        )
        if self.method == BlockFileMethod.INSERT:
            if any(value is None for value in insert_values):
                raise ValueError("insert method requires kind, content-addressed source, scale, and point")
        elif any(value is not None for value in insert_values) or self.move_inserted_to_back:
            raise ValueError("insert-only options require the insert method")
        if self.method == BlockFileMethod.CHANGE and self.change_mode is None:
            raise ValueError("change method requires an explicit DCL change mode")
        if self.method != BlockFileMethod.CHANGE and self.change_mode is not None:
            raise ValueError("change mode requires the change method")
        return self


class MultiFileBlockChangeRequest(ContractRequest):
    documents: tuple[DocumentSnapshot, ...] = Field(min_length=1)
    options: MultiFileBlockOptions
    exact_results: tuple[ExplicitDocumentResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> MultiFileBlockChangeRequest:
        _validate_document_results(self.documents, self.exact_results)
        return self


class MultiFileBlockChangePlan(Batch28BPlan):
    documents: tuple[DocumentSnapshot, ...]
    options: MultiFileBlockOptions
    results: tuple[ExplicitDocumentResult, ...]


def plan_multi_file_block_change(request: MultiFileBlockChangeRequest) -> MultiFileBlockChangePlan:
    return MultiFileBlockChangePlan(
        command_alias="MFB",
        legacy_symbol="xiMultiFilesChBlk",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="DCL exposes file set, change/delete/insert/explode, layer, scale, location, insertion, and purge controls",
        semantic_gaps=(
            "block matching, nested traversal, dynamic data, draw order, and config positional decoding are compiled",
            "each content-addressed input document has an explicit manifest digest and expected output digest",
            "the planner performs no file I/O and does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.DCL_EXACT_RESULT,
        documents=request.documents,
        options=request.options,
        results=request.exact_results,
    )


class XrefMethod(StrEnum):
    REPATH_ONE = "repath_one"
    ABSOLUTE_TO_RELATIVE = "absolute_to_relative"
    FORCE_PATH = "force_path"
    DETACH = "detach"
    BIND = "bind"
    BIND_INSERT = "bind_insert"
    REMOVE_UNREFERENCED = "remove_unreferenced"


class ReferenceKind(StrEnum):
    DWG = "dwg"
    IMAGE = "image"
    PDF = "pdf"
    DGN = "dgn"


class ReferenceScope(StrEnum):
    ALL = "all"
    INCLUDE_ONLY = "include_only"
    EXCLUDE_ONLY = "exclude_only"


class MultiFileXrefOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    method: XrefMethod
    reference_kinds: frozenset[ReferenceKind] = Field(min_length=1)
    exclude_locked_layers: bool
    do_not_save_after_work: bool
    scope: ReferenceScope
    selected_reference_names: tuple[str, ...] = ()
    source_uri: str | None = Field(default=None, min_length=1)
    source_digest: str | None = Field(default=None, pattern=DIGEST_PATTERN)
    reference_name: str | None = Field(default=None, min_length=1)
    forced_path: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_method_inputs(self) -> MultiFileXrefOptions:
        selected = [item.casefold() for item in self.selected_reference_names]
        if len(selected) != len(set(selected)):
            raise ValueError("selected reference names must be unique")
        if self.scope == ReferenceScope.ALL and selected:
            raise ValueError("all scope does not accept selected reference names")
        if self.scope != ReferenceScope.ALL and not selected:
            raise ValueError("include/exclude scope requires selected reference names")
        if self.method == XrefMethod.REPATH_ONE:
            if self.source_uri is None or self.source_digest is None or self.reference_name is None:
                raise ValueError("repath_one requires a content-addressed source and reference name")
        elif any(value is not None for value in (self.source_uri, self.source_digest, self.reference_name)):
            raise ValueError("individual source fields require repath_one")
        if (self.method == XrefMethod.FORCE_PATH) != (self.forced_path is not None):
            raise ValueError("forced path is required only for force_path")
        return self


class MultiFileXrefChangeRequest(ContractRequest):
    documents: tuple[DocumentSnapshot, ...] = Field(min_length=1)
    options: MultiFileXrefOptions
    exact_results: tuple[ExplicitDocumentResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> MultiFileXrefChangeRequest:
        _validate_document_results(self.documents, self.exact_results)
        return self


class MultiFileXrefChangePlan(Batch28BPlan):
    documents: tuple[DocumentSnapshot, ...]
    options: MultiFileXrefOptions
    results: tuple[ExplicitDocumentResult, ...]


def plan_multi_file_xref_change(request: MultiFileXrefChangeRequest) -> MultiFileXrefChangePlan:
    return MultiFileXrefChangePlan(
        command_alias="MFX",
        legacy_symbol="xiMultiFilesChXref",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="DCL exposes repath/relative/forced path/detach/bind/remove modes, target types, scope, lock, and save controls",
        semantic_gaps=(
            "path resolution, dependency loading, bind naming, selection acquisition, and config positional decoding are compiled",
            "each content-addressed input document has an explicit manifest digest and expected output digest",
            "the planner performs no path or drawing I/O and does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.DCL_EXACT_RESULT,
        documents=request.documents,
        options=request.options,
        results=request.exact_results,
    )


class XclipReferenceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    reference: EntitySnapshot
    existing_boundary_digest: str | None = Field(default=None, pattern=DIGEST_PATTERN)


class XclipResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_boundary: tuple[Point3D, ...] = Field(min_length=3)
    expected_boundary_digest: str = Field(pattern=DIGEST_PATTERN)


class MultiXclipRequest(ContractRequest):
    references: tuple[XclipReferenceSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[XclipResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> MultiXclipRequest:
        sources = {item.reference.handle.casefold(): item for item in self.references}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if (
            len(sources) != len(self.references)
            or len(results) != len(self.exact_results)
            or sources.keys() != results.keys()
        ):
            raise ValueError("MX requires one unique explicit clipping result per reference")
        for key, source in sources.items():
            if results[key].source_revision != source.reference.revision:
                raise ValueError("MX result must cite the exact source revision")
        return self


class MultiXclipPlan(Batch28BPlan):
    references: tuple[XclipReferenceSnapshot, ...]
    results: tuple[XclipResult, ...]


def plan_multi_xclip(request: MultiXclipRequest) -> MultiXclipPlan:
    return MultiXclipPlan(
        command_alias="MX",
        legacy_symbol="xiMultiXclip",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and menus identify applying XCLIP to multiple references",
        semantic_gaps=(
            "boundary acquisition, coordinate transforms, inversion, replacement, and eligibility are compiled",
            "caller supplies every exact boundary and expected digest against versioned references",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXACT_RESULT,
        references=request.references,
        results=request.exact_results,
    )


class WblockExportJob(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_revision: str = Field(min_length=1)
    selected_handles: tuple[str, ...] = Field(min_length=1)
    base_point: Point3D
    destination_uri: str = Field(min_length=1)
    overwrite: bool
    expected_content_digest: str = Field(pattern=DIGEST_PATTERN)

    @model_validator(mode="after")
    def unique_handles(self) -> WblockExportJob:
        handles = [item.casefold() for item in self.selected_handles]
        if len(handles) != len(set(handles)):
            raise ValueError("QWB selected handles must be unique")
        return self


class WblockExportRequest(ContractRequest):
    source_document: DocumentSnapshot
    available_entities: tuple[EntitySnapshot, ...] = Field(min_length=1)
    exact_job: WblockExportJob

    @model_validator(mode="after")
    def validate_export(self) -> WblockExportRequest:
        if self.exact_job.source_revision != self.source_document.revision:
            raise ValueError("QWB export must cite the exact source document revision")
        available = {item.handle.casefold() for item in self.available_entities}
        selected = {item.casefold() for item in self.exact_job.selected_handles}
        if not selected.issubset(available):
            raise ValueError("QWB selected handles must exist in the supplied entity snapshots")
        return self


class WblockExportPlan(Batch28BPlan):
    source_document: DocumentSnapshot
    available_entities: tuple[EntitySnapshot, ...]
    job: WblockExportJob


def plan_wblock_export(request: WblockExportRequest) -> WblockExportPlan:
    return WblockExportPlan(
        command_alias="QWB",
        legacy_symbol="xiWblockExport",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and menus identify WBLOCK export",
        semantic_gaps=(
            "selection prompts, file naming, DWG version, units, dependencies, and overwrite defaults are compiled",
            "caller supplies exact source entities, base point, destination, overwrite policy, and expected digest",
            "the planner performs no file I/O and does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXACT_RESULT,
        source_document=request.source_document,
        available_entities=request.available_entities,
        job=request.exact_job,
    )


def register_headless_core_batch28b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 28B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_ear", plan_explode_attributes_retaining_text),
        ("xicad_plan_m2b", plan_multi_insert_to_blocks),
        ("xicad_plan_mfb", plan_multi_file_block_change),
        ("xicad_plan_mfx", plan_multi_file_xref_change),
        ("xicad_plan_mx", plan_multi_xclip),
        ("xicad_plan_qwb", plan_wblock_export),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
