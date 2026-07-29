from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, DrawingSpace
from .headless_core_batch9 import (
    AllLayersOnRequest,
    DrawOrderByLayerRequest,
    DrawOrderDirection,
    EntityVisibilityRequest,
    EraseLayerRequest,
    LayerEntitySnapshot,
    LayerSnapshot,
    SelectedLayerRequest,
    plan_all_layers_on,
    plan_draw_order_by_layer,
    plan_entity_visibility,
    plan_erase_layer,
    plan_selected_layers_isolate,
    plan_selected_layers_off,
)


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _models(items: tuple[BaseModel, ...]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)


class LiveSelectedLayerPreviewRequest(_Request):
    selected_entity_handles: tuple[str, ...] = Field(min_length=1)
    current_layer_policy: str = Field(default="error", pattern=r"^(error|keep_on)$")
    xref_layer_policy: str = Field(default="skip", pattern=r"^(error|skip)$")


class LiveSelectedLayerExecuteRequest(LiveSelectedLayerPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveAllLayersOnPreviewRequest(_Request):
    thaw_frozen: bool = False
    include_xref_layers: bool = False


class LiveAllLayersOnExecuteRequest(LiveAllLayersOnPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveDolPreviewRequest(_Request):
    ordered_layers: tuple[str, ...] = Field(min_length=1)
    direction: DrawOrderDirection
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    unlisted_layer_policy: str = Field(default="preserve", pattern=r"^(preserve|error)$")


class LiveDolExecuteRequest(LiveDolPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveElyPreviewRequest(_Request):
    target_layers: tuple[str, ...] = Field(min_length=1)
    expected_entity_handles: tuple[str, ...] = Field(min_length=1)
    include_nested: bool = False
    erase_layer_records: bool = False


class LiveElyExecuteRequest(LiveElyPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveEooPreviewRequest(_Request):
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)


class LiveEooExecuteRequest(LiveEooPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveLayer9aResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_layers: tuple[str, ...] = ()
    changed_handles: tuple[str, ...] = ()
    erased_handles: tuple[str, ...] = ()
    erased_layers: tuple[str, ...] = ()
    postcondition_verified: bool


class ZWCADLiveLayer9aAdapter:
    def __init__(self, document_name: str) -> None:
        self.document_name = document_name
        self.app: Any | None = None
        self.doc: Any | None = None

    def connect(self) -> Any:
        if self.doc is not None:
            return self.doc
        import win32com.client

        self.app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
        matches = [doc for doc in self.app.Documents if str(doc.Name).casefold() == self.document_name.casefold()]
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one open document named {self.document_name!r}, found {len(matches)}")
        self.doc = matches[0]
        self.doc.Activate()
        return self.doc

    def layers(self) -> tuple[LayerSnapshot, ...]:
        doc = self.connect()
        current = str(doc.ActiveLayer.Name).casefold()
        result = []
        for layer in doc.Layers:
            name = str(layer.Name)
            result.append(
                LayerSnapshot(
                    name=name,
                    color_index=int(layer.Color),
                    linetype=str(layer.Linetype),
                    is_on=bool(layer.LayerOn),
                    is_frozen=bool(layer.Freeze),
                    is_locked=bool(layer.Lock),
                    is_xref="|" in name,
                    is_current=name.casefold() == current,
                )
            )
        result.sort(key=lambda item: item.name.casefold())
        return tuple(result)

    @staticmethod
    def _visible(entity: Any) -> bool:
        try:
            return bool(entity.Visible)
        except Exception as exc:
            raise RuntimeError(f"ZWCAD entity does not expose visibility: {entity.Handle}") from exc

    def inventory(self) -> tuple[LayerEntitySnapshot, ...]:
        doc = self.connect()
        result: dict[str, LayerEntitySnapshot] = {}
        for block in doc.Blocks:
            is_layout = bool(block.IsLayout)
            if is_layout:
                space = DrawingSpace.MODEL if str(block.Name).casefold() == "*model_space" else DrawingSpace.PAPER
                nested = False
                owner = None
                block_name = None
            else:
                space = DrawingSpace.MODEL
                nested = True
                owner = str(block.Handle)
                block_name = str(block.Name)
            for entity in block:
                handle = str(entity.Handle)
                layer = str(entity.Layer)
                result[handle.casefold()] = LayerEntitySnapshot(
                    handle=handle,
                    layer=layer,
                    color_index=int(entity.Color),
                    linetype=str(entity.Linetype),
                    visible=self._visible(entity),
                    space=space,
                    block_owner_handle=owner,
                    block_name=block_name,
                    nested=nested,
                    is_xref="|" in layer or (block_name is not None and "|" in block_name),
                )
        return tuple(sorted(result.values(), key=lambda item: item.handle.casefold()))

    def layer_objects(self) -> dict[str, Any]:
        return {str(layer.Name).casefold(): layer for layer in self.connect().Layers}

    def entity_objects(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for block in self.connect().Blocks:
            for entity in block:
                result[str(entity.Handle).casefold()] = entity
        return result

    def owner_blocks(self) -> dict[str, Any]:
        result = {}
        for block in self.connect().Blocks:
            if bool(block.IsLayout):
                for entity in block:
                    result[str(entity.Handle).casefold()] = block
        return result

    def sortents(self, owner: Any) -> Any:
        try:
            dictionary = owner.GetExtensionDictionary()
            try:
                return dictionary.GetObject("ACAD_SORTENTS")
            except Exception:
                return dictionary.AddObject("ACAD_SORTENTS", "AcDbSortentsTable")
        except Exception as exc:
            raise RuntimeError("ZWCAD ActiveX SortentsTable capability is unavailable") from exc

    @staticmethod
    def dispatch_array(entities: list[Any]) -> Any:
        import pythoncom
        import win32com.client

        return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, entities)


def _approval(execute: bool, fingerprint: str | None = None) -> Approval:
    return Approval(approved=execute, fingerprint=fingerprint)


def _state(adapter: ZWCADLiveLayer9aAdapter) -> tuple[tuple[LayerSnapshot, ...], tuple[LayerEntitySnapshot, ...]]:
    return adapter.layers(), adapter.inventory()


def _same(actual: tuple[BaseModel, ...], expected: tuple[BaseModel, ...], alias: str) -> None:
    if _models(actual) != _models(expected):
        raise ValueError(f"{alias} inventory no longer matches the approved snapshot")


def _payload(
    request: BaseModel, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...], plan: BaseModel
) -> dict[str, Any]:
    body = {
        **request.model_dump(mode="json"),
        "expected_layers": _models(layers),
        "expected_entities": _models(entities),
    }
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def _selected_core(
    request: LiveSelectedLayerPreviewRequest, execute: bool, fingerprint: str | None = None
) -> SelectedLayerRequest:
    return SelectedLayerRequest(
        document_id=request.document_name,
        selected_entity_handles=request.selected_entity_handles,
        current_layer_policy=request.current_layer_policy,
        xref_layer_policy=request.xref_layer_policy,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def _protect_layer_state(plan: Any) -> Any:
    changes = tuple(
        change
        for change in plan.changes
        if change.layer.casefold() not in {"0", "defpoints"} and "|" not in change.layer
    )
    return plan.model_copy(update={"changes": changes})


def preview_live_1(request: LiveSelectedLayerPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    plan = plan_selected_layers_off(_selected_core(request, False), layers, entities)
    plan = _protect_layer_state(plan)
    return _payload(request, layers, entities, plan)


def preview_live_2(request: LiveSelectedLayerPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    plan = plan_selected_layers_isolate(_selected_core(request, False), layers, entities)
    plan = _protect_layer_state(plan)
    return _payload(request, layers, entities, plan)


def _execute_layer_state(
    request: LiveSelectedLayerExecuteRequest, alias: str, planner: Callable[..., Any]
) -> LiveLayer9aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError(f"approval fingerprint does not match the exact {alias} request")
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    _same(layers, request.expected_layers, alias)
    _same(entities, request.expected_entities, alias)
    plan = planner(_selected_core(request, True, request.approval_fingerprint), layers, entities)
    plan = _protect_layer_state(plan)
    doc = adapter.connect()
    records = adapter.layer_objects()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            record = records[change.layer.casefold()]
            record.LayerOn = change.replacement_on
            record.Freeze = change.replacement_frozen
    finally:
        doc.EndUndoMark()
    after = {layer.name.casefold(): layer for layer in adapter.layers()}
    if not all(
        after[c.layer.casefold()].is_on == c.replacement_on
        and after[c.layer.casefold()].is_frozen == c.replacement_frozen
        for c in plan.changes
    ):
        raise RuntimeError(f"{alias} postcondition failed")
    return LiveLayer9aResult(
        document_name=str(doc.Name),
        command_alias=alias,
        changed_layers=tuple(c.layer for c in plan.changes),
        postcondition_verified=True,
    )


def register_live_layer_batch9a_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 9A layer operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 9A layer operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_1", preview_live_1, preview),
        ("xicad_execute_live_1", execute_live_1, execute),
        ("xicad_preview_live_2", preview_live_2, preview),
        ("xicad_execute_live_2", execute_live_2, execute),
        ("xicad_preview_live_3", preview_live_3, preview),
        ("xicad_execute_live_3", execute_live_3, execute),
        ("xicad_preview_live_dol", preview_live_dol, preview),
        ("xicad_execute_live_dol", execute_live_dol, execute),
        ("xicad_preview_live_ely", preview_live_ely, preview),
        ("xicad_execute_live_ely", execute_live_ely, execute),
        ("xicad_preview_live_eoo", preview_live_eoo, preview),
        ("xicad_execute_live_eoo", execute_live_eoo, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)


def execute_live_1(request: LiveSelectedLayerExecuteRequest) -> LiveLayer9aResult:
    return _execute_layer_state(request, "1", plan_selected_layers_off)


def execute_live_2(request: LiveSelectedLayerExecuteRequest) -> LiveLayer9aResult:
    return _execute_layer_state(request, "2", plan_selected_layers_isolate)


def _all_core(
    request: LiveAllLayersOnPreviewRequest, execute: bool, fingerprint: str | None = None
) -> AllLayersOnRequest:
    return AllLayersOnRequest(
        document_id=request.document_name,
        thaw_frozen=request.thaw_frozen,
        include_xref_layers=request.include_xref_layers,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_3(request: LiveAllLayersOnPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    plan = plan_all_layers_on(_all_core(request, False), layers)
    plan = _protect_layer_state(plan)
    return _payload(request, layers, entities, plan)


def execute_live_3(request: LiveAllLayersOnExecuteRequest) -> LiveLayer9aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact 3 request")
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    _same(layers, request.expected_layers, "3")
    _same(entities, request.expected_entities, "3")
    plan = plan_all_layers_on(_all_core(request, True, request.approval_fingerprint), layers)
    plan = _protect_layer_state(plan)
    doc = adapter.connect()
    records = adapter.layer_objects()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            record = records[change.layer.casefold()]
            record.LayerOn = change.replacement_on
            record.Freeze = change.replacement_frozen
    finally:
        doc.EndUndoMark()
    after = {layer.name.casefold(): layer for layer in adapter.layers()}
    if not all(
        after[c.layer.casefold()].is_on == c.replacement_on
        and after[c.layer.casefold()].is_frozen == c.replacement_frozen
        for c in plan.changes
    ):
        raise RuntimeError("3 postcondition failed")
    return LiveLayer9aResult(
        document_name=str(doc.Name),
        command_alias="3",
        changed_layers=tuple(c.layer for c in plan.changes),
        postcondition_verified=True,
    )


def _dol_core(request: LiveDolPreviewRequest, execute: bool, fingerprint: str | None = None) -> DrawOrderByLayerRequest:
    return DrawOrderByLayerRequest(
        document_id=request.document_name,
        ordered_layers=request.ordered_layers,
        direction=request.direction,
        spaces=request.spaces,
        include_nested=False,
        unlisted_layer_policy=request.unlisted_layer_policy,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_dol(request: LiveDolPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    plan = plan_draw_order_by_layer(_dol_core(request, False), entities)
    return _payload(request, layers, entities, plan)


def execute_live_dol(request: LiveDolExecuteRequest) -> LiveLayer9aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact DOL request")
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    _same(layers, request.expected_layers, "DOL")
    _same(entities, request.expected_entities, "DOL")
    plan = plan_draw_order_by_layer(_dol_core(request, True, request.approval_fingerprint), entities)
    objects = adapter.entity_objects()
    owners = adapter.owner_blocks()
    doc = adapter.connect()
    target = list(
        plan.ordered_handles
        if plan.direction is DrawOrderDirection.FIRST_LAYER_TO_BACK
        else reversed(plan.ordered_handles)
    )
    owner_groups: dict[int, tuple[Any, list[str]]] = {}
    for handle in target:
        owner = owners.get(handle.casefold())
        if owner is None:
            raise ValueError(f"DOL cannot reorder nested or missing entity: {handle}")
        owner_groups.setdefault(id(owner), (owner, []))[1].append(handle)
    doc.StartUndoMark()
    try:
        for owner, handles in owner_groups.values():
            table = adapter.sortents(owner)
            for handle in handles:
                table.MoveToTop(adapter.dispatch_array([objects[handle.casefold()]]))
    finally:
        doc.EndUndoMark()
    for owner, handles in owner_groups.values():
        order = [str(entity.Handle).casefold() for entity in adapter.sortents(owner).GetFullDrawOrder(True)]
        actual = [handle for handle in order if handle in {h.casefold() for h in handles}]
        if actual != [h.casefold() for h in handles]:
            raise RuntimeError("DOL postcondition failed")
    return LiveLayer9aResult(
        document_name=str(doc.Name),
        command_alias="DOL",
        changed_handles=plan.ordered_handles,
        postcondition_verified=True,
    )


def _ely_core(request: LiveElyPreviewRequest, execute: bool, fingerprint: str | None = None) -> EraseLayerRequest:
    return EraseLayerRequest(
        document_id=request.document_name,
        target_layers=request.target_layers,
        expected_entity_handles=request.expected_entity_handles,
        include_nested=request.include_nested,
        erase_layer_records=request.erase_layer_records,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_ely(request: LiveElyPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    plan = plan_erase_layer(_ely_core(request, False), layers, entities)
    return _payload(request, layers, entities, plan)


def execute_live_ely(request: LiveElyExecuteRequest) -> LiveLayer9aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact ELY request")
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    _same(layers, request.expected_layers, "ELY")
    _same(entities, request.expected_entities, "ELY")
    plan = plan_erase_layer(_ely_core(request, True, request.approval_fingerprint), layers, entities)
    objects = adapter.entity_objects()
    records = adapter.layer_objects()
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for handle in plan.erase_handles:
            objects[handle.casefold()].Delete()
        for name in plan.erase_layer_records:
            records[name.casefold()].Delete()
    finally:
        doc.EndUndoMark()
    after_entities = {item.handle.casefold() for item in adapter.inventory()}
    after_layers = {item.name.casefold() for item in adapter.layers()}
    if any(h.casefold() in after_entities for h in plan.erase_handles) or any(
        n.casefold() in after_layers for n in plan.erase_layer_records
    ):
        raise RuntimeError("ELY postcondition failed")
    return LiveLayer9aResult(
        document_name=str(doc.Name),
        command_alias="ELY",
        erased_handles=plan.erase_handles,
        erased_layers=plan.erase_layer_records,
        postcondition_verified=True,
    )


def _eoo_core(request: LiveEooPreviewRequest, execute: bool, fingerprint: str | None = None) -> EntityVisibilityRequest:
    return EntityVisibilityRequest(
        document_id=request.document_name,
        spaces=request.spaces,
        include_nested=False,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_eoo(request: LiveEooPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    plan = plan_entity_visibility(_eoo_core(request, False), entities, alias="EOO")
    return _payload(request, layers, entities, plan)


def execute_live_eoo(request: LiveEooExecuteRequest) -> LiveLayer9aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact EOO request")
    adapter = ZWCADLiveLayer9aAdapter(request.document_name)
    layers, entities = _state(adapter)
    _same(layers, request.expected_layers, "EOO")
    _same(entities, request.expected_entities, "EOO")
    plan = plan_entity_visibility(_eoo_core(request, True, request.approval_fingerprint), entities, alias="EOO")
    objects = adapter.entity_objects()
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            objects[change.handle.casefold()].Visible = change.replacement_visible
    finally:
        doc.EndUndoMark()
    after = {item.handle.casefold(): item for item in adapter.inventory()}
    if not all(after[c.handle.casefold()].visible == c.replacement_visible for c in plan.changes):
        raise RuntimeError("EOO postcondition failed")
    return LiveLayer9aResult(
        document_name=str(doc.Name),
        command_alias="EOO",
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )
