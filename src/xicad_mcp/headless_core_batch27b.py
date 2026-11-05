"""Evidence-bounded dialog-free planners for xiCAD batch 27B block commands."""

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


class Batch27BPlan(BaseModel):
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


class EntityKind(StrEnum):
    LINE = "line"
    ARC = "arc"
    CIRCLE = "circle"
    POLYLINE = "polyline"
    HATCH = "hatch"
    TEXT = "text"
    DIMENSION = "dimension"
    LEADER = "leader"
    SOLID = "solid"
    BLOCK_REFERENCE = "block_reference"
    OTHER = "other"


class BlockEntityState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    entity_path: str = Field(min_length=1)
    kind: EntityKind
    layer: str = Field(min_length=1)
    color: str = Field(min_length=1)
    linetype: str = Field(min_length=1)
    linetype_scale: float = Field(gt=0)
    geometry_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class BlockDefinitionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    definition_revision: str = Field(min_length=1)
    base_point: Point3D
    entities: tuple[BlockEntityState, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_entity_paths(self) -> BlockDefinitionSnapshot:
        paths = [item.entity_path.casefold() for item in self.entities]
        if len(paths) != len(set(paths)):
            raise ValueError("block entity paths must be unique within a definition snapshot")
        return self


class BlockReferenceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    handle: str = Field(min_length=1)
    reference_revision: str = Field(min_length=1)
    block_name: str = Field(min_length=1)
    insertion_point: Point3D
    rotation_radians: float
    scale_x: float
    scale_y: float
    scale_z: float
    layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def nonzero_scales(self) -> BlockReferenceSnapshot:
        if 0 in (self.scale_x, self.scale_y, self.scale_z):
            raise ValueError("block reference scales must be nonzero")
        return self


class EntityAction(StrEnum):
    KEEP = "keep"
    UPDATE = "update"
    DELETE = "delete"


class EntityMutationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_entity_path: str = Field(min_length=1)
    action: EntityAction
    exact_result: BlockEntityState | None

    @model_validator(mode="after")
    def result_matches_action(self) -> EntityMutationResult:
        if (self.action == EntityAction.DELETE) != (self.exact_result is None):
            raise ValueError("delete requires no exact result; keep/update requires one")
        if self.exact_result and self.exact_result.entity_path.casefold() != self.source_entity_path.casefold():
            raise ValueError("exact result must retain its source entity path")
        return self


class DefinitionMutationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_name: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    entity_results: tuple[EntityMutationResult, ...] = Field(min_length=1)


def _validate_definition_results(
    definitions: tuple[BlockDefinitionSnapshot, ...], results: tuple[DefinitionMutationResult, ...]
) -> None:
    source_map = {item.name.casefold(): item for item in definitions}
    result_map = {item.source_name.casefold(): item for item in results}
    if len(source_map) != len(definitions) or len(result_map) != len(results) or source_map.keys() != result_map.keys():
        raise ValueError("requires one unique exact mutation result per definition snapshot")
    for key, source in source_map.items():
        result = result_map[key]
        if result.source_revision != source.definition_revision:
            raise ValueError("definition result must cite the exact source revision")
        source_paths = {item.entity_path.casefold() for item in source.entities}
        result_paths = [item.source_entity_path.casefold() for item in result.entity_results]
        if len(result_paths) != len(set(result_paths)) or source_paths != set(result_paths):
            raise ValueError("requires one unique entity result per source entity path")


class BlockConditionOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    include_dimensions_and_leaders: bool
    target_layer: str | None = Field(default=None, min_length=1)
    change_outer_reference_layer: bool
    target_color: str | None = Field(default=None, min_length=1)
    target_linetype: str | None = Field(default=None, min_length=1)
    target_linetype_scale: float | None = Field(default=None, gt=0)
    explode_nested_blocks: bool
    delete_kinds: frozenset[EntityKind] = frozenset()
    exclude_off_or_frozen_layers: bool
    excluded_layers: tuple[str, ...] = ()
    exclude_solids: bool

    @model_validator(mode="after")
    def validate_dcl_options(self) -> BlockConditionOptions:
        allowed = {EntityKind.HATCH, EntityKind.TEXT, EntityKind.DIMENSION, EntityKind.LEADER}
        if not self.delete_kinds.issubset(allowed):
            raise ValueError("BCC DCL permits deletion only for hatch/text/dimension/leader")
        if len({item.casefold() for item in self.excluded_layers}) != len(self.excluded_layers):
            raise ValueError("excluded layers must be unique")
        return self


class BlockConditionChangeRequest(ContractRequest):
    definitions: tuple[BlockDefinitionSnapshot, ...] = Field(min_length=1)
    options: BlockConditionOptions
    exact_results: tuple[DefinitionMutationResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> BlockConditionChangeRequest:
        _validate_definition_results(self.definitions, self.exact_results)
        return self


class BlockConditionChangePlan(Batch27BPlan):
    definitions: tuple[BlockDefinitionSnapshot, ...]
    options: BlockConditionOptions
    results: tuple[DefinitionMutationResult, ...]


def plan_block_condition_change(request: BlockConditionChangeRequest) -> BlockConditionChangePlan:
    return BlockConditionChangePlan(
        command_alias="BCC",
        legacy_symbol="xiBlockConditionChange",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="DCL exposes layer/color/linetype/scale, nested explode, deletion, and exclusion controls",
        semantic_gaps=(
            "compiled selection traversal and property inheritance remain unknown",
            "caller supplies one exact result for every versioned definition entity",
            "the DCL-backed explicit-result contract does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.DCL_EXACT_RESULT,
        definitions=request.definitions,
        options=request.options,
        results=request.exact_results,
    )


class ExternalDefinitionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_uri: str = Field(min_length=1)
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    definition: BlockDefinitionSnapshot


class ReplacementOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    preserve_rotation: bool
    preserve_scale: bool
    preserve_layer: bool
    replace_nested_references: bool


class ReferenceReplacementResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_result: BlockReferenceSnapshot


class ChangeBlockRequest(ContractRequest):
    references: tuple[BlockReferenceSnapshot, ...] = Field(min_length=1)
    replacement_definition: ExternalDefinitionSnapshot
    options: ReplacementOptions
    exact_results: tuple[ReferenceReplacementResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_replacements(self) -> ChangeBlockRequest:
        sources = {item.handle.casefold(): item for item in self.references}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if (
            len(sources) != len(self.references)
            or len(results) != len(self.exact_results)
            or sources.keys() != results.keys()
        ):
            raise ValueError("BCH requires one unique exact replacement result per reference")
        for key, source in sources.items():
            result = results[key]
            if result.source_revision != source.reference_revision:
                raise ValueError("replacement result must cite the exact source revision")
            target = result.exact_result
            if target.block_name.casefold() != self.replacement_definition.definition.name.casefold():
                raise ValueError("replacement result must reference the supplied external definition")
            if self.options.preserve_rotation and target.rotation_radians != source.rotation_radians:
                raise ValueError("preserve_rotation requires exact source rotation")
            if self.options.preserve_scale and (target.scale_x, target.scale_y, target.scale_z) != (
                source.scale_x,
                source.scale_y,
                source.scale_z,
            ):
                raise ValueError("preserve_scale requires exact source scales")
            if self.options.preserve_layer and target.layer != source.layer:
                raise ValueError("preserve_layer requires exact source layer")
        return self


class ChangeBlockPlan(Batch27BPlan):
    references: tuple[BlockReferenceSnapshot, ...]
    replacement_definition: ExternalDefinitionSnapshot
    options: ReplacementOptions
    results: tuple[ReferenceReplacementResult, ...]


def plan_change_block(request: ChangeBlockRequest) -> ChangeBlockPlan:
    return ChangeBlockPlan(
        command_alias="BCH",
        legacy_symbol="xiChgBlock",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="DCL identifies external block replacement and preserve rotation/scale/layer/nested options",
        semantic_gaps=(
            "external file block selection, dynamic properties, attributes, and nested traversal are compiled",
            "the external content and all resulting references are versioned explicit inputs",
            "the DCL-backed explicit-result contract does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.DCL_EXACT_RESULT,
        references=request.references,
        replacement_definition=request.replacement_definition,
        options=request.options,
        results=request.exact_results,
    )


class ExtractedEntityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_definition: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    source_entity_path: str = Field(min_length=1)
    destination_owner: str = Field(min_length=1)
    exact_result: BlockEntityState


class CopyBlockDefinitionRequest(ContractRequest):
    definitions: tuple[BlockDefinitionSnapshot, ...] = Field(min_length=1)
    exact_extractions: tuple[ExtractedEntityResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_extractions(self) -> CopyBlockDefinitionRequest:
        definitions = {item.name.casefold(): item for item in self.definitions}
        seen: set[tuple[str, str]] = set()
        for item in self.exact_extractions:
            key = item.source_definition.casefold()
            source = definitions.get(key)
            if source is None or item.source_revision != source.definition_revision:
                raise ValueError("extraction must cite a supplied definition and exact revision")
            entity_key = (key, item.source_entity_path.casefold())
            if entity_key in seen or item.source_entity_path.casefold() not in {
                entity.entity_path.casefold() for entity in source.entities
            }:
                raise ValueError("extraction source entity paths must exist and be unique")
            seen.add(entity_key)
        return self


class CopyBlockDefinitionPlan(Batch27BPlan):
    definitions: tuple[BlockDefinitionSnapshot, ...]
    extractions: tuple[ExtractedEntityResult, ...]


def plan_copy_block_definition(request: CopyBlockDefinitionRequest) -> CopyBlockDefinitionPlan:
    return CopyBlockDefinitionPlan(
        command_alias="BCO",
        legacy_symbol="xiBlkCopyDefinition",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and CUI identify extracting objects from inside blocks",
        semantic_gaps=(
            "selection depth, transform composition, property inheritance, and destination are compiled",
            "caller supplies exact extracted entities and destination owners against versioned definitions",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXACT_RESULT,
        definitions=request.definitions,
        extractions=request.exact_extractions,
    )


class ExportFormat(StrEnum):
    DWG = "dwg"
    DXF = "dxf"


class BlockExportResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_name: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    destination_uri: str = Field(min_length=1)
    export_format: ExportFormat
    overwrite: bool
    expected_content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ExportBlockRequest(ContractRequest):
    definitions: tuple[BlockDefinitionSnapshot, ...] = Field(min_length=1)
    exact_exports: tuple[BlockExportResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_exports(self) -> ExportBlockRequest:
        definitions = {item.name.casefold(): item for item in self.definitions}
        destinations: set[str] = set()
        exported: set[str] = set()
        for item in self.exact_exports:
            key = item.source_name.casefold()
            source = definitions.get(key)
            if source is None or item.source_revision != source.definition_revision:
                raise ValueError("export must cite a supplied definition and exact revision")
            destination = item.destination_uri.casefold()
            if key in exported or destination in destinations:
                raise ValueError("exports require unique source definitions and destinations")
            exported.add(key)
            destinations.add(destination)
        return self


class ExportBlockPlan(Batch27BPlan):
    definitions: tuple[BlockDefinitionSnapshot, ...]
    exports: tuple[BlockExportResult, ...]


def plan_export_block(request: ExportBlockRequest) -> ExportBlockPlan:
    return ExportBlockPlan(
        command_alias="BEX",
        legacy_symbol="xiExportBlock",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and CUI identify exporting blocks in the drawing",
        semantic_gaps=(
            "file naming, format/version, units, dependencies, and overwrite behavior are compiled",
            "caller supplies unique destinations and expected digests for versioned definitions",
            "the planner performs no file I/O and does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXACT_RESULT,
        definitions=request.definitions,
        exports=request.exact_exports,
    )


class RebaseBlockRequest(ContractRequest):
    source_definition: BlockDefinitionSnapshot
    references: tuple[BlockReferenceSnapshot, ...] = Field(min_length=1)
    new_base_point: Point3D
    exact_definition: BlockDefinitionSnapshot
    exact_references: tuple[ReferenceReplacementResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rebase(self) -> RebaseBlockRequest:
        if self.new_base_point == self.source_definition.base_point:
            raise ValueError("BIN new base point must differ from the source base point")
        if self.exact_definition.name.casefold() != self.source_definition.name.casefold():
            raise ValueError("BIN exact definition must retain the block name")
        if self.exact_definition.base_point != self.new_base_point:
            raise ValueError("BIN exact definition must use the requested new base point")
        sources = {item.handle.casefold(): item for item in self.references}
        results = {item.source_handle.casefold(): item for item in self.exact_references}
        if (
            len(sources) != len(self.references)
            or len(results) != len(self.exact_references)
            or sources.keys() != results.keys()
        ):
            raise ValueError("BIN requires one unique exact result per reference")
        for key, source in sources.items():
            if source.block_name.casefold() != self.source_definition.name.casefold():
                raise ValueError("BIN references must target the source definition")
            if results[key].source_revision != source.reference_revision:
                raise ValueError("BIN result must cite the exact source reference revision")
        return self


class RebaseBlockPlan(Batch27BPlan):
    source_definition: BlockDefinitionSnapshot
    references: tuple[BlockReferenceSnapshot, ...]
    new_base_point: Point3D
    exact_definition: BlockDefinitionSnapshot
    exact_references: tuple[ReferenceReplacementResult, ...]


def plan_rebase_block(request: RebaseBlockRequest) -> RebaseBlockPlan:
    return RebaseBlockPlan(
        command_alias="BIN",
        legacy_symbol="xiBchin",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and CUI identify changing a block insertion point",
        semantic_gaps=(
            "reference compensation, attribute positions, dynamic blocks, and nested references are compiled",
            "caller supplies the exact rebased definition and every resulting reference",
            "the shortcut-backed explicit-result contract does not claim CAD equivalence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXACT_RESULT,
        source_definition=request.source_definition,
        references=request.references,
        new_base_point=request.new_base_point,
        exact_definition=request.exact_definition,
        exact_references=request.exact_references,
    )


class BlockLayerChangeRequest(ContractRequest):
    definitions: tuple[BlockDefinitionSnapshot, ...] = Field(min_length=1)
    target_layer: str = Field(min_length=1)
    exact_results: tuple[DefinitionMutationResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> BlockLayerChangeRequest:
        _validate_definition_results(self.definitions, self.exact_results)
        for result in self.exact_results:
            if any(
                item.action == EntityAction.DELETE
                or item.exact_result is None
                or item.exact_result.layer != self.target_layer
                for item in result.entity_results
            ):
                raise ValueError("BLA exact results must retain every entity on the target layer")
        return self


class BlockLayerChangePlan(Batch27BPlan):
    definitions: tuple[BlockDefinitionSnapshot, ...]
    target_layer: str
    results: tuple[DefinitionMutationResult, ...]


def plan_block_layer_change(request: BlockLayerChangeRequest) -> BlockLayerChangePlan:
    return BlockLayerChangePlan(
        command_alias="BLA",
        legacy_symbol="xiBLKLAY",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcuts and CUI identify changing all internal block-object layers",
        semantic_gaps=(
            "selection scope, nested traversal, locked/xref/dynamic behavior, and outer reference treatment are compiled",
            "caller supplies one target-layer result for every entity in each versioned definition",
            "xiBlkLayerSet.txt concerns symbol insertion categories and is not treated as BLA behavior evidence",
        ),
        evidence_level=EvidenceLevel.SHORTCUT_EXACT_RESULT,
        definitions=request.definitions,
        target_layer=request.target_layer,
        results=request.exact_results,
    )


def register_headless_core_batch27b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 27B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_bcc", plan_block_condition_change),
        ("xicad_plan_bch", plan_change_block),
        ("xicad_plan_bco", plan_copy_block_definition),
        ("xicad_plan_bex", plan_export_block),
        ("xicad_plan_bin", plan_rebase_block),
        ("xicad_plan_bla", plan_block_layer_change),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
