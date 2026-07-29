"""Evidence-bounded dialog-free planners for xiCAD batch 27A.

The compiled commands expose labels but not their implementation.  Every
block, xref, symbol, and file result is consequently explicit, versioned input.
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
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    @model_validator(mode="after")
    def validate_approval(self) -> ContractRequest:
        if not self.dry_run and (not self.approval.approved or self.approval.fingerprint != self.fingerprint()):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch27APlan(BaseModel):
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


class EntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    geometry_revision: str = Field(min_length=1)
    layer: str = Field(min_length=1)


class ProposedEntity(BaseModel):
    """Exact adapter-ready output encoded without mutable/unordered mappings."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    output_id: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    geometry_payload: tuple[tuple[str, str], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_payload(self) -> ProposedEntity:
        keys = [item[0].casefold() for item in self.geometry_payload]
        if any(not item[0] for item in self.geometry_payload) or len(keys) != len(set(keys)):
            raise ValueError("proposed entity payload keys must be non-empty and unique")
        return self


class BlockReferenceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    block_name: str = Field(min_length=1)
    definition_revision: str = Field(min_length=1)
    reference_revision: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)


def _unique(values: tuple[str, ...], label: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{label} values must be unique")


def _base(request: ContractRequest, alias: str, symbol: str, description: str) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "legacy_symbol": symbol,
        "document_id": request.document_id,
        "dry_run": request.dry_run,
        "request_fingerprint": request.fingerprint(),
        "semantic_evidence": (
            f"current/frozen shortcuts identify {symbol} as {description}; CAD menu evidence exists where cataloged"
        ),
        "semantic_gaps": (
            "no command-specific DCL/config/data/readable source was found",
            "selection, naming, property inheritance, geometry conversion, and error behavior are compiled",
            "all versioned sources and exact outputs are caller supplied; no legacy equivalence is claimed",
        ),
    }


class SymbolDrawRequest(ContractRequest):
    symbol_kind: str = Field(min_length=1)
    insertion_point: Point3D
    exact_entities: tuple[ProposedEntity, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_outputs(self) -> SymbolDrawRequest:
        _unique(tuple(item.output_id for item in self.exact_entities), "XZ output")
        return self


class SymbolDrawPlan(Batch27APlan):
    symbol_kind: str
    insertion_point: Point3D
    creates: tuple[ProposedEntity, ...]


def plan_xz_symbol(request: SymbolDrawRequest) -> SymbolDrawPlan:
    return SymbolDrawPlan(
        **_base(request, "XZ", "xiXZ", "drawing an XZ symbol"),
        symbol_kind=request.symbol_kind,
        insertion_point=request.insertion_point,
        creates=request.exact_entities,
    )


class ExplodedBlockResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_block_handle: str = Field(min_length=1)
    exact_entities: tuple[ProposedEntity, ...] = Field(min_length=1)


class AllBlocksExplodeRequest(ContractRequest):
    blocks: tuple[BlockReferenceSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[ExplodedBlockResult, ...] = Field(min_length=1)
    delete_source_blocks: bool = True

    @model_validator(mode="after")
    def validate_results(self) -> AllBlocksExplodeRequest:
        source = [item.handle.casefold() for item in self.blocks]
        result = [item.source_block_handle.casefold() for item in self.exact_results]
        if len(source) != len(set(source)) or len(result) != len(set(result)) or set(source) != set(result):
            raise ValueError("ABX requires one unique exact result per versioned block")
        _unique(tuple(e.output_id for r in self.exact_results for e in r.exact_entities), "ABX output")
        if not self.delete_source_blocks:
            raise ValueError("ABX explode contract requires explicit source block deletion")
        return self


class AllBlocksExplodePlan(Batch27APlan):
    blocks: tuple[BlockReferenceSnapshot, ...]
    results: tuple[ExplodedBlockResult, ...]
    delete_handles: tuple[str, ...]


def plan_all_blocks_explode(request: AllBlocksExplodeRequest) -> AllBlocksExplodePlan:
    return AllBlocksExplodePlan(
        **_base(request, "ABX", "xiAllBlockExplode", "exploding all internal blocks"),
        blocks=request.blocks,
        results=request.exact_results,
        delete_handles=tuple(item.handle for item in request.blocks),
    )


class ProposedXref(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    file_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    reference_output_id: str = Field(min_length=1)


class BlockToXrefRequest(ContractRequest):
    source: BlockReferenceSnapshot
    target_path: str = Field(min_length=1)
    target_revision_before: str = Field(min_length=1)
    overwrite_existing: bool
    exact_file_entities: tuple[ProposedEntity, ...] = Field(min_length=1)
    exact_xref: ProposedXref
    delete_source_block: bool = True

    @model_validator(mode="after")
    def validate_file_plan(self) -> BlockToXrefRequest:
        if self.exact_xref.path != self.target_path:
            raise ValueError("B2X xref path must equal the explicit target path")
        if not self.delete_source_block:
            raise ValueError("B2X conversion requires explicit source block deletion")
        _unique(tuple(item.output_id for item in self.exact_file_entities), "B2X file output")
        return self


class BlockToXrefPlan(Batch27APlan):
    source: BlockReferenceSnapshot
    target_path: str
    target_revision_before: str
    overwrite_existing: bool
    file_entities: tuple[ProposedEntity, ...]
    xref: ProposedXref
    delete_handle: str


def plan_block_to_xref(request: BlockToXrefRequest) -> BlockToXrefPlan:
    return BlockToXrefPlan(
        **_base(request, "B2X", "xiBlock2Xref", "converting a block to an external reference"),
        source=request.source,
        target_path=request.target_path,
        target_revision_before=request.target_revision_before,
        overwrite_existing=request.overwrite_existing,
        file_entities=request.exact_file_entities,
        xref=request.exact_xref,
        delete_handle=request.source.handle,
    )


class BlockDefinitionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    definition_revision: str = Field(min_length=1)
    member_source_handles: tuple[str, ...]

    @model_validator(mode="after")
    def validate_members(self) -> BlockDefinitionSnapshot:
        _unique(self.member_source_handles, "block member")
        return self


class AddObjectsToBlockRequest(ContractRequest):
    definition: BlockDefinitionSnapshot
    added_entities: tuple[EntitySnapshot, ...] = Field(min_length=1)
    exact_definition_revision_after: str = Field(min_length=1)
    exact_member_source_handles_after: tuple[str, ...] = Field(min_length=1)
    delete_added_entities_from_space: bool = True

    @model_validator(mode="after")
    def validate_revision(self) -> AddObjectsToBlockRequest:
        added = tuple(item.handle for item in self.added_entities)
        _unique(added, "BAD added entity")
        if self.exact_definition_revision_after == self.definition.definition_revision:
            raise ValueError("BAD revised definition must have a new revision")
        expected = {x.casefold() for x in (*self.definition.member_source_handles, *added)}
        actual = {x.casefold() for x in self.exact_member_source_handles_after}
        if len(actual) != len(self.exact_member_source_handles_after) or actual != expected:
            raise ValueError("BAD exact members must equal old members plus added entities")
        if not self.delete_added_entities_from_space:
            raise ValueError("BAD inclusion requires explicit source-space deletion")
        return self


class AddObjectsToBlockPlan(Batch27APlan):
    definition: BlockDefinitionSnapshot
    added_entities: tuple[EntitySnapshot, ...]
    definition_revision_after: str
    member_source_handles_after: tuple[str, ...]
    delete_handles: tuple[str, ...]


def plan_add_objects_to_block(request: AddObjectsToBlockRequest) -> AddObjectsToBlockPlan:
    return AddObjectsToBlockPlan(
        **_base(request, "BAD", "xiADDB", "including objects in a block"),
        definition=request.definition,
        added_entities=request.added_entities,
        definition_revision_after=request.exact_definition_revision_after,
        member_source_handles_after=request.exact_member_source_handles_after,
        delete_handles=tuple(item.handle for item in request.added_entities),
    )


class ProposedBlockDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    definition_revision: str = Field(min_length=1)
    base_point: Point3D
    exact_entities: tuple[ProposedEntity, ...] = Field(min_length=1)


class ProposedBlockReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    output_id: str = Field(min_length=1)
    block_name: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)


class BlockAutoMakeRequest(ContractRequest):
    sources: tuple[EntitySnapshot, ...] = Field(min_length=1)
    exact_definition: ProposedBlockDefinition
    exact_reference: ProposedBlockReference
    delete_sources: bool = True

    @model_validator(mode="after")
    def validate_block(self) -> BlockAutoMakeRequest:
        _unique(tuple(item.handle for item in self.sources), "BAM source")
        _unique(tuple(item.output_id for item in self.exact_definition.exact_entities), "BAM output")
        if self.exact_reference.block_name != self.exact_definition.name:
            raise ValueError("BAM reference must name the exact proposed definition")
        if not self.delete_sources:
            raise ValueError("BAM replacement requires explicit source deletion")
        return self


class BlockAutoMakePlan(Batch27APlan):
    sources: tuple[EntitySnapshot, ...]
    definition: ProposedBlockDefinition
    reference: ProposedBlockReference
    delete_handles: tuple[str, ...]


def plan_block_auto_make(request: BlockAutoMakeRequest) -> BlockAutoMakePlan:
    return BlockAutoMakePlan(
        **_base(request, "BAM", "xiBlockAutoMake", "automatically making a block"),
        sources=request.sources,
        definition=request.exact_definition,
        reference=request.exact_reference,
        delete_handles=tuple(item.handle for item in request.sources),
    )


class LineBetweenBlocksRequest(ContractRequest):
    blocks: tuple[BlockReferenceSnapshot, ...] = Field(min_length=2)
    ordered_handles: tuple[str, ...] = Field(min_length=2)
    output_layer: str = Field(min_length=1)
    closed: bool = False

    @model_validator(mode="after")
    def validate_order(self) -> LineBetweenBlocksRequest:
        source = [item.handle.casefold() for item in self.blocks]
        order = [item.casefold() for item in self.ordered_handles]
        if len(source) != len(set(source)) or len(order) != len(set(order)) or set(source) != set(order):
            raise ValueError("BBL ordering must reference every block exactly once")
        return self


class LineBetweenBlocksPlan(Batch27APlan):
    ordered_handles: tuple[str, ...]
    vertices: tuple[Point3D, ...]
    output_layer: str
    closed: bool


def plan_line_between_blocks(request: LineBetweenBlocksRequest) -> LineBetweenBlocksPlan:
    by_handle = {item.handle.casefold(): item for item in request.blocks}
    vertices = tuple(by_handle[item.casefold()].insertion_point for item in request.ordered_handles)
    return LineBetweenBlocksPlan(
        **_base(request, "BBL", "xiLineBetweenBlock", "joining block insertion points with a line"),
        ordered_handles=request.ordered_handles,
        vertices=vertices,
        output_layer=request.output_layer,
        closed=request.closed,
    )


def register_headless_core_batch27a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 27A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_xz", plan_xz_symbol),
        ("xicad_plan_abx", plan_all_blocks_explode),
        ("xicad_plan_b2x", plan_block_to_xref),
        ("xicad_plan_bad", plan_add_objects_to_block),
        ("xicad_plan_bam", plan_block_auto_make),
        ("xicad_plan_bbl", plan_line_between_blocks),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
