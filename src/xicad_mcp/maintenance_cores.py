from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DrawingSpace(StrEnum):
    MODEL = "model"
    PAPER = "paper"


class CadPlatform(StrEnum):
    ZWCAD = "zwcad"
    AUTOCAD = "autocad"
    BRICSCAD = "bricscad"
    GSTARCAD = "gstarcad"


class EntityRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    dxf_type: str = Field(min_length=1)
    space: DrawingSpace


class LayerFilterRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    system: bool = False


class Approval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    approved: bool = False
    fingerprint: str | None = None

    @model_validator(mode="after")
    def validate_approval(self) -> Approval:
        if self.approved and not self.fingerprint:
            raise ValueError("approved destructive actions require an approval fingerprint")
        return self


class AllPointDeleteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> AllPointDeleteRequest:
        if not self.spaces:
            raise ValueError("at least one drawing space is required")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("APD execution requires explicit approval")
        return self


class AllPointDeletePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "APD"
    document_id: str
    dxf_types: tuple[str, ...] = ("POINT",)
    spaces: tuple[DrawingSpace, ...]
    destructive: bool = True
    dry_run: bool
    approval_required: bool = True
    production_usable: bool = False


class AllPointDeleteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: AllPointDeletePlan
    matched_handles: tuple[str, ...]
    deleted_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    warnings: tuple[str, ...] = ()


class LayerFilterDeleteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    aliases: tuple[str, ...] = ("LFD", "LPD")
    delete_all_user_filters: bool = True
    include_names: tuple[str, ...] = ()
    preserve_names: tuple[str, ...] = ()
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LayerFilterDeleteRequest:
        if not self.delete_all_user_filters and not self.include_names:
            raise ValueError("specific mode requires include_names")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("layer-filter deletion requires explicit approval")
        if set(name.casefold() for name in self.include_names) & set(name.casefold() for name in self.preserve_names):
            raise ValueError("a filter cannot be both included and preserved")
        return self


class LayerFilterDeletePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_aliases: tuple[str, ...] = ("LFD", "LPD")
    shared_core_key: str = "layer_filters_delete"
    document_id: str
    selected_names: tuple[str, ...]
    preserved_names: tuple[str, ...]
    destructive: bool = True
    dry_run: bool
    approval_required: bool = True
    production_usable: bool = False


class LayerFilterDeleteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: LayerFilterDeletePlan
    deleted_names: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    warnings: tuple[str, ...] = ()


class PlatformSupport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    alias: str
    platform: CadPlatform
    supported: bool
    implementation_state: str
    reason: str
    production_usable: bool = False


class MaintenanceAdapter(Protocol):
    def active_document_id(self) -> str: ...
    def begin_undo_mark(self) -> None: ...
    def end_undo_mark(self) -> None: ...
    def find_entities(self, dxf_types: tuple[str, ...], spaces: tuple[DrawingSpace, ...]) -> Sequence[EntityRef]: ...
    def erase_entities(self, handles: Sequence[str]) -> None: ...
    def list_layer_filters(self) -> Sequence[LayerFilterRef]: ...
    def delete_layer_filters(self, names: Sequence[str]) -> None: ...


def _require_document(adapter: MaintenanceAdapter, document_id: str) -> None:
    active = adapter.active_document_id()
    if active != document_id:
        raise ValueError(f"active document mismatch: expected {document_id}, got {active}")


def plan_all_point_delete(request: AllPointDeleteRequest) -> AllPointDeletePlan:
    return AllPointDeletePlan(
        document_id=request.document_id,
        spaces=request.spaces,
        dry_run=request.dry_run,
    )


def execute_all_point_delete(request: AllPointDeleteRequest, adapter: MaintenanceAdapter) -> AllPointDeleteResult:
    _require_document(adapter, request.document_id)
    plan = plan_all_point_delete(request)
    entities = tuple(adapter.find_entities(plan.dxf_types, plan.spaces))
    invalid = [entity.handle for entity in entities if entity.dxf_type.upper() != "POINT"]
    if invalid:
        raise ValueError(f"adapter returned non-POINT entities: {invalid}")
    handles = tuple(entity.handle for entity in entities)
    if request.dry_run or not handles:
        return AllPointDeleteResult(
            plan=plan,
            matched_handles=handles,
            deleted_handles=(),
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    try:
        adapter.begin_undo_mark()
        opened = True
        adapter.erase_entities(handles)
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return AllPointDeleteResult(
        plan=plan,
        matched_handles=handles,
        deleted_handles=handles,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


def plan_layer_filter_delete(
    request: LayerFilterDeleteRequest,
    filters: Sequence[LayerFilterRef],
) -> LayerFilterDeletePlan:
    preserve = {name.casefold() for name in request.preserve_names}
    include = {name.casefold() for name in request.include_names}
    selected: list[str] = []
    preserved: list[str] = []
    for item in filters:
        key = item.name.casefold()
        should_delete = (request.delete_all_user_filters and not item.system) or (
            not request.delete_all_user_filters and key in include
        )
        if item.system or key in preserve:
            preserved.append(item.name)
        elif should_delete:
            selected.append(item.name)
    return LayerFilterDeletePlan(
        document_id=request.document_id,
        selected_names=tuple(sorted(set(selected), key=str.casefold)),
        preserved_names=tuple(sorted(set(preserved), key=str.casefold)),
        dry_run=request.dry_run,
    )


def execute_layer_filter_delete(
    request: LayerFilterDeleteRequest, adapter: MaintenanceAdapter
) -> LayerFilterDeleteResult:
    _require_document(adapter, request.document_id)
    plan = plan_layer_filter_delete(request, tuple(adapter.list_layer_filters()))
    if request.dry_run or not plan.selected_names:
        return LayerFilterDeleteResult(
            plan=plan,
            deleted_names=(),
            undo_mark_opened=False,
            undo_mark_closed=False,
        )
    opened = False
    closed = False
    try:
        adapter.begin_undo_mark()
        opened = True
        adapter.delete_layer_filters(plan.selected_names)
    finally:
        if opened:
            adapter.end_undo_mark()
            closed = True
    return LayerFilterDeleteResult(
        plan=plan,
        deleted_names=plan.selected_names,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
    )


def legacy_platform_support(alias: str, platform: CadPlatform) -> PlatformSupport:
    key = alias.upper()
    if key == "SLD":
        if platform is CadPlatform.ZWCAD:
            return PlatformSupport(
                alias=key,
                platform=platform,
                supported=False,
                implementation_state="platform_excluded",
                reason="The frozen xiCAD shortcut explicitly marks scale-list deletion unsupported on ZWCAD.",
            )
        return PlatformSupport(
            alias=key,
            platform=platform,
            supported=False,
            implementation_state="adapter_missing",
            reason="The command is not enabled until a reviewed platform-specific adapter exists.",
        )
    raise KeyError(alias)


def register_maintenance_core_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Maintenance Core Plans",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="xicad_plan_all_point_delete",
        description="Build a deterministic APD plan. The tool does not connect to CAD or delete entities.",
        annotations=read_only,
    )
    def mcp_plan_all_point_delete(request: AllPointDeleteRequest) -> AllPointDeletePlan:
        return plan_all_point_delete(request)

    @mcp.tool(
        name="xicad_plan_layer_filter_delete",
        description="Build the shared LFD/LPD deletion plan from an explicit list of known layer filters. The tool does not modify CAD.",
        annotations=read_only,
    )
    def mcp_plan_layer_filter_delete(
        request: LayerFilterDeleteRequest,
        filters: list[LayerFilterRef],
    ) -> LayerFilterDeletePlan:
        return plan_layer_filter_delete(request, filters)

    @mcp.tool(
        name="xicad_legacy_platform_support",
        description="Return the explicit platform policy for a platform-sensitive legacy command such as SLD.",
        annotations=read_only,
    )
    def mcp_legacy_platform_support(alias: str, platform: CadPlatform) -> PlatformSupport:
        try:
            return legacy_platform_support(alias, platform)
        except KeyError as exc:
            raise ValueError(f"No platform policy exists for: {alias}") from exc
