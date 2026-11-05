from __future__ import annotations

import hashlib
import json
from math import degrees, radians
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch3 import (
    AttributeBlockRotateRequest,
    AttributeBlockSnapshot,
    AttributePreservation,
    BlockRecordSnapshot,
    GhostClassification,
    GhostCleanupRequest,
    NullBlockCleanupRequest,
    RotationMode,
    plan_attribute_block_rotate,
    plan_ghost_cleanup,
    plan_null_block_cleanup,
)


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _point(value: Any, name: str) -> Point3D:
    try:
        coordinates = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"ZWCAD returned invalid {name}") from exc
    if len(coordinates) != 3:
        raise RuntimeError(f"ZWCAD returned invalid {name}")
    return Point3D(x=coordinates[0], y=coordinates[1], z=coordinates[2])


def _model_list(items: tuple[BaseModel, ...]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]


class LiveAttributeState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    handle: str = Field(min_length=1)
    insertion_point: Point3D
    rotation_radians: float
    alignment: int = 0
    text_alignment_point: Point3D | None = None


class LiveAttributeBlockSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    block: AttributeBlockSnapshot
    attributes: tuple[LiveAttributeState, ...]


class LiveBarPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)
    block_handles: tuple[str, ...] = Field(min_length=1)
    rotation_mode: RotationMode
    angle_degrees: float
    attribute_preservation: AttributePreservation


class LiveBarExecuteRequest(LiveBarPreviewRequest):
    expected_blocks: tuple[LiveAttributeBlockSnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveAbdPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)
    target_names: tuple[str, ...] = ()
    preserve_names: tuple[str, ...] = ("*Model_Space", "*Paper_Space")


class LiveAbdExecuteRequest(LiveAbdPreviewRequest):
    expected_records: tuple[BlockRecordSnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveAgdPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)
    accepted_classifications: tuple[GhostClassification, ...] = Field(min_length=1)
    target_handles: tuple[str, ...] = ()


class LiveAgdExecuteRequest(LiveAgdPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveAnnotationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...]
    removed_handles: tuple[str, ...]
    postcondition_verified: bool


class ZWCADLiveAnnotationAdapter:
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

    def drawing_objects(self) -> dict[str, Any]:
        doc = self.connect()
        objects: dict[str, Any] = {}
        for entity in doc.ModelSpace:
            objects[str(entity.Handle).casefold()] = entity
        for layout in doc.Layouts:
            if str(layout.Name).casefold() == "model":
                continue
            for entity in layout.Block:
                objects[str(entity.Handle).casefold()] = entity
        return objects

    def block_reference(self, handle: str) -> Any:
        entity = self.drawing_objects().get(handle.casefold())
        if entity is None or "blockreference" not in str(entity.ObjectName).casefold():
            raise ValueError(f"block reference handle not found: {handle}")
        return entity

    @staticmethod
    def _block_name(reference: Any) -> str:
        try:
            effective = str(reference.EffectiveName)
            if effective:
                return effective
        except Exception:
            pass
        return str(reference.Name)

    def _definition(self, name: str) -> Any:
        doc = self.connect()
        try:
            return doc.Blocks.Item(name)
        except Exception as exc:
            raise RuntimeError(f"block definition is unavailable: {name}") from exc

    def read_bar(self, handles: tuple[str, ...]) -> tuple[LiveAttributeBlockSnapshot, ...]:
        snapshots: list[LiveAttributeBlockSnapshot] = []
        for handle in handles:
            reference = self.block_reference(handle)
            name = self._block_name(reference)
            try:
                attributes = tuple(reference.GetAttributes()) if bool(reference.HasAttributes) else ()
                attribute_states = tuple(
                    LiveAttributeState(
                        handle=str(attribute.Handle),
                        insertion_point=_point(attribute.InsertionPoint, "attribute InsertionPoint"),
                        rotation_radians=float(attribute.Rotation),
                        alignment=int(attribute.Alignment),
                        text_alignment_point=(
                            _point(attribute.TextAlignmentPoint, "attribute TextAlignmentPoint")
                            if int(attribute.Alignment) != 0
                            else None
                        ),
                    )
                    for attribute in attributes
                )
                non_attributes = sum(
                    1
                    for entity in self._definition(name)
                    if "attributedefinition" not in str(entity.ObjectName).casefold()
                )
                block = AttributeBlockSnapshot(
                    handle=str(reference.Handle),
                    block_name=name,
                    current_rotation_degrees=degrees(float(reference.Rotation)),
                    attribute_handles=tuple(state.handle for state in attribute_states),
                    non_attribute_entity_count=non_attributes,
                )
            except Exception as exc:
                raise RuntimeError(f"ZWCAD cannot provide the exact BAR state for {handle}") from exc
            snapshots.append(LiveAttributeBlockSnapshot(block=block, attributes=attribute_states))
        return tuple(snapshots)

    def vector(self, point: Point3D) -> Any:
        import pythoncom
        import win32com.client

        return win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8,
            [point.x, point.y, point.z],
        )

    def list_block_records(self) -> tuple[BlockRecordSnapshot, ...]:
        doc = self.connect()
        counts: dict[str, int] = {}
        seen_references: set[str] = set()
        # Scan every block record, not just model/paper space: an empty block can
        # still be referenced by a nested block definition.
        for owner_record in doc.Blocks:
            for entity in owner_record:
                if "blockreference" not in str(entity.ObjectName).casefold():
                    continue
                handle = str(entity.Handle).casefold()
                if handle in seen_references:
                    continue
                seen_references.add(handle)
                names = {str(entity.Name).casefold(), self._block_name(entity).casefold()}
                for name in names:
                    counts[name] = counts.get(name, 0) + 1
        records: list[BlockRecordSnapshot] = []
        for record in doc.Blocks:
            name = str(record.Name)
            try:
                is_layout = bool(record.IsLayout)
                is_xref = bool(record.IsXRef)
            except Exception as exc:
                raise RuntimeError(f"ZWCAD cannot classify block record {name}") from exc
            try:
                is_dynamic = bool(record.IsDynamicBlock)
            except Exception:
                is_dynamic = False
            records.append(
                BlockRecordSnapshot(
                    handle=str(record.Handle),
                    name=name,
                    reference_count=counts.get(name.casefold(), 0),
                    entity_count=sum(1 for _ in record),
                    is_layout=is_layout,
                    is_xref=is_xref,
                    is_dynamic_base=is_dynamic,
                    is_system=name.startswith("*"),
                )
            )
        return tuple(records)

    def block_records(self) -> dict[str, Any]:
        doc = self.connect()
        return {str(record.Handle).casefold(): record for record in doc.Blocks}

    def inspect_ghost_objects(self) -> tuple[Any, ...]:
        raise RuntimeError(
            "AGD is unavailable through ZWCAD ActiveX: erased residents, orphaned owners, "
            "and invalid database objects are not enumerable with verifiable classifications"
        )


def _bar_core_request(
    request: LiveBarPreviewRequest, *, execute: bool, fingerprint: str | None = None
) -> AttributeBlockRotateRequest:
    return AttributeBlockRotateRequest(
        document_id=request.document_name,
        block_handles=request.block_handles,
        rotation_mode=request.rotation_mode,
        angle_degrees=request.angle_degrees,
        attribute_preservation=request.attribute_preservation,
        dry_run=not execute,
        approval=Approval(approved=execute, fingerprint=fingerprint),
    )


def preview_live_bar(request: LiveBarPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveAnnotationAdapter(request.document_name)
    snapshots = adapter.read_bar(request.block_handles)
    plan = plan_attribute_block_rotate(
        _bar_core_request(request, execute=False), tuple(snapshot.block for snapshot in snapshots)
    )
    payload = {**request.model_dump(mode="json"), "expected_blocks": _model_list(snapshots)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def _angle_matches(actual: float, expected: float) -> bool:
    return abs((actual - expected + 180.0) % 360.0 - 180.0) <= 1e-7


def execute_live_bar(request: LiveBarExecuteRequest) -> LiveAnnotationResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact BAR request")
    adapter = ZWCADLiveAnnotationAdapter(request.document_name)
    before = adapter.read_bar(request.block_handles)
    if _model_list(before) != _model_list(request.expected_blocks):
        raise ValueError("BAR block preconditions no longer match the approved snapshots")
    plan = plan_attribute_block_rotate(
        _bar_core_request(request, execute=True, fingerprint=request.approval_fingerprint),
        tuple(snapshot.block for snapshot in before),
    )
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for operation, snapshot in zip(plan.operations, before, strict=True):
            reference = adapter.block_reference(operation.block_handle)
            reference.Rotate(reference.InsertionPoint, radians(operation.delta_degrees))
            attributes = {str(item.Handle).casefold(): item for item in reference.GetAttributes()}
            for state in snapshot.attributes:
                attribute = attributes[state.handle.casefold()]
                if operation.attribute_preservation is AttributePreservation.WORLD_POSITION_AND_ROTATION:
                    attribute.InsertionPoint = adapter.vector(state.insertion_point)
                    if state.text_alignment_point is not None:
                        attribute.TextAlignmentPoint = adapter.vector(state.text_alignment_point)
                    attribute.Rotation = state.rotation_radians
                elif operation.attribute_preservation is AttributePreservation.WORLD_ROTATION_ONLY:
                    attribute.Rotation = state.rotation_radians
    finally:
        doc.EndUndoMark()
    after = adapter.read_bar(request.block_handles)
    verified = True
    for operation, old, new in zip(plan.operations, before, after, strict=True):
        verified = verified and _angle_matches(new.block.current_rotation_degrees, operation.target_rotation_degrees)
        old_attributes = {item.handle.casefold(): item for item in old.attributes}
        for state in new.attributes:
            prior = old_attributes[state.handle.casefold()]
            if operation.attribute_preservation is AttributePreservation.WORLD_POSITION_AND_ROTATION:
                verified = verified and state.insertion_point == prior.insertion_point
                verified = verified and state.text_alignment_point == prior.text_alignment_point
            if operation.attribute_preservation is not AttributePreservation.FOLLOW_BLOCK:
                verified = verified and abs(state.rotation_radians - prior.rotation_radians) <= 1e-9
    if not verified:
        raise RuntimeError("BAR postcondition failed")
    return LiveAnnotationResult(
        document_name=str(doc.Name),
        command_alias="BAR",
        changed_handles=tuple(operation.block_handle for operation in plan.operations),
        removed_handles=(),
        postcondition_verified=True,
    )


def _abd_core_request(
    request: LiveAbdPreviewRequest, *, execute: bool, fingerprint: str | None = None
) -> NullBlockCleanupRequest:
    return NullBlockCleanupRequest(
        document_id=request.document_name,
        target_names=request.target_names,
        preserve_names=request.preserve_names,
        dry_run=not execute,
        approval=Approval(approved=execute, fingerprint=fingerprint),
    )


def preview_live_abd(request: LiveAbdPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveAnnotationAdapter(request.document_name)
    records = adapter.list_block_records()
    plan = plan_null_block_cleanup(_abd_core_request(request, execute=False), records)
    payload = {**request.model_dump(mode="json"), "expected_records": _model_list(records)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_abd(request: LiveAbdExecuteRequest) -> LiveAnnotationResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact ABD request")
    adapter = ZWCADLiveAnnotationAdapter(request.document_name)
    before = adapter.list_block_records()
    if _model_list(before) != _model_list(request.expected_records):
        raise ValueError("ABD block-table precondition no longer matches the approved snapshot")
    plan = plan_null_block_cleanup(
        _abd_core_request(request, execute=True, fingerprint=request.approval_fingerprint), before
    )
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        records = adapter.block_records()
        for handle in plan.purge_handles:
            record = records.get(handle.casefold())
            if record is None:
                raise ValueError(f"approved block record disappeared: {handle}")
            try:
                record.Delete()
            except Exception as exc:
                raise RuntimeError(f"ZWCAD refused to delete approved empty block record {handle}") from exc
    finally:
        doc.EndUndoMark()
    after_handles = {record.handle.casefold() for record in adapter.list_block_records()}
    if not all(handle.casefold() not in after_handles for handle in plan.purge_handles):
        raise RuntimeError("ABD postcondition failed")
    return LiveAnnotationResult(
        document_name=str(doc.Name),
        command_alias="ABD",
        changed_handles=(),
        removed_handles=plan.purge_handles,
        postcondition_verified=True,
    )


def preview_live_agd(request: LiveAgdPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveAnnotationAdapter(request.document_name)
    objects = adapter.inspect_ghost_objects()
    core_request = GhostCleanupRequest(
        document_id=request.document_name,
        accepted_classifications=request.accepted_classifications,
        target_handles=request.target_handles,
        dry_run=True,
    )
    plan = plan_ghost_cleanup(core_request, objects)
    payload = request.model_dump(mode="json")
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_agd(request: LiveAgdExecuteRequest) -> LiveAnnotationResult:
    if request.approval_fingerprint != _hash(request.model_dump(mode="json", exclude={"approval_fingerprint"})):
        raise ValueError("approval fingerprint does not match the exact AGD request")
    adapter = ZWCADLiveAnnotationAdapter(request.document_name)
    adapter.inspect_ghost_objects()
    raise RuntimeError("AGD cannot execute without a verifiable ZWCAD database-object inspection API")


def register_live_annotation_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD annotation maintenance",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD annotation maintenance",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_bar", preview_live_bar, preview),
        ("xicad_execute_live_bar", execute_live_bar, execute),
        ("xicad_preview_live_abd", preview_live_abd, preview),
        ("xicad_execute_live_abd", execute_live_abd, execute),
        ("xicad_preview_live_agd", preview_live_agd, preview),
        ("xicad_execute_live_agd", execute_live_agd, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
