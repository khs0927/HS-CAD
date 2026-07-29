"""Structured, dialog-free planners for the first twelve frozen xiCAD aliases."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch14 import GeometrySnapshot


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval fingerprint")


def _unique(values: Sequence[str], name: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{name} must be unique")


class Batch15Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    semantic_evidence: str
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class ContentKind(StrEnum):
    TEXT = "text"
    CIRCLE_DIAMETER = "circle_diameter"
    POLYLINE_WIDTH = "polyline_width"
    BLOCK_NAME = "block_name"


class ContentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    kind: ContentKind
    value: str | float
    is_xref: bool = False
    locked_layer: bool = False


class CopyContentsRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handle: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    expected_kind: ContentKind
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> CopyContentsRequest:
        _unique(self.target_handles, "CT target_handles")
        if self.source_handle.casefold() in {handle.casefold() for handle in self.target_handles}:
            raise ValueError("CT source cannot also be a target")
        _approval(self.dry_run, self.approval, "CT")
        return self


class CopyContentsPlan(Batch15Plan):
    command_alias: str = "CT"
    legacy_symbol: str = "xiCopyconTents"
    semantic_evidence: str = "xiShortkey: 내용 복사 (문자,원지름,폴리선두께,블럭)"
    source_value: str | float
    changes: dict[str, str | float]


def plan_copy_contents(request: CopyContentsRequest, snapshots: Sequence[ContentSnapshot]) -> CopyContentsPlan:
    by_handle = {snapshot.handle.casefold(): snapshot for snapshot in snapshots}
    source = by_handle.get(request.source_handle.casefold())
    if source is None or source.kind is not request.expected_kind:
        raise ValueError("CT source is missing or has a different content kind")
    changes: dict[str, str | float] = {}
    for handle in request.target_handles:
        target = by_handle.get(handle.casefold())
        if target is None or target.kind is not request.expected_kind:
            raise ValueError(f"CT target is missing or incompatible: {handle}")
        if target.is_xref or target.locked_layer:
            raise ValueError(f"CT target is not editable: {handle}")
        changes[target.handle] = source.value
    return CopyContentsPlan(
        document_id=request.document_id,
        source_value=source.value,
        changes=changes,
        dry_run=request.dry_run,
    )


class DateStampRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    creation_date: date
    insertion_point: Point3D
    format_template: str = Field(min_length=1)
    prefix: str = ""
    layer: str = Field(min_length=1)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DateStampRequest:
        try:
            self.creation_date.strftime(self.format_template)
        except (TypeError, ValueError) as exc:
            raise ValueError("DTS format_template is invalid") from exc
        _approval(self.dry_run, self.approval, "DTS")
        return self


class TextCreateSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    insertion_point: Point3D
    layer: str
    style: str
    height: float


class DateStampPlan(Batch15Plan):
    command_alias: str = "DTS"
    legacy_symbol: str = "xiDATESTAMP"
    semantic_evidence: str = "xiShortkey: 도면 생성 날짜 기록하기; date supplied explicitly"
    create: TextCreateSpec


def plan_date_stamp(request: DateStampRequest) -> DateStampPlan:
    return DateStampPlan(
        document_id=request.document_id,
        create=TextCreateSpec(
            text=request.prefix + request.creation_date.strftime(request.format_template),
            insertion_point=request.insertion_point,
            layer=request.layer,
            style=request.text_style,
            height=request.text_height,
        ),
        dry_run=request.dry_run,
    )


class FlattenRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    target_z: float = 0
    preserve_nonplanar_curves: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> FlattenRequest:
        _unique(self.target_handles, "FLT target_handles")
        if self.preserve_nonplanar_curves:
            raise ValueError("FLT non-planar curve preservation is blocked without curve parameters")
        _approval(self.dry_run, self.approval, "FLT")
        return self


class FlattenPlan(Batch15Plan):
    command_alias: str = "FLT"
    legacy_symbol: str = "xiFlatten"
    semantic_evidence: str = "xiShortkey: Z값 0으로 변경"
    target_vertices: dict[str, tuple[Point3D, ...]]


def plan_flatten(request: FlattenRequest, snapshots: Sequence[GeometrySnapshot]) -> FlattenPlan:
    by_handle = {snapshot.handle.casefold(): snapshot for snapshot in snapshots}
    changes: dict[str, tuple[Point3D, ...]] = {}
    for handle in request.target_handles:
        item = by_handle.get(handle.casefold())
        if item is None or item.is_xref or item.locked_layer:
            raise ValueError(f"FLT target unavailable: {handle}")
        changes[item.handle] = tuple(Point3D(x=p.x, y=p.y, z=request.target_z) for p in item.vertices)
    return FlattenPlan(document_id=request.document_id, target_vertices=changes, dry_run=request.dry_run)


class GroupOperation(StrEnum):
    ADD_MEMBERS = "add_members"
    REMOVE_MEMBERS = "remove_members"
    RENAME = "rename"


class GroupSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    member_handles: tuple[str, ...]


class GroupEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    group_name: str = Field(min_length=1)
    operation: GroupOperation
    member_handles: tuple[str, ...] = ()
    new_name: str | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> GroupEditRequest:
        _unique(self.member_handles, "GEE member_handles")
        if self.operation is GroupOperation.RENAME and not self.new_name:
            raise ValueError("GEE rename requires new_name")
        if self.operation is not GroupOperation.RENAME and not self.member_handles:
            raise ValueError("GEE member operation requires member_handles")
        _approval(self.dry_run, self.approval, "GEE")
        return self


class GroupEditPlan(Batch15Plan):
    command_alias: str = "GEE"
    legacy_symbol: str = "xiGroupEdit"
    semantic_evidence: str = "xiShortkey: 그룹 수정; operation supplied explicitly"
    resulting_name: str
    resulting_members: tuple[str, ...]


def plan_group_edit(request: GroupEditRequest, groups: Sequence[GroupSnapshot]) -> GroupEditPlan:
    group = next((item for item in groups if item.name.casefold() == request.group_name.casefold()), None)
    if group is None:
        raise ValueError("GEE group not found")
    members = list(group.member_handles)
    if request.operation is GroupOperation.ADD_MEMBERS:
        existing = {item.casefold() for item in members}
        members.extend(handle for handle in request.member_handles if handle.casefold() not in existing)
    elif request.operation is GroupOperation.REMOVE_MEMBERS:
        removed = {handle.casefold() for handle in request.member_handles}
        members = [handle for handle in members if handle.casefold() not in removed]
    return GroupEditPlan(
        document_id=request.document_id,
        resulting_name=request.new_name if request.operation is GroupOperation.RENAME else group.name,
        resulting_members=tuple(members),
        dry_run=request.dry_run,
    )


class DefinitionKind(StrEnum):
    LAYER = "layer"
    LINETYPE = "linetype"
    TEXT_STYLE = "text_style"
    DIM_STYLE = "dim_style"
    BLOCK = "block"


class ConflictPolicy(StrEnum):
    KEEP_TARGET = "keep_target"
    OVERWRITE = "overwrite"
    RENAME_IMPORTED = "rename_imported"


class StealItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: DefinitionKind
    name: str = Field(min_length=1)
    renamed_to: str | None = None


class StealRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_document_path: str = Field(min_length=1)
    items: tuple[StealItem, ...] = Field(min_length=1)
    conflict_policy: ConflictPolicy
    source_digest: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> StealRequest:
        keys = [f"{item.kind}:{item.name}" for item in self.items]
        _unique(keys, "STL items")
        if self.conflict_policy is ConflictPolicy.RENAME_IMPORTED and any(not item.renamed_to for item in self.items):
            raise ValueError("STL rename_imported requires renamed_to for every item")
        _approval(self.dry_run, self.approval, "STL")
        return self


class StealPlan(Batch15Plan):
    command_alias: str = "STL"
    legacy_symbol: str = "xiSteal"
    semantic_evidence: str = "xiShortkey + xiSteal DCL two-list definition importer"
    source_document_path: str
    source_digest: str
    imports: tuple[StealItem, ...]
    conflict_policy: ConflictPolicy


def plan_steal(request: StealRequest) -> StealPlan:
    return StealPlan(
        document_id=request.document_id,
        source_document_path=request.source_document_path,
        source_digest=request.source_digest,
        imports=request.items,
        conflict_policy=request.conflict_policy,
        dry_run=request.dry_run,
    )


class ShortcutSection(StrEnum):
    COMM = "comm"
    OPEN = "open"
    DRAW = "draw"
    HATCH = "hatch"
    CUT = "cut"
    MULTI = "multi"
    LAYER = "layer"
    DBOX = "dbox"
    AREA = "area"
    TEXT_EDIT = "text_edit"
    TEXT_CREATE = "text_create"
    DIM = "dim"
    SHAPE = "shape"
    BLOCK = "block"
    PAPER = "paper"
    PLOT = "plot"
    NONE = "none"


class ShortcutOperation(StrEnum):
    UPSERT = "upsert"
    REMOVE = "remove"
    RESET = "reset"


class ShortcutChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    operation: ShortcutOperation
    alias: str = Field(min_length=1)
    command: str | None = None
    description: str | None = None
    section: ShortcutSection

    @model_validator(mode="after")
    def validate_change(self) -> ShortcutChange:
        if self.operation is ShortcutOperation.UPSERT and (not self.command or not self.description):
            raise ValueError("COM upsert requires command and description")
        return self


class CommandEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    key_file_path: str = Field(min_length=1)
    expected_file_digest: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    changes: tuple[ShortcutChange, ...] = Field(min_length=1)
    apply_to_pgp: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> CommandEditRequest:
        _unique([change.alias for change in self.changes], "COM aliases")
        if self.apply_to_pgp:
            raise ValueError("COM PGP mutation is blocked; generate and review a key-file patch first")
        _approval(self.dry_run, self.approval, "COM")
        return self


class CommandEditPlan(Batch15Plan):
    command_alias: str = "COM"
    legacy_symbol: str = "xiCommandEdit"
    semantic_evidence: str = "xiCommandEdit DCL keys/sections/edit controls; PGP write blocked"
    key_file_path: str
    expected_file_digest: str
    changes: tuple[ShortcutChange, ...]
    external_write_blocked: bool = True


def plan_command_edit(request: CommandEditRequest) -> CommandEditPlan:
    return CommandEditPlan(
        document_id=request.document_id,
        key_file_path=request.key_file_path,
        expected_file_digest=request.expected_file_digest,
        changes=request.changes,
        dry_run=request.dry_run,
    )


class ExplorerRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    drawing_path: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_approval(self) -> ExplorerRequest:
        _approval(self.dry_run, self.approval, "EXP")
        return self


class ExplorerPlan(Batch15Plan):
    command_alias: str = "EXP"
    legacy_symbol: str = "xiEXDWG"
    semantic_evidence: str = "xiShortkey: 현재 작업폴더로 탐색기 실행하기"
    folder_path: str
    external_process_blocked: bool = True


def plan_explorer(request: ExplorerRequest) -> ExplorerPlan:
    path = PureWindowsPath(request.drawing_path)
    if not path.is_absolute() or not path.suffix:
        raise ValueError("EXP drawing_path must be an absolute file path")
    return ExplorerPlan(document_id=request.document_id, folder_path=str(path.parent), dry_run=request.dry_run)


class OpenDrawingRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    current_path: str = Field(min_length=1)
    candidate_paths: tuple[str, ...] = Field(min_length=1)
    selected_path: str | None = None
    read_only: bool
    operation: str = Field(pattern=r"^(list_select|next)$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> OpenDrawingRequest:
        _unique(self.candidate_paths, "drawing candidates")
        if self.operation == "list_select" and not self.selected_path:
            raise ValueError("OL requires selected_path")
        _approval(self.dry_run, self.approval, "OL" if self.operation == "list_select" else "ON")
        return self


class OpenDrawingPlan(Batch15Plan):
    target_path: str
    read_only: bool
    external_open_blocked: bool = True


def plan_open_drawing(request: OpenDrawingRequest) -> OpenDrawingPlan:
    current = PureWindowsPath(request.current_path)
    candidates = sorted(
        (PureWindowsPath(path) for path in request.candidate_paths), key=lambda path: path.name.casefold()
    )
    if any(path.parent != current.parent for path in candidates):
        raise ValueError("OL/ON candidates must be in the current drawing folder")
    if request.operation == "list_select":
        selected = PureWindowsPath(request.selected_path or "")
        if selected not in candidates:
            raise ValueError("OL selected_path is not in candidate_paths")
        alias, symbol, evidence = "OL", "xiOpenList", "xiOpenList DCL folder/list/read-only selection"
    else:
        try:
            index = next(i for i, path in enumerate(candidates) if path == current)
        except StopIteration as exc:
            raise ValueError("ON current drawing is absent from candidates") from exc
        if index + 1 >= len(candidates):
            raise ValueError("ON has no next drawing")
        selected = candidates[index + 1]
        alias, symbol, evidence = "ON", "xiOpenNext", "xiShortkey: 현재 도면의 다음 순서 파일 열기; casefold sort"
    return OpenDrawingPlan(
        command_alias=alias,
        legacy_symbol=symbol,
        semantic_evidence=evidence,
        document_id=request.document_id,
        target_path=str(selected),
        read_only=request.read_only,
        dry_run=request.dry_run,
    )


class ClosePolicy(StrEnum):
    SAVE_ALL = "save_all"
    DISCARD_ALL = "discard_all"
    SAVE_MODIFIED = "save_modified"


class DocumentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    path: str | None = None
    modified: bool
    read_only: bool = False


class QuickQuitRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_document_ids: tuple[str, ...] = Field(min_length=1)
    policy: ClosePolicy
    confirm_discard_modified: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> QuickQuitRequest:
        _unique(self.target_document_ids, "QQ document ids")
        if self.policy is ClosePolicy.DISCARD_ALL and not self.confirm_discard_modified:
            raise ValueError("QQ discard_all requires confirm_discard_modified=true")
        _approval(self.dry_run, self.approval, "QQ")
        return self


class CloseAction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str
    save_before_close: bool


class QuickQuitPlan(Batch15Plan):
    command_alias: str = "QQ"
    legacy_symbol: str = "xiQuickQuit"
    semantic_evidence: str = "xiShortkey: 도면 일괄 닫기 (저장 또는 비저장); explicit close policy"
    actions: tuple[CloseAction, ...]
    external_close_blocked: bool = True


def plan_quick_quit(request: QuickQuitRequest, documents: Sequence[DocumentSnapshot]) -> QuickQuitPlan:
    by_id = {document.document_id.casefold(): document for document in documents}
    actions = []
    for document_id in request.target_document_ids:
        document = by_id.get(document_id.casefold())
        if document is None:
            raise ValueError(f"QQ document not found: {document_id}")
        save = request.policy is ClosePolicy.SAVE_ALL or (
            request.policy is ClosePolicy.SAVE_MODIFIED and document.modified
        )
        if save and (document.read_only or not document.path):
            raise ValueError(f"QQ cannot save read-only or unnamed document: {document_id}")
        actions.append(CloseAction(document_id=document.document_id, save_before_close=save))
    return QuickQuitPlan(document_id=request.document_id, actions=tuple(actions), dry_run=request.dry_run)


class FrameSize(StrEnum):
    NONE = "none"
    A0 = "a0"
    A1 = "a1"
    A2 = "a2"
    A3 = "a3"
    A4 = "a4"
    USER1 = "user1"
    USER2 = "user2"


class LayerCreateSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    color: int = Field(ge=1, le=255)
    linetype: str = Field(min_length=1)


class StartRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    drawing_scale: float = Field(gt=0)
    apply_ltscale: bool
    apply_dimscale: bool
    reference_file: str | None = None
    create_layers: tuple[LayerCreateSpec, ...] = ()
    frame_size: FrameSize
    frame_file: str | None = None
    insertion_point: Point3D | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> StartRequest:
        _unique([layer.name for layer in self.create_layers], "STT layers")
        if self.frame_size is not FrameSize.NONE and (not self.frame_file or self.insertion_point is None):
            raise ValueError("STT selected frame requires frame_file and insertion_point")
        _approval(self.dry_run, self.approval, "STT")
        return self


class StartPlan(Batch15Plan):
    command_alias: str = "STT"
    legacy_symbol: str = "xiStart"
    semantic_evidence: str = "xiStart DCL: scale/LTSCALE/DIMSCALE/reference/layers/A0-A4/User frames"
    system_variables: dict[str, float]
    reference_file: str | None
    create_layers: tuple[LayerCreateSpec, ...]
    frame_size: FrameSize
    frame_file: str | None
    insertion_point: Point3D | None


def plan_start(request: StartRequest) -> StartPlan:
    variables = {}
    if request.apply_ltscale:
        variables["LTSCALE"] = request.drawing_scale
    if request.apply_dimscale:
        variables["DIMSCALE"] = request.drawing_scale
    return StartPlan(
        document_id=request.document_id,
        system_variables=variables,
        reference_file=request.reference_file,
        create_layers=request.create_layers,
        frame_size=request.frame_size,
        frame_file=request.frame_file,
        insertion_point=request.insertion_point,
        dry_run=request.dry_run,
    )


class SteelKind(StrEnum):
    H_BEAM = "h_beam"
    ANGLE = "angle"
    CHANNEL = "channel"
    C_CHANNEL = "c_channel"
    RECTANGULAR_TUBE = "rectangular_tube"
    CIRCULAR_PIPE = "circular_pipe"


class SteelView(StrEnum):
    SECTION = "section"
    SIDE = "side"
    PLAN = "plan"


class SteelRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    kind: SteelKind
    view: SteelView
    insertion_point: Point3D
    depth: float = Field(gt=0)
    width: float = Field(gt=0)
    web_thickness: float = Field(gt=0)
    flange_thickness: float = Field(gt=0)
    length: float | None = Field(default=None, gt=0)
    section_layer: str = Field(min_length=1)
    elevation_layer: str = Field(min_length=1)
    hidden_layer: str = Field(min_length=1)
    square_corners: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SteelRequest:
        if self.web_thickness >= self.width or 2 * self.flange_thickness >= self.depth:
            raise ValueError("BE thicknesses must fit inside profile dimensions")
        if self.view is not SteelView.SECTION and self.length is None:
            raise ValueError("BE side/plan view requires length")
        if not self.square_corners and self.kind in {SteelKind.C_CHANNEL, SteelKind.RECTANGULAR_TUBE}:
            raise ValueError("BE rounded-corner profiles require radius semantics not present in the DCL")
        _approval(self.dry_run, self.approval, "BE")
        return self


class SteelPlan(Batch15Plan):
    command_alias: str = "BE"
    legacy_symbol: str = "xiBE"
    semantic_evidence: str = "xiBeam DCL: six profile kinds, section/side/plan, three layers, square-corner toggle"
    kind: SteelKind
    view: SteelView
    outline: tuple[Point3D, ...]
    layer: str
    hidden_layer: str


def plan_steel(request: SteelRequest) -> SteelPlan:
    x, y, z = request.insertion_point.x, request.insertion_point.y, request.insertion_point.z
    if request.view is SteelView.SECTION:
        outline = (
            Point3D(x=x - request.width / 2, y=y - request.depth / 2, z=z),
            Point3D(x=x + request.width / 2, y=y - request.depth / 2, z=z),
            Point3D(x=x + request.width / 2, y=y + request.depth / 2, z=z),
            Point3D(x=x - request.width / 2, y=y + request.depth / 2, z=z),
        )
        layer = request.section_layer
    else:
        transverse = request.depth if request.view is SteelView.SIDE else request.width
        outline = (
            Point3D(x=x, y=y - transverse / 2, z=z),
            Point3D(x=x + (request.length or 0), y=y - transverse / 2, z=z),
            Point3D(x=x + (request.length or 0), y=y + transverse / 2, z=z),
            Point3D(x=x, y=y + transverse / 2, z=z),
        )
        layer = request.elevation_layer
    return SteelPlan(
        document_id=request.document_id,
        kind=request.kind,
        view=request.view,
        outline=outline,
        layer=layer,
        hidden_layer=request.hidden_layer,
        dry_run=request.dry_run,
    )


def register_headless_core_batch15_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 15 Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    def register(name: str):
        return lambda function: mcp.tool(name=name, annotations=annotations)(function)

    @register("xicad_plan_ct")
    def ct_tool(request: CopyContentsRequest, snapshots: tuple[ContentSnapshot, ...]) -> CopyContentsPlan:
        return plan_copy_contents(request, snapshots)

    @register("xicad_plan_dts")
    def dts_tool(request: DateStampRequest) -> DateStampPlan:
        return plan_date_stamp(request)

    @register("xicad_plan_flt")
    def flt_tool(request: FlattenRequest, snapshots: tuple[GeometrySnapshot, ...]) -> FlattenPlan:
        return plan_flatten(request, snapshots)

    @register("xicad_plan_gee")
    def gee_tool(request: GroupEditRequest, snapshots: tuple[GroupSnapshot, ...]) -> GroupEditPlan:
        return plan_group_edit(request, snapshots)

    @register("xicad_plan_stl")
    def stl_tool(request: StealRequest) -> StealPlan:
        return plan_steal(request)

    @register("xicad_plan_com")
    def com_tool(request: CommandEditRequest) -> CommandEditPlan:
        return plan_command_edit(request)

    @register("xicad_plan_exp")
    def exp_tool(request: ExplorerRequest) -> ExplorerPlan:
        return plan_explorer(request)

    @register("xicad_plan_ol")
    def ol_tool(request: OpenDrawingRequest) -> OpenDrawingPlan:
        if request.operation != "list_select":
            raise ValueError("OL requires operation=list_select")
        return plan_open_drawing(request)

    @register("xicad_plan_on")
    def on_tool(request: OpenDrawingRequest) -> OpenDrawingPlan:
        if request.operation != "next":
            raise ValueError("ON requires operation=next")
        return plan_open_drawing(request)

    @register("xicad_plan_qq")
    def qq_tool(request: QuickQuitRequest, documents: tuple[DocumentSnapshot, ...]) -> QuickQuitPlan:
        return plan_quick_quit(request, documents)

    @register("xicad_plan_stt")
    def stt_tool(request: StartRequest) -> StartPlan:
        return plan_start(request)

    @register("xicad_plan_be")
    def be_tool(request: SteelRequest) -> SteelPlan:
        return plan_steel(request)
