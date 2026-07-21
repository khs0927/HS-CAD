from __future__ import annotations

import hashlib
import json
from math import radians
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval
from .headless_core_batch5 import TextEntityKind, TextEntitySnapshot
from .headless_core_batch8 import (
    AttributeBlockEditRequest,
    AttributeBlockSnapshot,
    AttributeConversionMode,
    AttributeEditSpec,
    AttributeSnapshot,
    AttributeToTextRequest,
    ComprehensiveTextEditRequest,
    ComprehensiveTextPatch,
    ContextReplacementPolicy,
    ContextSelectionPrecedence,
    ContextTextEditRequest,
    FrameFitMode,
    MTextFrameFitRequest,
    MTextFrameSnapshot,
    SourceDisposition,
    TextCopyDestination,
    TextCopyPlacement,
    TextCopyRequest,
    plan_attribute_block_edit,
    plan_attribute_to_text,
    plan_comprehensive_text_edit,
    plan_context_text_edit,
    plan_mtext_frame_fit,
    plan_text_copy,
)
from .live_text_batch7a import ZWCADLiveText7aAdapter


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _models(items: tuple[BaseModel, ...]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)


class LiveA2mPreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: AttributeConversionMode
    include_tag: bool
    tag_separator: str = ": "
    block_separator: str = "\\P"
    source_disposition: SourceDisposition


class LiveA2mExecuteRequest(LiveA2mPreviewRequest):
    expected_attributes: tuple[AttributeSnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveAbePreviewRequest(_Request):
    target_block_handles: tuple[str, ...] = Field(min_length=1)
    edits: tuple[AttributeEditSpec, ...] = Field(min_length=1)
    missing_tag_policy: str = Field(pattern=r"^(error|skip)$")


class LiveAbeExecuteRequest(LiveAbePreviewRequest):
    expected_blocks: tuple[AttributeBlockSnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveCtxPreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    old_text: str = Field(min_length=1)
    new_text: str
    selection_precedence: ContextSelectionPrecedence
    whole_string_match: bool
    replacement_policy: ContextReplacementPolicy
    case_sensitive: bool = True
    zoom_text_height_factor: float = Field(gt=0)


class LiveCtxExecuteRequest(LiveCtxPreviewRequest):
    expected_entities: tuple[TextEntitySnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveTcPreviewRequest(_Request):
    placements: tuple[TextCopyPlacement, ...] = Field(min_length=1)


class LiveTableCellSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    table_handle: str
    row: int
    column: int
    text: str


class LiveTcExecuteRequest(LiveTcPreviewRequest):
    expected_entities: tuple[TextEntitySnapshot, ...] = Field(min_length=1)
    expected_cells: tuple[LiveTableCellSnapshot, ...] = ()
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveTePreviewRequest(_Request):
    patches: tuple[ComprehensiveTextPatch, ...] = Field(min_length=1)


class LiveTeExecuteRequest(LiveTePreviewRequest):
    expected_entities: tuple[TextEntitySnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveFrameMeasurement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    handle: str = Field(min_length=1)
    measured_content_width: float = Field(gt=0)


class LiveTffPreviewRequest(_Request):
    measurements: tuple[LiveFrameMeasurement, ...] = Field(min_length=1)
    mode: FrameFitMode
    horizontal_padding_height_factor: float = Field(default=0, ge=0)


class LiveTffExecuteRequest(LiveTffPreviewRequest):
    expected_frames: tuple[MTextFrameSnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveText8aResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...] = ()
    created_handles: tuple[str, ...] = ()
    erased_handles: tuple[str, ...] = ()
    postcondition_verified: bool


class ZWCADLiveText8aAdapter(ZWCADLiveText7aAdapter):
    def _block_references(self) -> dict[str, tuple[Any, Any, bool]]:
        result: dict[str, tuple[Any, Any, bool]] = {}
        for _space, owner in self._spaces():
            for entity in owner:
                if "blockreference" in str(entity.ObjectName).casefold():
                    result[str(entity.Handle).casefold()] = (entity, owner, False)
        return result

    def attributes(self, handles: tuple[str, ...]) -> tuple[AttributeSnapshot, ...]:
        wanted = {handle.casefold() for handle in handles}
        found: dict[str, AttributeSnapshot] = {}
        for _block_handle, (block, _owner, _nested) in self._block_references().items():
            try:
                attributes = tuple(block.GetAttributes()) if bool(block.HasAttributes) else ()
            except Exception as exc:
                raise RuntimeError(f"cannot enumerate block attributes: {block.Handle}") from exc
            for attribute in attributes:
                handle = str(attribute.Handle)
                if handle.casefold() not in wanted:
                    continue
                layer = str(attribute.Layer)
                found[handle.casefold()] = AttributeSnapshot(
                    handle=handle,
                    owner_block_handle=str(block.Handle),
                    tag=str(attribute.TagString),
                    value=str(attribute.TextString),
                    insertion_point=self._point(attribute.InsertionPoint),
                    layer=layer,
                    text_style=str(attribute.StyleName),
                    text_height=float(attribute.Height),
                    rotation_degrees=float(attribute.Rotation) * 180 / 3.141592653589793,
                    locked_layer=self._locked(layer),
                    is_xref="|" in layer or "|" in str(block.Name),
                )
        if set(found) != wanted:
            raise ValueError(f"attribute handles not found: {sorted(wanted - set(found))}")
        return tuple(found[handle.casefold()] for handle in handles)

    def attribute_entities(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for block, _owner, _nested in self._block_references().values():
            for attribute in tuple(block.GetAttributes()) if bool(block.HasAttributes) else ():
                result[str(attribute.Handle).casefold()] = attribute
        return result

    def blocks(self, handles: tuple[str, ...]) -> tuple[AttributeBlockSnapshot, ...]:
        references = self._block_references()
        result = []
        for handle in handles:
            row = references.get(handle.casefold())
            if row is None:
                raise ValueError(f"attribute block not found: {handle}")
            block, owner, nested = row
            attributes = tuple(block.GetAttributes()) if bool(block.HasAttributes) else ()
            tags = [str(attribute.TagString).casefold() for attribute in attributes]
            if len(tags) != len(set(tags)):
                raise ValueError(f"ABE cannot represent duplicate attribute tags: {handle}")
            layer = str(block.Layer)
            space = next(space for space, candidate in self._spaces() if candidate is owner)
            result.append(
                AttributeBlockSnapshot(
                    handle=str(block.Handle),
                    name=str(block.Name),
                    attributes={str(a.TagString): str(a.TextString) for a in attributes},
                    space=space,
                    nested=nested,
                    locked_layer=self._locked(layer),
                    is_xref="|" in layer or "|" in str(block.Name),
                )
            )
        return tuple(result)

    def table(self, handle: str) -> Any:
        entity = self.objects().get(handle.casefold())
        if entity is None or "table" not in str(entity.ObjectName).casefold():
            raise ValueError(f"table handle not found: {handle}")
        return entity

    def frames(self, measurements: tuple[LiveFrameMeasurement, ...]) -> tuple[MTextFrameSnapshot, ...]:
        result = []
        for measurement in measurements:
            entity = self.entity(measurement.handle)
            if str(entity.ObjectName).casefold() != "acdbmtext":
                raise ValueError(f"TFF requires MTEXT: {measurement.handle}")
            layer = str(entity.Layer)
            result.append(
                MTextFrameSnapshot(
                    handle=str(entity.Handle),
                    current_width=float(entity.Width),
                    measured_content_width=measurement.measured_content_width,
                    text_height=float(entity.TextHeight),
                    locked_layer=self._locked(layer),
                    is_xref="|" in layer,
                )
            )
        return tuple(result)


def _approval(execute: bool, fingerprint: str | None = None) -> Approval:
    return Approval(approved=execute, fingerprint=fingerprint)


def _same(actual: tuple[BaseModel, ...], expected: tuple[BaseModel, ...], alias: str) -> None:
    if _models(actual) != _models(expected):
        raise ValueError(f"{alias} preconditions no longer match the approved snapshots")


def _a2m_core(request: LiveA2mPreviewRequest, execute: bool, fingerprint: str | None = None) -> AttributeToTextRequest:
    return AttributeToTextRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        mode=request.mode,
        include_tag=request.include_tag,
        tag_separator=request.tag_separator,
        block_separator=request.block_separator,
        source_disposition=request.source_disposition,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_a2m(request: LiveA2mPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    attributes = adapter.attributes(request.target_handles)
    plan = plan_attribute_to_text(_a2m_core(request, False), attributes)
    payload = {**request.model_dump(mode="json"), "expected_attributes": _models(attributes)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_a2m(request: LiveA2mExecuteRequest) -> LiveText8aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact A2M request")
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    actual = adapter.attributes(request.target_handles)
    _same(actual, request.expected_attributes, "A2M")
    plan = plan_attribute_to_text(_a2m_core(request, True, request.approval_fingerprint), actual)
    doc = adapter.connect()
    attribute_entities = adapter.attribute_entities()
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        for conversion in plan.conversions:
            owner = adapter.owner(conversion.owner_block_handle)
            if conversion.output_kind is TextEntityKind.TEXT:
                entity = owner.AddText(
                    conversion.text, adapter.vector(conversion.insertion_point), conversion.text_height
                )
                entity.Height = conversion.text_height
            else:
                width = max(conversion.text_height, conversion.text_height * max(len(conversion.text), 1) * 2)
                entity = owner.AddMText(adapter.vector(conversion.insertion_point), width, conversion.text)
                entity.TextHeight = conversion.text_height
            entity.Layer = conversion.layer
            entity.StyleName = conversion.text_style
            entity.Rotation = radians(conversion.rotation_degrees)
            created.append(entity)
            if conversion.erase_source:
                for handle in conversion.source_handles:
                    attribute_entities[handle.casefold()].Delete()
    finally:
        doc.EndUndoMark()
    after_objects = adapter.objects()
    after_attributes = adapter.attribute_entities()
    created_handles = tuple(str(entity.Handle) for entity in created)
    erased = tuple(h for c in plan.conversions if c.erase_source for h in c.source_handles)
    verified = all(h.casefold() in after_objects for h in created_handles) and all(
        h.casefold() not in after_attributes for h in erased
    )
    verified = verified and all(
        str(entity.TextString) == conversion.text for entity, conversion in zip(created, plan.conversions, strict=True)
    )
    verified = verified and all(
        str(entity.Layer) == conversion.layer
        and str(entity.StyleName) == conversion.text_style
        and abs(float(entity.Rotation) - radians(conversion.rotation_degrees)) <= 1e-9
        and abs(
            float(entity.TextHeight if conversion.output_kind is TextEntityKind.MTEXT else entity.Height)
            - conversion.text_height
        )
        <= 1e-9
        for entity, conversion in zip(created, plan.conversions, strict=True)
    )
    if not verified:
        raise RuntimeError("A2M postcondition failed")
    return LiveText8aResult(
        document_name=str(doc.Name),
        command_alias="A2M",
        created_handles=created_handles,
        erased_handles=erased,
        postcondition_verified=True,
    )


def _abe_core(
    request: LiveAbePreviewRequest, execute: bool, fingerprint: str | None = None
) -> AttributeBlockEditRequest:
    return AttributeBlockEditRequest(
        document_id=request.document_name,
        target_block_handles=request.target_block_handles,
        edits=request.edits,
        include_nested=False,
        missing_tag_policy=request.missing_tag_policy,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_abe(request: LiveAbePreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    blocks = adapter.blocks(request.target_block_handles)
    plan = plan_attribute_block_edit(_abe_core(request, False), blocks)
    payload = {**request.model_dump(mode="json"), "expected_blocks": _models(blocks)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_abe(request: LiveAbeExecuteRequest) -> LiveText8aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact ABE request")
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    actual = adapter.blocks(request.target_block_handles)
    _same(actual, request.expected_blocks, "ABE")
    plan = plan_attribute_block_edit(_abe_core(request, True, request.approval_fingerprint), actual)
    references = adapter._block_references()
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            block = references[change.block_handle.casefold()][0]
            attributes = {str(a.TagString).casefold(): a for a in block.GetAttributes()}
            attributes[change.tag.casefold()].TextString = change.replacement_value
    finally:
        doc.EndUndoMark()
    after = adapter.blocks(request.target_block_handles)
    after_map = {b.handle.casefold(): {k.casefold(): v for k, v in b.attributes.items()} for b in after}
    if not all(after_map[c.block_handle.casefold()][c.tag.casefold()] == c.replacement_value for c in plan.changes):
        raise RuntimeError("ABE postcondition failed")
    return LiveText8aResult(
        document_name=str(doc.Name),
        command_alias="ABE",
        changed_handles=tuple(dict.fromkeys(c.block_handle for c in plan.changes)),
        postcondition_verified=True,
    )


def _ctx_core(request: LiveCtxPreviewRequest, execute: bool, fingerprint: str | None = None) -> ContextTextEditRequest:
    return ContextTextEditRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        old_text=request.old_text,
        new_text=request.new_text,
        selection_precedence=request.selection_precedence,
        whole_string_match=request.whole_string_match,
        replacement_policy=request.replacement_policy,
        case_sensitive=request.case_sensitive,
        zoom_text_height_factor=request.zoom_text_height_factor,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_ctx(request: LiveCtxPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    entities = adapter.snapshots(request.target_handles)
    plan = plan_context_text_edit(_ctx_core(request, False), entities)
    payload = {**request.model_dump(mode="json"), "expected_entities": _models(entities)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_ctx(request: LiveCtxExecuteRequest) -> LiveText8aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact CTX request")
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    actual = adapter.snapshots(request.target_handles)
    _same(actual, request.expected_entities, "CTX")
    plan = plan_context_text_edit(_ctx_core(request, True, request.approval_fingerprint), actual)
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            adapter.entity(change.handle).TextString = change.replacement_text
    finally:
        doc.EndUndoMark()
    if not all(str(adapter.entity(c.handle).TextString) == c.replacement_text for c in plan.changes):
        raise RuntimeError("CTX postcondition failed")
    return LiveText8aResult(
        document_name=str(doc.Name),
        command_alias="CTX",
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )


def _tc_core(request: LiveTcPreviewRequest, execute: bool, fingerprint: str | None = None) -> TextCopyRequest:
    return TextCopyRequest(
        document_id=request.document_name,
        placements=request.placements,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def _tc_state(
    adapter: ZWCADLiveText8aAdapter, request: LiveTcPreviewRequest
) -> tuple[tuple[TextEntitySnapshot, ...], tuple[LiveTableCellSnapshot, ...]]:
    handles = tuple(dict.fromkeys(p.source_handle for p in request.placements))
    entities = adapter.snapshots(handles)
    cells = []
    for placement in request.placements:
        if placement.table_handle is not None:
            table = adapter.table(placement.table_handle)
            text = str(table.GetText(placement.row, placement.column))
            if text != placement.expected_cell_text:
                raise ValueError(f"TC table cell precondition failed: {placement.table_handle}")
            cells.append(
                LiveTableCellSnapshot(
                    table_handle=placement.table_handle, row=placement.row, column=placement.column, text=text
                )
            )
    return entities, tuple(cells)


def preview_live_tc(request: LiveTcPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    entities, cells = _tc_state(adapter, request)
    plan = plan_text_copy(_tc_core(request, False), entities)
    payload = {
        **request.model_dump(mode="json"),
        "expected_entities": _models(entities),
        "expected_cells": _models(cells),
    }
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_tc(request: LiveTcExecuteRequest) -> LiveText8aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact TC request")
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    entities, cells = _tc_state(adapter, request)
    _same(entities, request.expected_entities, "TC")
    _same(cells, request.expected_cells, "TC table")
    plan = plan_text_copy(_tc_core(request, True, request.approval_fingerprint), entities)
    source_by_handle = {item.handle.casefold(): item for item in entities}
    doc = adapter.connect()
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        create_index = 0
        for placement in request.placements:
            if placement.destination is not TextCopyDestination.NEW_TEXT:
                continue
            spec = plan.creates[create_index]
            create_index += 1
            source = source_by_handle[placement.source_handle.casefold()]
            entity = adapter.owner(source.handle).AddText(
                spec.text, adapter.vector(spec.insertion_point), spec.text_height
            )
            entity.Layer, entity.StyleName, entity.Rotation = (
                spec.layer,
                spec.text_style,
                radians(spec.rotation_degrees),
            )
            created.append(entity)
        for change in plan.table_changes:
            adapter.table(change.table_handle).SetText(change.row, change.column, change.replacement_text)
    finally:
        doc.EndUndoMark()
    handles = tuple(str(entity.Handle) for entity in created)
    verified = all(h.casefold() in adapter.objects() for h in handles)
    verified = verified and all(
        str(entity.TextString) == spec.text
        and str(entity.Layer) == spec.layer
        and str(entity.StyleName) == spec.text_style
        and abs(float(entity.Height) - spec.text_height) <= 1e-9
        and abs(float(entity.Rotation) - radians(spec.rotation_degrees)) <= 1e-9
        for entity, spec in zip(created, plan.creates, strict=True)
    )
    verified = verified and all(
        str(adapter.table(c.table_handle).GetText(c.row, c.column)) == c.replacement_text for c in plan.table_changes
    )
    if not verified:
        raise RuntimeError("TC postcondition failed")
    return LiveText8aResult(
        document_name=str(doc.Name),
        command_alias="TC",
        created_handles=handles,
        changed_handles=tuple(c.table_handle for c in plan.table_changes),
        postcondition_verified=True,
    )


def _te_core(
    request: LiveTePreviewRequest, execute: bool, fingerprint: str | None = None
) -> ComprehensiveTextEditRequest:
    return ComprehensiveTextEditRequest(
        document_id=request.document_name,
        patches=request.patches,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_te(request: LiveTePreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    entities = adapter.snapshots(tuple(p.handle for p in request.patches))
    by_handle = {e.handle.casefold(): e for e in entities}
    for patch in request.patches:
        if patch.width_factor is not None and by_handle[patch.handle.casefold()].kind is TextEntityKind.MTEXT:
            raise ValueError("TE WidthFactor is unsupported for MTEXT")
        if patch.target_layer is not None:
            adapter.connect().Layers.Item(patch.target_layer)
        if patch.target_style is not None:
            adapter.connect().TextStyles.Item(patch.target_style)
    plan = plan_comprehensive_text_edit(_te_core(request, False), entities)
    payload = {**request.model_dump(mode="json"), "expected_entities": _models(entities)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_te(request: LiveTeExecuteRequest) -> LiveText8aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact TE request")
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    actual = adapter.snapshots(tuple(p.handle for p in request.patches))
    _same(actual, request.expected_entities, "TE")
    plan = plan_comprehensive_text_edit(_te_core(request, True, request.approval_fingerprint), actual)
    kind_by_handle = {e.handle.casefold(): e.kind for e in actual}
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            entity = adapter.entity(change.handle)
            if change.replacement_text is not None:
                entity.TextString = change.replacement_text
            if change.target_layer is not None:
                entity.Layer = change.target_layer
            if change.target_style is not None:
                entity.StyleName = change.target_style
            if change.text_height is not None:
                if kind_by_handle[change.handle.casefold()] is TextEntityKind.MTEXT:
                    entity.TextHeight = change.text_height
                else:
                    entity.Height = change.text_height
            if change.width_factor is not None:
                entity.WidthFactor = change.width_factor
            if change.rotation_degrees is not None:
                entity.Rotation = radians(change.rotation_degrees)
    finally:
        doc.EndUndoMark()
    for change in plan.changes:
        entity = adapter.entity(change.handle)
        if change.replacement_text is not None and str(entity.TextString) != change.replacement_text:
            raise RuntimeError("TE postcondition failed")
        if change.target_layer is not None and str(entity.Layer) != change.target_layer:
            raise RuntimeError("TE postcondition failed")
        if change.target_style is not None and str(entity.StyleName) != change.target_style:
            raise RuntimeError("TE postcondition failed")
        if change.text_height is not None:
            height = (
                entity.TextHeight if kind_by_handle[change.handle.casefold()] is TextEntityKind.MTEXT else entity.Height
            )
            if abs(float(height) - change.text_height) > 1e-9:
                raise RuntimeError("TE postcondition failed")
        if change.width_factor is not None and abs(float(entity.WidthFactor) - change.width_factor) > 1e-9:
            raise RuntimeError("TE postcondition failed")
        if (
            change.rotation_degrees is not None
            and abs(float(entity.Rotation) - radians(change.rotation_degrees)) > 1e-9
        ):
            raise RuntimeError("TE postcondition failed")
    return LiveText8aResult(
        document_name=str(doc.Name),
        command_alias="TE",
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )


def _tff_core(request: LiveTffPreviewRequest, execute: bool, fingerprint: str | None = None) -> MTextFrameFitRequest:
    return MTextFrameFitRequest(
        document_id=request.document_name,
        target_handles=tuple(m.handle for m in request.measurements),
        mode=request.mode,
        horizontal_padding_height_factor=request.horizontal_padding_height_factor,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_tff(request: LiveTffPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    frames = adapter.frames(request.measurements)
    plan = plan_mtext_frame_fit(_tff_core(request, False), frames)
    payload = {**request.model_dump(mode="json"), "expected_frames": _models(frames)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_tff(request: LiveTffExecuteRequest) -> LiveText8aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact TFF request")
    adapter = ZWCADLiveText8aAdapter(request.document_name)
    actual = adapter.frames(request.measurements)
    _same(actual, request.expected_frames, "TFF")
    plan = plan_mtext_frame_fit(_tff_core(request, True, request.approval_fingerprint), actual)
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            adapter.entity(change.handle).Width = change.replacement_width
    finally:
        doc.EndUndoMark()
    if not all(abs(float(adapter.entity(c.handle).Width) - c.replacement_width) <= 1e-9 for c in plan.changes):
        raise RuntimeError("TFF postcondition failed")
    return LiveText8aResult(
        document_name=str(doc.Name),
        command_alias="TFF",
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )


def register_live_text_batch8a_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 8A text operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 8A text operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_a2m", preview_live_a2m, preview),
        ("xicad_execute_live_a2m", execute_live_a2m, execute),
        ("xicad_preview_live_abe", preview_live_abe, preview),
        ("xicad_execute_live_abe", execute_live_abe, execute),
        ("xicad_preview_live_ctx", preview_live_ctx, preview),
        ("xicad_execute_live_ctx", execute_live_ctx, execute),
        ("xicad_preview_live_tc", preview_live_tc, preview),
        ("xicad_execute_live_tc", execute_live_tc, execute),
        ("xicad_preview_live_te", preview_live_te, preview),
        ("xicad_execute_live_te", execute_live_te, execute),
        ("xicad_preview_live_tff", preview_live_tff, preview),
        ("xicad_execute_live_tff", execute_live_tff, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
