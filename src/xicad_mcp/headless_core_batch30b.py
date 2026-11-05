"""Evidence-bounded dialog-free planners for xiCAD batch 30B file/plot commands."""

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
    HELP_EXACT_RESULT = "help_backed_explicit_result_not_legacy_equivalent"
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


class Batch30BPlan(BaseModel):
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


def _unique(values: tuple[str, ...], label: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{label} values must be unique")


class FileFormat(StrEnum):
    DWG = "dwg"
    DXF = "dxf"
    IMAGE = "image"
    PDF = "pdf"
    OTHER = "other"


class VersionedFileSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    content_digest: str = Field(pattern=DIGEST_PATTERN)
    format: FileFormat
    is_saved: bool
    is_open: bool = False


class VersionedEntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class ExactEntityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    result_id: str = Field(min_length=1)
    result_revision: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    state_digest: str = Field(pattern=DIGEST_PATTERN)


class InsertMode(StrEnum):
    BLOCK = "block"
    XREF = "xref"
    IMAGE = "image"
    PDF_UNDERLAY = "pdf_underlay"
    PDF_VECTOR = "pdf_vector"


class XrefDisposition(StrEnum):
    REMAIN = "remain"
    BIND = "bind"
    INSERT = "insert"


class InsertFileResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_path: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    exact_entities: tuple[ExactEntityResult, ...] = Field(min_length=1)
    result_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


class InsertBlocksRequest(ContractRequest):
    files: tuple[VersionedFileSnapshot, ...] = Field(min_length=1)
    insert_mode: InsertMode
    xref_disposition: XrefDisposition | None = None
    explode_inserted_drawings: bool
    redefine_same_name_blocks: bool
    order_policy: str = Field(min_length=1)
    items_per_row: int = Field(gt=0)
    horizontal_gap: float = Field(ge=0)
    vertical_gap: float = Field(ge=0)
    image_width: float = Field(gt=0)
    exact_results: tuple[InsertFileResult, ...] = Field(min_length=1)
    cad_platform: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> InsertBlocksRequest:
        files = {item.path.casefold(): item for item in self.files}
        results = {item.source_path.casefold(): item for item in self.exact_results}
        if len(files) != len(self.files) or len(results) != len(self.exact_results):
            raise ValueError("IB file and result paths must be unique")
        if files.keys() != results.keys():
            raise ValueError("IB requires one exact result per input file")
        if (self.insert_mode == InsertMode.XREF) != (self.xref_disposition is not None):
            raise ValueError("IB xref disposition is required exactly for xref mode")
        formats = {item.format for item in self.files}
        if FileFormat.PDF in formats and self.insert_mode not in {
            InsertMode.PDF_UNDERLAY,
            InsertMode.PDF_VECTOR,
        }:
            raise ValueError("IB PDF files require an explicit PDF insertion mode")
        if FileFormat.PDF not in formats and self.insert_mode in {
            InsertMode.PDF_UNDERLAY,
            InsertMode.PDF_VECTOR,
        }:
            raise ValueError("IB PDF insertion modes require PDF-only inputs")
        if self.insert_mode == InsertMode.PDF_VECTOR and self.cad_platform.casefold() in {
            "zwcad",
            "gstarcad",
        }:
            raise ValueError("IB help documents PDF vector import as unavailable on this platform")
        for key, source in files.items():
            result = results[key]
            if not source.is_saved:
                raise ValueError("IB DCL states that only saved files are valid")
            if result.source_revision != source.revision:
                raise ValueError("IB result must cite the exact file revision")
            _unique(tuple(item.result_id for item in result.exact_entities), "IB result entity")
        return self


class InsertBlocksPlan(Batch30BPlan):
    files: tuple[VersionedFileSnapshot, ...]
    insert_mode: InsertMode
    xref_disposition: XrefDisposition | None
    exact_results: tuple[InsertFileResult, ...]


def plan_insert_blocks(request: InsertBlocksRequest) -> InsertBlocksPlan:
    return InsertBlocksPlan(
        **_base(
            request,
            "IB",
            "xiInsertBlks",
            "current/frozen shortcuts, ZWCAD menu, current ZWCAD DCL/xiConfig, and official help identify multi-file DWG/DXF/image/PDF insertion and arrangement controls",
            (
                "folder enumeration, image/PDF probing, block naming, transforms, four icon order meanings, binding, explode, and collision handling are compiled",
                "caller supplies saved versioned file snapshots and every exact resulting entity; the planner performs no file reads or CAD insertion",
                "the DCL-backed explicit-result contract does not claim CAD equivalence",
            ),
            EvidenceLevel.DCL_EXACT_RESULT,
        ),
        files=request.files,
        insert_mode=request.insert_mode,
        xref_disposition=request.xref_disposition,
        exact_results=request.exact_results,
    )


class SaveMode(StrEnum):
    SAVE = "save"
    SAVE_AS = "save_as"
    NO_SAVE = "no_save"


class OrganizedFileResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_path: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    destination_path: str | None = Field(default=None, min_length=1)
    output_revision: str = Field(min_length=1)
    output_digest: str = Field(pattern=DIGEST_PATTERN)
    persisted: bool


class MultiFileOrganizeRequest(ContractRequest):
    files: tuple[VersionedFileSnapshot, ...] = Field(min_length=1)
    save_mode: SaveMode
    save_as_folder: str | None = Field(default=None, min_length=1)
    current_file_only: bool
    script_commands: tuple[str, ...] = ()
    operation_manifest_digest: str = Field(pattern=DIGEST_PATTERN)
    exact_results: tuple[OrganizedFileResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> MultiFileOrganizeRequest:
        files = {item.path.casefold(): item for item in self.files}
        results = {item.source_path.casefold(): item for item in self.exact_results}
        if len(files) != len(self.files) or len(results) != len(self.exact_results):
            raise ValueError("MSL source and result paths must be unique")
        if files.keys() != results.keys():
            raise ValueError("MSL requires one exact result per source file")
        destinations = tuple(item.destination_path for item in self.exact_results if item.destination_path is not None)
        _unique(destinations, "MSL destination path")
        if (self.save_mode == SaveMode.SAVE_AS) != (self.save_as_folder is not None):
            raise ValueError("MSL save-as folder is required exactly for save_as mode")
        for key, source in files.items():
            if results[key].source_revision != source.revision:
                raise ValueError("MSL result must cite the exact source revision")
            if not self.current_file_only and source.is_open:
                raise ValueError("MSL help excludes open files from the file-list workflow")
            result = results[key]
            if self.save_mode == SaveMode.NO_SAVE:
                if result.persisted or result.destination_path is not None:
                    raise ValueError("MSL no_save results must not claim a persisted destination")
            elif not result.persisted or result.destination_path is None:
                raise ValueError("MSL save results require a persisted destination")
        return self


class MultiFileOrganizePlan(Batch30BPlan):
    files: tuple[VersionedFileSnapshot, ...]
    save_mode: SaveMode
    current_file_only: bool
    script_commands: tuple[str, ...]
    operation_manifest_digest: str
    results: tuple[OrganizedFileResult, ...]


def plan_multi_file_organize(request: MultiFileOrganizeRequest) -> MultiFileOrganizePlan:
    return MultiFileOrganizePlan(
        **_base(
            request,
            "MSL",
            "xiMSlide",
            "current/frozen shortcuts, ZWCAD menu, and official help identify opening drawings to run cleanup/script operations with save, save-as, or no-save handling",
            (
                "the active dialog was not found locally; cleanup option fields, execution order, script safety, name collision numbering, and failure recovery remain compiled",
                "caller supplies an opaque operation manifest plus content-addressed exact results; the planner opens no drawings and performs no filesystem I/O",
                "official help says file-list inputs exclude open files and save-as name collisions gain numeric suffixes, but CAD equivalence remains unverified",
            ),
            EvidenceLevel.HELP_EXACT_RESULT,
        ),
        files=request.files,
        save_mode=request.save_mode,
        current_file_only=request.current_file_only,
        script_commands=request.script_commands,
        operation_manifest_digest=request.operation_manifest_digest,
        results=request.exact_results,
    )


class PlotBoxCreateRequest(ContractRequest):
    target_owner: str = Field(min_length=1)
    target_owner_revision: str = Field(min_length=1)
    exact_plot_box: ExactEntityResult


class PlotBoxCreatePlan(Batch30BPlan):
    target_owner: str
    target_owner_revision: str
    result: ExactEntityResult


def plan_plot_box_create(request: PlotBoxCreateRequest) -> PlotBoxCreatePlan:
    if not request.exact_plot_box.layer.casefold().startswith("plot_box"):
        raise ValueError("PB exact plot box must use a PLOT_BOX* layer")
    if request.exact_plot_box.owner.casefold() != request.target_owner.casefold():
        raise ValueError("PB exact plot box must belong to the target owner")
    return PlotBoxCreatePlan(
        **_base(
            request,
            "PB",
            "xiPlotBox",
            "current/frozen shortcuts, ZWCAD menu, AutoPlot DCL, and official PPP help identify drawing one rectangle on a PLOT_BOX* layer",
            (
                "point acquisition, rectangle geometry, entity type, layer, metadata, and current-space behavior are compiled",
                "caller supplies the exact plot-box entity bound to a target owner revision; no geometry is inferred",
                "the shortcut-backed explicit-result contract does not claim CAD equivalence",
            ),
            EvidenceLevel.SHORTCUT_EXACT_RESULT,
        ),
        target_owner=request.target_owner,
        target_owner_revision=request.target_owner_revision,
        result=request.exact_plot_box,
    )


class DeletedEntityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    deleted: bool


class DeletePlotBoxesRequest(ContractRequest):
    owner: str = Field(min_length=1)
    owner_revision: str = Field(min_length=1)
    complete_plot_box_handles: tuple[str, ...] = Field(min_length=1)
    plot_boxes: tuple[VersionedEntitySnapshot, ...] = Field(min_length=1)
    exact_results: tuple[DeletedEntityResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> DeletePlotBoxesRequest:
        sources = {item.handle.casefold(): item for item in self.plot_boxes}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        handles = {item.casefold() for item in self.complete_plot_box_handles}
        if (
            len(sources) != len(self.plot_boxes)
            or len(results) != len(self.exact_results)
            or len(handles) != len(self.complete_plot_box_handles)
            or sources.keys() != results.keys()
            or sources.keys() != handles
        ):
            raise ValueError("PBD requires one complete unique owner-scope plot-box/result set")
        for key, source in sources.items():
            result = results[key]
            if source.owner.casefold() != self.owner.casefold():
                raise ValueError("PBD plot boxes must belong to the declared owner")
            if not source.layer.casefold().startswith("plot_box"):
                raise ValueError("PBD complete scope may contain only PLOT_BOX* layer entities")
            if result.source_revision != source.revision or not result.deleted:
                raise ValueError("PBD result must cite each exact revision and explicitly delete it")
        return self


class DeletePlotBoxesPlan(Batch30BPlan):
    owner: str
    owner_revision: str
    plot_boxes: tuple[VersionedEntitySnapshot, ...]
    results: tuple[DeletedEntityResult, ...]


def plan_delete_plot_boxes(request: DeletePlotBoxesRequest) -> DeletePlotBoxesPlan:
    return DeletePlotBoxesPlan(
        **_base(
            request,
            "PBD",
            "xiDelPlotBox",
            "current/frozen shortcuts, ZWCAD menu, AutoPlot DCL, and official PPP help identify deleting PLOT_BOX* layer objects",
            (
                "plot-box identification metadata, layout/model scope, locked-layer behavior, and transaction semantics are compiled",
                "caller attests the complete versioned owner scope and explicitly marks every exact source for deletion",
                "the shortcut-backed explicit-result contract does not claim CAD equivalence",
            ),
            EvidenceLevel.SHORTCUT_EXACT_RESULT,
        ),
        owner=request.owner,
        owner_revision=request.owner_revision,
        plot_boxes=request.plot_boxes,
        results=request.exact_results,
    )


class PlotBoxConversionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    source_retained: bool
    exact_plot_box: ExactEntityResult


class PlotBoxMultiMakeRequest(ContractRequest):
    poly_boxes: tuple[VersionedEntitySnapshot, ...] = Field(min_length=1)
    exact_results: tuple[PlotBoxConversionResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> PlotBoxMultiMakeRequest:
        sources = {item.handle.casefold(): item for item in self.poly_boxes}
        results = {item.source_handle.casefold(): item for item in self.exact_results}
        if len(sources) != len(self.poly_boxes) or len(results) != len(self.exact_results):
            raise ValueError("PBM source and result handles must be unique")
        if sources.keys() != results.keys():
            raise ValueError("PBM requires one exact plot-box result per poly-box")
        for key, source in sources.items():
            if "polyline" not in source.entity_type.casefold():
                raise ValueError("PBM sources must be explicit polyline snapshots")
            if results[key].source_revision != source.revision:
                raise ValueError("PBM result must cite the exact source revision")
            if not results[key].exact_plot_box.layer.casefold().startswith("plot_box"):
                raise ValueError("PBM exact result must use a PLOT_BOX* layer")
        _unique(tuple(item.exact_plot_box.result_id for item in self.exact_results), "PBM result")
        return self


class PlotBoxMultiMakePlan(Batch30BPlan):
    poly_boxes: tuple[VersionedEntitySnapshot, ...]
    results: tuple[PlotBoxConversionResult, ...]


def plan_plot_box_multi_make(request: PlotBoxMultiMakeRequest) -> PlotBoxMultiMakePlan:
    return PlotBoxMultiMakePlan(
        **_base(
            request,
            "PBM",
            "xiPlotBoxMultiMake",
            "current/frozen shortcuts, ZWCAD menu, and official PBM/PPP help identify overlaying ordinary polylines with PLOT_BOX-layer borders",
            (
                "polyline eligibility, closure/tolerance, plot-box properties/metadata, and source retention defaults are compiled",
                "caller supplies every source-retention decision and complete exact plot-box entity",
                "no command-specific DCL/config/data/readable source or CAD equivalence was found",
            ),
            EvidenceLevel.SHORTCUT_EXACT_RESULT,
        ),
        poly_boxes=request.poly_boxes,
        results=request.exact_results,
    )


class PlotFrameSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    frame_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    geometry_digest: str = Field(pattern=DIGEST_PATTERN)
    source_document_path: str = Field(min_length=1)
    source_document_revision: str = Field(min_length=1)


class PlotSettingsSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    config_revision: str = Field(min_length=1)
    config_digest: str = Field(pattern=DIGEST_PATTERN)
    plotter_name: str = Field(min_length=1)
    paper_name: str = Field(min_length=1)
    style_sheet: str = Field(min_length=1)
    copies: int = Field(gt=0)
    scale_policy: str = Field(min_length=1)
    rotation_policy: str = Field(min_length=1)
    location_policy: str = Field(min_length=1)
    output_policy: str = Field(min_length=1)


class PlotArtifactResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    frame_id: str = Field(min_length=1)
    frame_revision: str = Field(min_length=1)
    settings_revision: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    artifact_digest: str = Field(pattern=DIGEST_PATTERN)
    plot_manifest_digest: str = Field(pattern=DIGEST_PATTERN)


class AutoPlotRequest(ContractRequest):
    frames: tuple[PlotFrameSnapshot, ...] = Field(min_length=1)
    settings: PlotSettingsSnapshot
    exact_results: tuple[PlotArtifactResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_results(self) -> AutoPlotRequest:
        frames = {item.frame_id.casefold(): item for item in self.frames}
        results = {item.frame_id.casefold(): item for item in self.exact_results}
        if len(frames) != len(self.frames) or len(results) != len(self.exact_results):
            raise ValueError("PPP frame and result identities must be unique")
        if frames.keys() != results.keys():
            raise ValueError("PPP requires one explicit artifact result per frame")
        _unique(tuple(item.output_path for item in self.exact_results), "PPP output path")
        for key, frame in frames.items():
            result = results[key]
            if result.frame_revision != frame.revision:
                raise ValueError("PPP result must cite the exact frame revision")
            if result.settings_revision != self.settings.config_revision:
                raise ValueError("PPP result must cite the exact settings revision")
        return self


class AutoPlotPlan(Batch30BPlan):
    frames: tuple[PlotFrameSnapshot, ...]
    settings: PlotSettingsSnapshot
    results: tuple[PlotArtifactResult, ...]


def plan_auto_plot(request: AutoPlotRequest) -> AutoPlotPlan:
    return AutoPlotPlan(
        **_base(
            request,
            "PPP",
            "xiAutoPlot",
            "current/frozen shortcuts, ZWCAD menu, current AutoPlot DCL/xiConfig_ppp, and official help identify current/multi-file automatic plotting and outputs",
            (
                "frame discovery, hidden-frame filtering, block attributes, ordering icon meanings, plot APIs, printer capabilities, naming, overwrite, PDF merge, and retry behavior are compiled or environment-dependent",
                "caller supplies versioned frame/settings snapshots and content-addressed exact artifacts; the planner neither prints nor reads/writes output files",
                "DCL/config choices establish fields but not legacy runtime equivalence",
            ),
            EvidenceLevel.DCL_EXACT_RESULT,
        ),
        frames=request.frames,
        settings=request.settings,
        results=request.exact_results,
    )


def register_headless_core_batch30b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 30B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    for name, function in (
        ("xicad_plan_ib", plan_insert_blocks),
        ("xicad_plan_msl", plan_multi_file_organize),
        ("xicad_plan_pb", plan_plot_box_create),
        ("xicad_plan_pbd", plan_delete_plot_boxes),
        ("xicad_plan_pbm", plan_plot_box_multi_make),
        ("xicad_plan_ppp", plan_auto_plot),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
