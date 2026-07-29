"""Truthful ZWCAD live previews and evidence-bounded Batch 30 writes."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch30a import (
    AllViewportUnlockRequest,
    CorrectErrorRequest,
    DrawingBackupRequest,
    LayoutToDrawingsRequest,
    ViewportRotateRequest,
    ViewportState,
    ViewportUnlockRequest,
    plan_all_viewports_unlock,
    plan_correct_error,
    plan_drawing_backup,
    plan_layout_to_drawings,
    plan_viewport_rotate,
    plan_viewport_unlock,
)
from .headless_core_batch30b import (
    AutoPlotRequest,
    DeletePlotBoxesRequest,
    InsertBlocksRequest,
    MultiFileOrganizeRequest,
    PlotBoxCreateRequest,
    PlotBoxMultiMakeRequest,
    VersionedEntitySnapshot,
    plan_auto_plot,
    plan_delete_plot_boxes,
    plan_insert_blocks,
    plan_multi_file_organize,
    plan_plot_box_create,
    plan_plot_box_multi_make,
)

HELP_URLS = {
    "VSD": "https://izzarder.com/285",
    "BAK": "https://izzarder.com/502",
    "CER": "https://izzarder.com/?page=89",
    "IB": "https://izzarder.com/175",
    "MSL": "https://izzarder.com/265",
    "PB": "https://izzarder.com/43",
    "PBD": "https://izzarder.com/43",
    "PBM": "https://izzarder.com/133",
    "PPP": "https://izzarder.com/43",
}

BLOCKED = {
    "VR": "compiled viewport rotation acquisition, UCS/view transform, clipping, and lock behavior are unrecovered",
    "VSD": "layout export, DWG serialization, collision handling, references, and filesystem rollback are unrecovered",
    "BAK": "backup serialization, timestamp/collision behavior, unsaved drawings, and filesystem rollback are unrecovered",
    "CER": "compiled coordinate quantization, topology, block traversal, correction order, and property preservation are unrecovered",
    "IB": "file probing, transforms, block naming/collisions, PDF/image import, xref binding, and rollback are unrecovered",
    "MSL": "multi-file open/change/save, script safety, collision numbering, and failure recovery are unrecovered",
    "PB": "compiled point acquisition, exact rectangle geometry, metadata, setup color, and current-space behavior are unrecovered",
    "PBM": "compiled selection expansion, closure/tolerance, border geometry/properties, and retention default are unrecovered",
    "PPP": "plot discovery, device APIs, output naming, PDF merge, retries, and file/printer side effects are unrecovered",
}


class LiveViewportEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    handle: str
    object_name: str
    owner: str
    layer: str
    center: Point3D
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    view_twist_radians: float
    display_locked: bool
    viewport_number: int | None
    state_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    locked_layer: bool
    is_xref: bool


class LivePlotBoxEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    object_name: str
    owner: str
    layer: str
    state_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    locked_layer: bool
    is_xref: bool


class LiveVUExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ViewportUnlockRequest
    expected_sources: tuple[LiveViewportEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveVUUExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: AllViewportUnlockRequest
    expected_sources: tuple[LiveViewportEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LivePBDExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: DeletePlotBoxesRequest
    expected_sources: tuple[LivePlotBoxEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch30Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


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


def _entities(doc: Any) -> dict[str, tuple[Any, str]]:
    entities: dict[str, tuple[Any, str]] = {}
    for block in doc.Blocks:
        if not bool(block.IsLayout):
            continue
        owner = str(block.Layout.Name)
        for entity in block:
            entities[str(entity.Handle).casefold()] = entity, owner
    return entities


def _point(value: Any) -> Point3D:
    coordinates = tuple(float(item) for item in value)
    return Point3D(x=coordinates[0], y=coordinates[1], z=coordinates[2] if len(coordinates) > 2 else 0.0)


def _viewport_evidence(doc: Any, handle: str) -> tuple[LiveViewportEvidence, Any]:
    pair = _entities(doc).get(handle.casefold())
    if pair is None:
        raise ValueError(f"Batch 30 viewport does not exist: {handle}")
    entity, owner = pair
    if str(entity.ObjectName).casefold() != "acdbviewport":
        raise ValueError(f"Batch 30 source is not a viewport: {handle}")
    layer = str(entity.Layer)
    locked = bool(doc.Layers.Item(layer).Lock)
    xref = "|" in layer
    if locked or xref:
        raise ValueError(f"Batch 30 viewport is locked or xref-dependent: {handle}")
    try:
        number: int | None = int(entity.Number)
    except Exception:
        number = None
    state = {
        "handle": str(entity.Handle),
        "object_name": str(entity.ObjectName),
        "owner": owner,
        "layer": layer,
        "center": _point(entity.Center).model_dump(mode="json"),
        "width": float(entity.Width),
        "height": float(entity.Height),
        "view_twist_radians": float(entity.TwistAngle),
        "display_locked": bool(entity.DisplayLocked),
        "viewport_number": number,
    }
    return LiveViewportEvidence(
        **state,
        state_fingerprint=_fingerprint(state),
        locked_layer=locked,
        is_xref=xref,
    ), entity


def _plot_box_evidence(doc: Any, handle: str) -> tuple[LivePlotBoxEvidence, Any]:
    pair = _entities(doc).get(handle.casefold())
    if pair is None:
        raise ValueError(f"Batch 30 plot box does not exist: {handle}")
    entity, owner = pair
    layer = str(entity.Layer)
    if not layer.casefold().startswith("plot_box"):
        raise ValueError(f"Batch 30 PBD source is not on a PLOT_BOX* layer: {handle}")
    locked = bool(doc.Layers.Item(layer).Lock)
    xref = "|" in layer
    if locked or xref:
        raise ValueError(f"Batch 30 plot box is locked or xref-dependent: {handle}")
    state = {"handle": str(entity.Handle), "object_name": str(entity.ObjectName), "owner": owner, "layer": layer}
    return LivePlotBoxEvidence(
        **state,
        state_fingerprint=_fingerprint(state),
        locked_layer=locked,
        is_xref=xref,
    ), entity


def _plan(request: Any) -> Any:
    planners = {
        ViewportRotateRequest: plan_viewport_rotate,
        LayoutToDrawingsRequest: plan_layout_to_drawings,
        DrawingBackupRequest: plan_drawing_backup,
        CorrectErrorRequest: plan_correct_error,
        InsertBlocksRequest: plan_insert_blocks,
        MultiFileOrganizeRequest: plan_multi_file_organize,
        PlotBoxCreateRequest: plan_plot_box_create,
        DeletePlotBoxesRequest: plan_delete_plot_boxes,
        PlotBoxMultiMakeRequest: plan_plot_box_multi_make,
        AutoPlotRequest: plan_auto_plot,
    }
    if isinstance(request, AllViewportUnlockRequest):
        return plan_all_viewports_unlock(request)
    if isinstance(request, ViewportUnlockRequest):
        return plan_viewport_unlock(request)
    for request_type, planner in planners.items():
        if isinstance(request, request_type):
            return planner(request)
    raise TypeError(f"unsupported Batch 30 request: {type(request).__name__}")


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
    result = {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "live_executable": False,
        "blocked_reason": BLOCKED[plan.command_alias],
    }
    if plan.command_alias in HELP_URLS:
        result["official_help_url"] = HELP_URLS[plan.command_alias]
    return result


def _snapshot_matches(evidence: LiveViewportEvidence, snapshot: ViewportState) -> bool:
    return (
        evidence.handle.casefold() == snapshot.entity.handle.casefold()
        and evidence.object_name.casefold() == snapshot.entity.entity_type.casefold()
        and evidence.owner.casefold() == snapshot.layout_name.casefold()
        and evidence.center == snapshot.center
        and evidence.width == snapshot.width
        and evidence.height == snapshot.height
        and evidence.view_twist_radians == snapshot.view_twist_radians
        and evidence.display_locked == snapshot.display_locked
        and (evidence.viewport_number == 1) == snapshot.is_paper_viewport
    )


def _validate_unlock_results(request: ViewportUnlockRequest) -> None:
    sources = {item.entity.handle.casefold(): item for item in request.viewports}
    for result in request.exact_results:
        source = sources[result.source_handle.casefold()]
        target = result.exact_viewport
        if (
            target.entity.handle.casefold() != source.entity.handle.casefold()
            or target.entity.entity_type.casefold() != source.entity.entity_type.casefold()
            or target.layout_name.casefold() != source.layout_name.casefold()
            or target.layout_revision != source.layout_revision
            or target.center != source.center
            or target.width != source.width
            or target.height != source.height
            or target.view_twist_radians != source.view_twist_radians
            or target.is_paper_viewport != source.is_paper_viewport
            or target.display_locked
        ):
            raise ValueError("Batch 30 viewport unlock may change only DisplayLocked to false")


def _viewport_handles_in_layout(doc: Any, layout_name: str) -> set[str]:
    return {
        str(entity.Handle).casefold()
        for entity, owner in _entities(doc).values()
        if owner.casefold() == layout_name.casefold()
        and str(entity.ObjectName).casefold() == "acdbviewport"
        and getattr(entity, "Number", None) != 1
    }


def _unlock_payload(request: ViewportUnlockRequest, plan: Any, sources: tuple[LiveViewportEvidence, ...]) -> dict[str, Any]:
    return {
        "command_alias": plan.command_alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
    }


def _preview_unlock(request: ViewportUnlockRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _plan(request)
    _validate_unlock_results(request)
    doc = _drawing(request.document_id)
    sources = tuple(_viewport_evidence(doc, item.entity.handle)[0] for item in request.viewports)
    for evidence, snapshot in zip(sources, request.viewports, strict=True):
        if not _snapshot_matches(evidence, snapshot):
            raise ValueError(f"Batch 30 viewport does not match snapshot: {snapshot.entity.handle}")
    if not any(item.display_locked for item in sources):
        raise ValueError("Batch 30 viewport unlock requires at least one locked viewport")
    if isinstance(request, AllViewportUnlockRequest):
        actual = _viewport_handles_in_layout(doc, request.layout_name)
        declared = {handle.casefold() for handle in request.complete_viewport_handles}
        if actual != declared:
            raise ValueError("Batch 30 VUU declared scope is not the complete live layout viewport set")
    payload = _unlock_payload(request, plan, sources)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "only DisplayLocked=true-to-false is permitted; geometry, twist, layout, identity, and complete VUU scope are stale-checked",
    }


def preview_live_vu(request: ViewportUnlockRequest) -> dict[str, Any]:
    return _preview_unlock(request)


def preview_live_vuu(request: AllViewportUnlockRequest) -> dict[str, Any]:
    return _preview_unlock(request)


def _execute_unlock(
    request: ViewportUnlockRequest,
    expected_sources: tuple[LiveViewportEvidence, ...],
    approval_fingerprint: str,
) -> LiveBatch30Result:
    plan = _plan(request)
    _validate_unlock_results(request)
    payload = _unlock_payload(request, plan, expected_sources)
    if approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 30 viewport-unlock preview")
    doc = _drawing(request.document_id)
    current_pairs = tuple(_viewport_evidence(doc, item.entity.handle) for item in request.viewports)
    current = tuple(item[0] for item in current_pairs)
    if current != expected_sources:
        raise ValueError("Batch 30 viewport state no longer matches the approved preview")
    if isinstance(request, AllViewportUnlockRequest):
        actual = _viewport_handles_in_layout(doc, request.layout_name)
        declared = {handle.casefold() for handle in request.complete_viewport_handles}
        if actual != declared:
            raise ValueError("Batch 30 VUU live layout scope changed after approval")
    changed = tuple(item.handle for item in current if item.display_locked)
    if not changed:
        raise ValueError("Batch 30 viewport unlock requires at least one locked viewport")
    entities = {evidence.handle.casefold(): entity for evidence, entity in current_pairs}
    doc.StartUndoMark()
    try:
        for result in request.exact_results:
            entities[result.source_handle.casefold()].DisplayLocked = False
    finally:
        doc.EndUndoMark()
    for result in request.exact_results:
        evidence, _ = _viewport_evidence(doc, result.source_handle)
        if evidence.display_locked or not _snapshot_matches(evidence, result.exact_viewport):
            raise RuntimeError(f"{plan.command_alias} postcondition failed for viewport: {result.source_handle}")
    return LiveBatch30Result(
        document_name=str(doc.Name),
        command_alias=plan.command_alias,
        changed_handles=changed,
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def execute_live_vu(request: LiveVUExecuteRequest) -> LiveBatch30Result:
    return _execute_unlock(request.request, request.expected_sources, request.approval_fingerprint)


def execute_live_vuu(request: LiveVUUExecuteRequest) -> LiveBatch30Result:
    return _execute_unlock(request.request, request.expected_sources, request.approval_fingerprint)


def _plot_boxes_in_owner(doc: Any, owner: str) -> dict[str, tuple[Any, str]]:
    return {
        handle: pair
        for handle, pair in _entities(doc).items()
        if pair[1].casefold() == owner.casefold()
        and str(pair[0].Layer).casefold().startswith("plot_box")
    }


def _validate_pbd_snapshot(evidence: LivePlotBoxEvidence, snapshot: VersionedEntitySnapshot) -> bool:
    return (
        evidence.handle.casefold() == snapshot.handle.casefold()
        and evidence.object_name.casefold() == snapshot.entity_type.casefold()
        and evidence.owner.casefold() == snapshot.owner.casefold()
        and evidence.layer.casefold() == snapshot.layer.casefold()
    )


def _pbd_payload(request: DeletePlotBoxesRequest, plan: Any, sources: tuple[LivePlotBoxEvidence, ...]) -> dict[str, Any]:
    return {
        "command_alias": "PBD",
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
    }


def preview_live_pbd(request: DeletePlotBoxesRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = plan_delete_plot_boxes(request)
    doc = _drawing(request.document_id)
    actual = _plot_boxes_in_owner(doc, request.owner)
    declared = {item.casefold() for item in request.complete_plot_box_handles}
    if set(actual) != declared:
        raise ValueError("Batch 30 PBD declared scope is not the complete live owner PLOT_BOX* set")
    snapshots = {item.handle.casefold(): item for item in request.plot_boxes}
    sources = tuple(_plot_box_evidence(doc, handle)[0] for handle in request.complete_plot_box_handles)
    for evidence in sources:
        if not _validate_pbd_snapshot(evidence, snapshots[evidence.handle.casefold()]):
            raise ValueError(f"Batch 30 PBD entity does not match snapshot: {evidence.handle}")
    payload = _pbd_payload(request, plan, sources)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "official_help_url": HELP_URLS["PBD"],
        "scope_note": "official-help deletion is restricted to the complete owner-scoped PLOT_BOX* set with stale, layer-lock, xref, Undo, and empty-scope postcondition checks",
    }


def execute_live_pbd(request: LivePBDExecuteRequest) -> LiveBatch30Result:
    plan = plan_delete_plot_boxes(request.request)
    payload = _pbd_payload(request.request, plan, request.expected_sources)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 30 PBD preview")
    doc = _drawing(request.request.document_id)
    actual = _plot_boxes_in_owner(doc, request.request.owner)
    declared = {item.casefold() for item in request.request.complete_plot_box_handles}
    if set(actual) != declared:
        raise ValueError("Batch 30 PBD live owner scope changed after approval")
    current_pairs = tuple(_plot_box_evidence(doc, item.handle) for item in request.expected_sources)
    current = tuple(item[0] for item in current_pairs)
    if current != request.expected_sources:
        raise ValueError("Batch 30 PBD entity state no longer matches the approved preview")
    doc.StartUndoMark()
    try:
        for _, entity in current_pairs:
            entity.Delete()
    finally:
        doc.EndUndoMark()
    if _plot_boxes_in_owner(doc, request.request.owner):
        raise RuntimeError("PBD postcondition failed: owner still contains PLOT_BOX* entities")
    return LiveBatch30Result(
        document_name=str(doc.Name),
        command_alias="PBD",
        changed_handles=tuple(item.handle for item in request.expected_sources),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def preview_live_vr(request: ViewportRotateRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_vsd(request: LayoutToDrawingsRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_bak(request: DrawingBackupRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_cer(request: CorrectErrorRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_ib(request: InsertBlocksRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_msl(request: MultiFileOrganizeRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_pb(request: PlotBoxCreateRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_pbm(request: PlotBoxMultiMakeRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_ppp(request: AutoPlotRequest) -> dict[str, Any]: return _preview_blocked(request)


def register_live_batch30_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(title="Preview live xiCAD Batch 30 operation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    execute = ToolAnnotations(title="Execute live xiCAD Batch 30 operation", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
    functions = {
        "vr": preview_live_vr, "vsd": preview_live_vsd, "vu": preview_live_vu,
        "vuu": preview_live_vuu, "bak": preview_live_bak, "cer": preview_live_cer,
        "ib": preview_live_ib, "msl": preview_live_msl, "pb": preview_live_pb,
        "pbd": preview_live_pbd, "pbm": preview_live_pbm, "ppp": preview_live_ppp,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
    mcp.tool(name="xicad_execute_live_vu", annotations=execute)(execute_live_vu)
    mcp.tool(name="xicad_execute_live_vuu", annotations=execute)(execute_live_vuu)
    mcp.tool(name="xicad_execute_live_pbd", annotations=execute)(execute_live_pbd)
