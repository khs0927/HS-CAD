"""Evidence-bounded dialog-free planners for xiCAD batch 29A xref/layout commands."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval

DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


class EvidenceLevel(StrEnum):
    DCL_EXACT_RESULT = "dcl_backed_explicit_result_not_legacy_equivalent"
    RECOVERED_DCL_EXACT_RESULT = "recovered_dcl_explicit_result_not_legacy_equivalent"
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
        if not self.dry_run and (
            not self.approval.approved or self.approval.fingerprint != self.fingerprint()
        ):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch29APlan(BaseModel):
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


class VersionedEntity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class ExactEntityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    result_id: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


def _unique(values: tuple[str, ...], label: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{label} values must be unique")


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


class NamedDefinitionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol_kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    definition_digest: str = Field(pattern=DIGEST_PATTERN)


class DefinitionRenameResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol_kind: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    result_name: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    result_digest: str = Field(pattern=DIGEST_PATTERN)


class RemoveBindPrefixRequest(ContractRequest):
    definitions: tuple[NamedDefinitionSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[DefinitionRenameResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> RemoveBindPrefixRequest:
        sources = {(item.symbol_kind.casefold(), item.name.casefold()): item for item in self.definitions}
        results = {
            (item.symbol_kind.casefold(), item.source_name.casefold()): item
            for item in self.exact_results
        }
        if len(sources) != len(self.definitions) or len(results) != len(self.exact_results):
            raise ValueError("RBP source and result identities must be unique")
        if sources.keys() != results.keys():
            raise ValueError("RBP requires one exact result per definition")
        _unique(tuple(item.result_name for item in self.exact_results), "RBP result name")
        for key, source in sources.items():
            result = results[key]
            if result.source_revision != source.revision:
                raise ValueError("RBP result must cite the exact source revision")
            if result.result_revision == source.revision or result.result_name == source.name:
                raise ValueError("RBP result must use a changed name and new revision")
        return self


class RemoveBindPrefixPlan(Batch29APlan):
    definitions: tuple[NamedDefinitionSnapshot, ...]
    results: tuple[DefinitionRenameResult, ...]


def plan_remove_bind_prefix(request: RemoveBindPrefixRequest) -> RemoveBindPrefixPlan:
    return RemoveBindPrefixPlan(
        **_base(
            request,
            "RBP",
            "xiRemoveBindPrefix",
            "current/frozen shortcuts and the ZWCAD menu identify removing bound-xref insertion prefixes",
            (
                "the config stores positional values including $0$, but compiled decoding, scope, collisions, and reference rewrites are unknown",
                "caller supplies one exact renamed version for every versioned symbol definition",
                "no command-specific DCL/readable source or CAD equivalence was found",
            ),
            EvidenceLevel.SHORTCUT_EXACT_RESULT,
        ),
        definitions=request.definitions,
        results=request.exact_results,
    )


class WindowSymbolAction(StrEnum):
    INSERT = "insert"
    LIST = "list"
    LOCATE = "locate"
    CHANGE_SYMBOL = "change_symbol"


class WindowSymbolShape(StrEnum):
    CIRCLE = "circle"
    HEXAGON = "hexagon"
    USER_BLOCK = "user_block"


class WindowSymbolChange(StrEnum):
    NAME = "name"
    NUMBER = "number"
    PUSH_NUMBER = "push_number"
    PULL_NUMBER = "pull_number"


class WindowSymbolOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    action: WindowSymbolAction
    shape: WindowSymbolShape
    block_name: str | None = Field(default=None, min_length=1)
    name_tag: str | None = Field(default=None, min_length=1)
    number_tag: str | None = Field(default=None, min_length=1)
    insertion_scale: float = Field(gt=0)
    auto_offset: float | None = Field(default=None, gt=0)
    target_layer: str = Field(min_length=1)
    list_block_gap: float = Field(gt=0)
    list_text_height: float = Field(gt=0)
    change: WindowSymbolChange | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> WindowSymbolOptions:
        custom = (self.block_name, self.name_tag, self.number_tag)
        if self.shape == WindowSymbolShape.USER_BLOCK and any(value is None for value in custom):
            raise ValueError("WSL user block requires block, name-tag, and number-tag values")
        if self.shape != WindowSymbolShape.USER_BLOCK and any(value is not None for value in custom):
            raise ValueError("WSL custom block fields require user_block shape")
        if (self.action == WindowSymbolAction.CHANGE_SYMBOL) != (self.change is not None):
            raise ValueError("WSL change policy is required only for change_symbol action")
        return self


class WindowSymbolRequest(ContractRequest):
    sources: tuple[VersionedEntity, ...]
    options: WindowSymbolOptions
    exact_results: tuple[ExactEntityResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> WindowSymbolRequest:
        _unique(tuple(item.handle for item in self.sources), "WSL source handle")
        _unique(tuple(item.result_id for item in self.exact_results), "WSL result id")
        if self.options.action != WindowSymbolAction.INSERT and not self.sources:
            raise ValueError("WSL non-insert actions require versioned source symbols")
        return self


class WindowSymbolPlan(Batch29APlan):
    sources: tuple[VersionedEntity, ...]
    options: WindowSymbolOptions
    results: tuple[ExactEntityResult, ...]


def plan_window_symbols(request: WindowSymbolRequest) -> WindowSymbolPlan:
    return WindowSymbolPlan(
        **_base(
            request,
            "WSL",
            "xiWinSymList",
            "current/frozen shortcuts, current ZWCAD DCL, config, menu, and WIN-SYM layer data identify window-symbol insert/list/locate/change modes",
            (
                "attribute discovery, ordering, placement, block geometry, numbering propagation, and config positional decoding are compiled",
                "caller supplies all exact resulting entities; DCL choices alone do not prove runtime semantics",
                "CAD equivalence remains unverified",
            ),
            EvidenceLevel.DCL_EXACT_RESULT,
        ),
        sources=request.sources,
        options=request.options,
        results=request.exact_results,
    )


class XclipExplodeMethod(StrEnum):
    CUT_EACH_ENTITY = "cut_each_entity"
    INSERT_BLOCK = "insert_block"


class XrefBindMethod(StrEnum):
    BIND = "bind"
    INSERT = "insert"


class ClippedReferenceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    reference: VersionedEntity
    reference_kind: str = Field(min_length=1)
    clip_boundary_digest: str = Field(pattern=DIGEST_PATTERN)
    source_definition_revision: str = Field(min_length=1)


class XclipExplodeResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_entities: tuple[ExactEntityResult, ...] = Field(min_length=1)
    source_deleted: bool


class XclipExplodeRequest(ContractRequest):
    references: tuple[ClippedReferenceSnapshot, ...] = Field(min_length=1)
    method: XclipExplodeMethod
    xref_bind_method: XrefBindMethod | None = None
    exact_results: tuple[XclipExplodeResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> XclipExplodeRequest:
        sources = {item.reference.handle.casefold(): item for item in self.references}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if len(sources) != len(self.references) or len(results) != len(self.exact_results):
            raise ValueError("XCX source/result identities must be unique")
        if sources.keys() != results.keys():
            raise ValueError("XCX requires one explicit result per clipped reference")
        has_xref = any(item.reference_kind.casefold() == "xref" for item in self.references)
        if has_xref != (self.xref_bind_method is not None):
            raise ValueError("XCX bind method is required exactly when an xref source is present")
        for key, source in sources.items():
            result = results[key]
            if result.source_revision != source.reference.revision:
                raise ValueError("XCX result must cite the exact source revision")
            if not result.source_deleted:
                raise ValueError("XCX explode result must explicitly delete its source reference")
            _unique(tuple(item.result_id for item in result.exact_entities), "XCX result entity")
        return self


class XclipExplodePlan(Batch29APlan):
    references: tuple[ClippedReferenceSnapshot, ...]
    method: XclipExplodeMethod
    xref_bind_method: XrefBindMethod | None
    results: tuple[XclipExplodeResult, ...]


def plan_xclip_explode(request: XclipExplodeRequest) -> XclipExplodePlan:
    return XclipExplodePlan(
        **_base(
            request,
            "XCX",
            "xiXclipXplode",
            "current/frozen shortcuts and menu identify XCLIP explode/cleanup; an AutoSave DCL recovers two operation and two xref-bind choices",
            (
                "the recovered DCL is not present in the active DialogBox tree and is not treated as current-runtime proof",
                "clipping, explode topology, transforms, binding, cleanup, and transaction recovery are compiled; caller supplies all exact entities",
                "CAD equivalence remains unverified",
            ),
            EvidenceLevel.RECOVERED_DCL_EXACT_RESULT,
        ),
        references=request.references,
        method=request.method,
        xref_bind_method=request.xref_bind_method,
        results=request.exact_results,
    )


class XrefLayerSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    xref_name: str = Field(min_length=1)
    layer_name: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)
    is_off: bool
    is_frozen: bool


class ExactLayerResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    xref_name: str = Field(min_length=1)
    layer_name: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    result_digest: str = Field(pattern=DIGEST_PATTERN)


def _validate_layer_results(
    snapshots: tuple[XrefLayerSnapshot, ...], results: tuple[ExactLayerResult, ...], label: str
) -> None:
    sources = {(item.xref_name.casefold(), item.layer_name.casefold()): item for item in snapshots}
    outputs = {(item.xref_name.casefold(), item.layer_name.casefold()): item for item in results}
    if len(sources) != len(snapshots) or len(outputs) != len(results):
        raise ValueError(f"{label} layer identities must be unique")
    if sources.keys() != outputs.keys():
        raise ValueError(f"{label} requires one exact result per layer snapshot")
    for key, source in sources.items():
        result = outputs[key]
        if result.source_revision != source.revision or result.result_revision == source.revision:
            raise ValueError(f"{label} results must cite each source and use new revisions")


class XrefColorScope(StrEnum):
    ALL = "all"
    SELECTED = "selected"


class XrefColorOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    restore: bool
    scope: XrefColorScope
    color_index: int | None = Field(default=None, ge=0, le=256)
    linetype: str | None = Field(default=None, min_length=1)
    include_nested_xrefs: bool
    include_forced_entity_properties: bool
    exclude_off_or_frozen_layers: bool
    excluded_layer_names: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_options(self) -> XrefColorOptions:
        _unique(self.excluded_layer_names, "XRC excluded layer")
        if not self.restore and self.color_index is None and self.linetype is None:
            raise ValueError("XRC change mode requires color and/or linetype")
        return self


class XrefColorRequest(ContractRequest):
    layers: tuple[XrefLayerSnapshot, ...] = Field(min_length=1)
    options: XrefColorOptions
    exact_results: tuple[ExactLayerResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> XrefColorRequest:
        _validate_layer_results(self.layers, self.exact_results, "XRC")
        excluded = {item.casefold() for item in self.options.excluded_layer_names}
        if any(item.layer_name.casefold() in excluded for item in self.layers):
            raise ValueError("XRC result snapshots must already exclude explicitly excluded layers")
        if self.options.exclude_off_or_frozen_layers and any(
            item.is_off or item.is_frozen for item in self.layers
        ):
            raise ValueError("XRC result snapshots must exclude off/frozen layers when requested")
        return self


class XrefColorPlan(Batch29APlan):
    layers: tuple[XrefLayerSnapshot, ...]
    options: XrefColorOptions
    results: tuple[ExactLayerResult, ...]


def plan_xref_color(request: XrefColorRequest) -> XrefColorPlan:
    return XrefColorPlan(
        **_base(
            request,
            "XRC",
            "xiXrefColor",
            "current/frozen shortcuts and menu identify bulk xref color changes; an AutoSave DCL recovers scope/color/linetype/nesting/override/exclusion controls",
            (
                "the recovered ACAD DCL is absent from the active DialogBox tree and cannot establish current ZWCAD defaults",
                "layer traversal, restore storage, override precedence, reload, and entity-level effects are compiled; caller supplies exact layer revisions",
                "CAD equivalence remains unverified",
            ),
            EvidenceLevel.RECOVERED_DCL_EXACT_RESULT,
        ),
        layers=request.layers,
        options=request.options,
        results=request.exact_results,
    )


class ResetXrefLayersRequest(ContractRequest):
    layers: tuple[XrefLayerSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[ExactLayerResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> ResetXrefLayersRequest:
        _validate_layer_results(self.layers, self.exact_results, "XRR")
        return self


class ResetXrefLayersPlan(Batch29APlan):
    layers: tuple[XrefLayerSnapshot, ...]
    results: tuple[ExactLayerResult, ...]


def plan_reset_xref_layers(request: ResetXrefLayersRequest) -> ResetXrefLayersPlan:
    return ResetXrefLayersPlan(
        **_base(
            request,
            "XRR",
            "xiResetXRefLayers",
            "current/frozen shortcuts and the ZWCAD menu identify resetting xref layer settings",
            (
                "the config value 527 is opaque; reset fields, VISRETAIN interaction, nesting, overrides, and reload behavior are compiled",
                "caller supplies one exact new version for every affected xref layer and no default state is invented",
                "no command-specific DCL/readable source or CAD equivalence was found",
            ),
            EvidenceLevel.SHORTCUT_EXACT_RESULT,
        ),
        layers=request.layers,
        results=request.exact_results,
    )


class LayoutSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    paper_space_digest: str = Field(pattern=DIGEST_PATTERN)
    viewport_digest: str = Field(pattern=DIGEST_PATTERN)
    source_entities: tuple[VersionedEntity, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_entities(self) -> LayoutSnapshot:
        _unique(tuple(item.handle for item in self.source_entities), "P2M source handle")
        return self


class LayoutToModelResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    layout_name: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_model_entities: tuple[ExactEntityResult, ...] = Field(min_length=1)
    expected_model_space_revision: str = Field(min_length=1)
    expected_model_space_digest: str = Field(pattern=DIGEST_PATTERN)


class PaperToModelRequest(ContractRequest):
    model_space_revision: str = Field(min_length=1)
    model_space_digest: str = Field(pattern=DIGEST_PATTERN)
    layouts: tuple[LayoutSnapshot, ...] = Field(min_length=1)
    exact_results: tuple[LayoutToModelResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> PaperToModelRequest:
        sources = {item.name.casefold(): item for item in self.layouts}
        results = {item.layout_name.casefold(): item for item in self.exact_results}
        if len(sources) != len(self.layouts) or len(results) != len(self.exact_results):
            raise ValueError("P2M layout identities must be unique")
        if sources.keys() != results.keys():
            raise ValueError("P2M requires one explicit result per layout")
        revisions: list[str] = []
        for key, source in sources.items():
            result = results[key]
            if result.source_revision != source.revision:
                raise ValueError("P2M result must cite the exact layout revision")
            if result.expected_model_space_revision == self.model_space_revision:
                raise ValueError("P2M result must use a new model-space revision")
            _unique(tuple(item.result_id for item in result.exact_model_entities), "P2M result entity")
            revisions.append(result.expected_model_space_revision)
        _unique(tuple(revisions), "P2M sequential model-space revision")
        return self


class PaperToModelPlan(Batch29APlan):
    model_space_revision: str
    model_space_digest: str
    layouts: tuple[LayoutSnapshot, ...]
    results: tuple[LayoutToModelResult, ...]


def plan_paper_to_model(request: PaperToModelRequest) -> PaperToModelPlan:
    return PaperToModelPlan(
        **_base(
            request,
            "P2M",
            "xiPsp2Msp",
            "current/frozen shortcuts and the ZWCAD menu identify exporting layout drawings to model space",
            (
                "layout selection, viewport projection/clipping, annotation scale, duplicate model geometry, ordering, and source retention are compiled",
                "caller supplies versioned layout/viewports and every exact model-space result with expected revision/digest",
                "the planner mutates no drawing and claims no CAD equivalence",
            ),
            EvidenceLevel.SHORTCUT_EXACT_RESULT,
        ),
        model_space_revision=request.model_space_revision,
        model_space_digest=request.model_space_digest,
        layouts=request.layouts,
        results=request.exact_results,
    )


def register_headless_core_batch29a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 29A Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_rbp", plan_remove_bind_prefix),
        ("xicad_plan_wsl", plan_window_symbols),
        ("xicad_plan_xcx", plan_xclip_explode),
        ("xicad_plan_xrc", plan_xref_color),
        ("xicad_plan_xrr", plan_reset_xref_layers),
        ("xicad_plan_p2m", plan_paper_to_model),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
