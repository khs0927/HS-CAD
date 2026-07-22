"""Truthful ZWCAD live previews and the evidence-bounded Batch 28 write adapter."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch28a import (
    BlockQuantityRequest,
    ChangeBlockScaleRequest,
    CopyObjectsToXrefRequest,
    MakeBlockInPlaceRequest,
    RemoveBlockMembersRequest,
    RenameBlocksRequest,
    plan_block_quantity,
    plan_change_block_scale,
    plan_copy_objects_to_xref,
    plan_make_block_in_place,
    plan_remove_block_members,
    plan_rename_blocks,
)
from .headless_core_batch28b import (
    ExplodeAttributesRetainingTextRequest,
    MultiFileBlockChangeRequest,
    MultiFileXrefChangeRequest,
    MultiInsertToBlocksRequest,
    MultiXclipRequest,
    WblockExportRequest,
    plan_explode_attributes_retaining_text,
    plan_multi_file_block_change,
    plan_multi_file_xref_change,
    plan_multi_insert_to_blocks,
    plan_multi_xclip,
    plan_wblock_export,
)


class LiveBlockReferenceEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    block_name: str
    layer: str
    insertion_point: Point3D
    rotation_radians: float
    scale_x: float
    scale_y: float
    scale_z: float
    state_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    locked_layer: bool
    is_xref: bool


class LiveBSCExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ChangeBlockScaleRequest
    expected_sources: tuple[LiveBlockReferenceEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch28Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


BLOCKED = {
    "BLX": "compiled block-definition ownership, transforms, attributes, and dynamic-block behavior are unrecovered",
    "BQT": "table/CSV serialization, overlap and area grouping, and output placement semantics are unrecovered",
    "BRM": "compiled nested block-definition editing, ownership, transforms, and reference refresh are unrecovered",
    "BRN": "copy-versus-rename definition cloning, collision, dependency, and dynamic-block semantics are unrecovered",
    "CX": "xref file transforms, locking, atomic save/reload, and cross-document recovery are unrecovered",
    "EAR": "explode topology and exact attribute-to-text formatting and transform behavior are unrecovered",
    "M2B": "multi-insert array transforms, attributes, dynamic properties, and source replacement are unrecovered",
    "MFB": "multi-file open/change/save, dependency, lock, and atomic rollback behavior are unrecovered",
    "MFX": "multi-file xref path, detach/bind, dependency, save, and rollback behavior are unrecovered",
    "MX": "XCLIP boundary coordinate transforms, inversion, replacement, and eligibility are unrecovered",
    "QWB": "WBLOCK version, units, dependencies, file overwrite, and atomic export behavior are unrecovered",
}


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _drawing(name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _entities(doc: Any) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    for block in doc.Blocks:
        if bool(block.IsLayout):
            for entity in block:
                entities[str(entity.Handle).casefold()] = entity
    return entities


def _point(value: Any) -> Point3D:
    coordinates = tuple(float(item) for item in value)
    return Point3D(x=coordinates[0], y=coordinates[1], z=coordinates[2] if len(coordinates) > 2 else 0.0)


def _is_xref(doc: Any, entity: Any, block_name: str, layer: str) -> bool:
    if "|" in layer:
        return True
    try:
        return bool(doc.Blocks.Item(block_name).IsXRef)
    except Exception:
        try:
            return bool(entity.IsXRef)
        except Exception:
            return False


def _block_evidence(doc: Any, handle: str) -> tuple[LiveBlockReferenceEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"Batch 28 block reference does not exist: {handle}")
    if str(entity.ObjectName).casefold() != "acdbblockreference":
        raise ValueError(f"Batch 28 BSC source is not a block reference: {handle}")
    name = str(getattr(entity, "EffectiveName", "") or entity.Name)
    layer = str(entity.Layer)
    locked = bool(doc.Layers.Item(layer).Lock)
    xref = _is_xref(doc, entity, name, layer)
    if locked or xref:
        raise ValueError(f"Batch 28 block reference is locked or xref-dependent: {handle}")
    state = {
        "handle": str(entity.Handle),
        "block_name": name,
        "layer": layer,
        "insertion_point": _point(entity.InsertionPoint).model_dump(mode="json"),
        "rotation_radians": float(entity.Rotation),
        "scale_x": float(entity.XScaleFactor),
        "scale_y": float(entity.YScaleFactor),
        "scale_z": float(entity.ZScaleFactor),
    }
    return LiveBlockReferenceEvidence(
        **state,
        state_fingerprint=_fingerprint(state),
        locked_layer=locked,
        is_xref=xref,
    ), entity


def _plan(request: Any) -> Any:
    planners = {
        MakeBlockInPlaceRequest: plan_make_block_in_place,
        BlockQuantityRequest: plan_block_quantity,
        RemoveBlockMembersRequest: plan_remove_block_members,
        RenameBlocksRequest: plan_rename_blocks,
        ChangeBlockScaleRequest: plan_change_block_scale,
        CopyObjectsToXrefRequest: plan_copy_objects_to_xref,
        ExplodeAttributesRetainingTextRequest: plan_explode_attributes_retaining_text,
        MultiInsertToBlocksRequest: plan_multi_insert_to_blocks,
        MultiFileBlockChangeRequest: plan_multi_file_block_change,
        MultiFileXrefChangeRequest: plan_multi_file_xref_change,
        MultiXclipRequest: plan_multi_xclip,
        WblockExportRequest: plan_wblock_export,
    }
    for request_type, planner in planners.items():
        if isinstance(request, request_type):
            return planner(request)
    raise TypeError(f"unsupported Batch 28 request: {type(request).__name__}")


def _preview_blocked(request: Any) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _plan(request)
    payload = {
        "command_alias": plan.command_alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
    }
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "live_executable": False,
        "blocked_reason": BLOCKED[plan.command_alias],
    }


def _bsc_payload(request: ChangeBlockScaleRequest, plan: Any, sources: tuple[LiveBlockReferenceEvidence, ...]) -> dict[str, Any]:
    return {
        "command_alias": "BSC",
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
    }


def _validate_bsc_live_scope(request: ChangeBlockScaleRequest) -> None:
    snapshots = {item.handle.casefold(): item for item in request.references}
    for result in request.exact_results:
        source = snapshots[result.source_handle.casefold()]
        if (
            result.insertion_point != source.insertion_point
            or result.rotation_radians != source.rotation_radians
            or result.scale_z != source.scale_z
            or result.layer.casefold() != source.layer.casefold()
        ):
            raise ValueError("Batch 28 BSC live execution permits only official-help X/Y scale changes")
        if (result.scale_x, result.scale_y) == (source.scale_x, source.scale_y):
            raise ValueError("Batch 28 BSC live execution must change X or Y scale")


def preview_live_bsc(request: ChangeBlockScaleRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = plan_change_block_scale(request)
    _validate_bsc_live_scope(request)
    doc = _drawing(request.document_id)
    snapshots = {item.handle.casefold(): item for item in request.references}
    sources = tuple(_block_evidence(doc, result.source_handle)[0] for result in request.exact_results)
    for evidence in sources:
        snapshot = snapshots[evidence.handle.casefold()]
        if (
            evidence.block_name.casefold() != snapshot.block_name.casefold()
            or evidence.layer.casefold() != snapshot.layer.casefold()
            or evidence.insertion_point != snapshot.insertion_point
            or evidence.rotation_radians != snapshot.rotation_radians
            or (evidence.scale_x, evidence.scale_y, evidence.scale_z)
            != (snapshot.scale_x, snapshot.scale_y, snapshot.scale_z)
        ):
            raise ValueError(f"Batch 28 BSC source does not match snapshot: {snapshot.handle}")
    for result in request.exact_results:
        try:
            layer = doc.Layers.Item(result.layer)
        except Exception as exc:
            raise ValueError(f"Batch 28 BSC target layer does not exist: {result.layer}") from exc
        if bool(layer.Lock) or "|" in str(layer.Name):
            raise ValueError(f"Batch 28 BSC target layer is locked or xref-dependent: {result.layer}")
    payload = _bsc_payload(request, plan, sources)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "official-help X/Y scale changes are stale-checked; absolute/ratio acquisition remains caller-resolved and full legacy equivalence is not claimed",
    }


def execute_live_bsc(request: LiveBSCExecuteRequest) -> LiveBatch28Result:
    plan = plan_change_block_scale(request.request)
    _validate_bsc_live_scope(request.request)
    payload = _bsc_payload(request.request, plan, request.expected_sources)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 28 BSC preview")
    doc = _drawing(request.request.document_id)
    current_pairs = tuple(_block_evidence(doc, result.source_handle) for result in request.request.exact_results)
    current = tuple(item[0] for item in current_pairs)
    if current != request.expected_sources:
        raise ValueError("Batch 28 BSC source state no longer matches the approved preview")
    entities = {evidence.handle.casefold(): entity for evidence, entity in current_pairs}
    for result in request.request.exact_results:
        layer = doc.Layers.Item(result.layer)
        if bool(layer.Lock) or "|" in str(layer.Name):
            raise ValueError(f"Batch 28 BSC target layer is locked or xref-dependent: {result.layer}")

    doc.StartUndoMark()
    try:
        for result in request.request.exact_results:
            entity = entities[result.source_handle.casefold()]
            entity.XScaleFactor = result.scale_x
            entity.YScaleFactor = result.scale_y
    finally:
        doc.EndUndoMark()

    for result in request.request.exact_results:
        entity = _entities(doc).get(result.source_handle.casefold())
        if entity is None or (
            _point(entity.InsertionPoint) != result.insertion_point
            or float(entity.Rotation) != result.rotation_radians
            or (float(entity.XScaleFactor), float(entity.YScaleFactor), float(entity.ZScaleFactor))
            != (result.scale_x, result.scale_y, result.scale_z)
            or str(entity.Layer).casefold() != result.layer.casefold()
        ):
            raise RuntimeError(f"BSC postcondition failed for block reference: {result.source_handle}")
    return LiveBatch28Result(
        document_name=str(doc.Name),
        command_alias="BSC",
        changed_handles=tuple(result.source_handle for result in request.request.exact_results),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def preview_live_blx(request: MakeBlockInPlaceRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_bqt(request: BlockQuantityRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_brm(request: RemoveBlockMembersRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_brn(request: RenameBlocksRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_cx(request: CopyObjectsToXrefRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_ear(request: ExplodeAttributesRetainingTextRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_m2b(request: MultiInsertToBlocksRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_mfb(request: MultiFileBlockChangeRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_mfx(request: MultiFileXrefChangeRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_mx(request: MultiXclipRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_qwb(request: WblockExportRequest) -> dict[str, Any]: return _preview_blocked(request)


def register_live_batch28_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(title="Preview live xiCAD Batch 28 operation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    execute = ToolAnnotations(title="Execute live xiCAD Batch 28 operation", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
    functions = {
        "blx": preview_live_blx, "bqt": preview_live_bqt, "brm": preview_live_brm,
        "brn": preview_live_brn, "bsc": preview_live_bsc, "cx": preview_live_cx,
        "ear": preview_live_ear, "m2b": preview_live_m2b, "mfb": preview_live_mfb,
        "mfx": preview_live_mfx, "mx": preview_live_mx, "qwb": preview_live_qwb,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
    mcp.tool(name="xicad_execute_live_bsc", annotations=execute)(execute_live_bsc)
