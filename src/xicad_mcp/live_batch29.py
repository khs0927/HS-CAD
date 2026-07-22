"""Truthful ZWCAD live previews and evidence-bounded Batch 29 viewport locks."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch29a import (
    PaperToModelRequest,
    RemoveBindPrefixRequest,
    ResetXrefLayersRequest,
    WindowSymbolRequest,
    XclipExplodeRequest,
    XrefColorRequest,
    plan_paper_to_model,
    plan_remove_bind_prefix,
    plan_reset_xref_layers,
    plan_window_symbols,
    plan_xclip_explode,
    plan_xref_color,
)
from .headless_core_batch29b import (
    AllViewportLockRequest,
    ViewportAlignRequest,
    ViewportGuideLineRequest,
    ViewportLayerPropertyRequest,
    ViewportLockRequest,
    ViewportMakeObjectRequest,
    ViewportSnapshot,
    plan_all_viewports_lock,
    plan_viewport_align,
    plan_viewport_guide_line,
    plan_viewport_layer_property,
    plan_viewport_lock,
    plan_viewport_make_object,
)

HELP_URLS = {
    "RBP": "https://izzarder.com/335",
    "XCX": "https://izzarder.com/472",
    "XRC": "https://izzarder.com/376",
    "XRR": "https://izzarder.com/278",
    "P2M": "https://izzarder.com/256",
    "VMO": "https://izzarder.com/257",
    "VPP": "https://izzarder.com/486",
}

BLOCKED = {
    "RBP": "symbol-table merge/collision/reference rewrite and nested-definition transactions are unrecovered",
    "WSL": "symbol geometry, attribute discovery/order, numbering propagation, and placement are unrecovered",
    "XCX": "clip-boundary transforms, trimming topology, hatch/block policy, xref binding, and rollback are unrecovered",
    "XRC": "xref traversal, restore-state storage, nested overrides, wildcard filtering, and reload behavior are unrecovered",
    "XRR": "selected reset fields, VISRETAIN/reload behavior, nesting, and override precedence are unrecovered",
    "P2M": "ExportLayout/ChSpace choice, multi-layout file I/O, transforms, xref binding, and scale policy are unrecovered",
    "VA": "alignment anchor, center/edge policy, and viewport view transformation are unrecovered",
    "VGL": "paper-to-model transform, clipping geometry, entity type, layer, and properties are unrecovered",
    "VMO": "layout/paper setup, boundary transform, viewport view target, scale, and clipping semantics are unrecovered",
    "VPP": "VPLAYER scope, copy/paste state, freeze/thaw/invert rules, and version-specific properties are unrecovered",
}


class LiveViewportEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    handle: str
    object_name: str
    layer: str
    layout_name: str
    center: Point3D
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    display_locked: bool
    viewport_number: int | None
    state_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    locked_layer: bool
    is_xref: bool


class LiveVLExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ViewportLockRequest
    expected_sources: tuple[LiveViewportEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveVLLExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: AllViewportLockRequest
    expected_sources: tuple[LiveViewportEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch29Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


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
        layout_name = str(block.Layout.Name)
        for entity in block:
            entities[str(entity.Handle).casefold()] = entity, layout_name
    return entities


def _point(value: Any) -> Point3D:
    coordinates = tuple(float(item) for item in value)
    return Point3D(
        x=coordinates[0],
        y=coordinates[1],
        z=coordinates[2] if len(coordinates) > 2 else 0.0,
    )


def _viewport_evidence(doc: Any, handle: str) -> tuple[LiveViewportEvidence, Any]:
    pair = _entities(doc).get(handle.casefold())
    if pair is None:
        raise ValueError(f"Batch 29 viewport does not exist: {handle}")
    entity, layout_name = pair
    object_name = str(entity.ObjectName)
    if object_name.casefold() != "acdbviewport":
        raise ValueError(f"Batch 29 source is not a viewport: {handle}")
    layer = str(entity.Layer)
    locked = bool(doc.Layers.Item(layer).Lock)
    xref = "|" in layer
    if locked or xref:
        raise ValueError(f"Batch 29 viewport is locked or xref-dependent: {handle}")
    try:
        viewport_number: int | None = int(entity.Number)
    except Exception:
        viewport_number = None
    state = {
        "handle": str(entity.Handle),
        "object_name": object_name,
        "layer": layer,
        "layout_name": layout_name,
        "center": _point(entity.Center).model_dump(mode="json"),
        "width": float(entity.Width),
        "height": float(entity.Height),
        "display_locked": bool(entity.DisplayLocked),
        "viewport_number": viewport_number,
    }
    return (
        LiveViewportEvidence(
            **state,
            state_fingerprint=_fingerprint(state),
            locked_layer=locked,
            is_xref=xref,
        ),
        entity,
    )


def _plan(request: Any) -> Any:
    planners = {
        RemoveBindPrefixRequest: plan_remove_bind_prefix,
        WindowSymbolRequest: plan_window_symbols,
        XclipExplodeRequest: plan_xclip_explode,
        XrefColorRequest: plan_xref_color,
        ResetXrefLayersRequest: plan_reset_xref_layers,
        PaperToModelRequest: plan_paper_to_model,
        ViewportAlignRequest: plan_viewport_align,
        ViewportGuideLineRequest: plan_viewport_guide_line,
        ViewportMakeObjectRequest: plan_viewport_make_object,
        ViewportLayerPropertyRequest: plan_viewport_layer_property,
    }
    # AllViewportLockRequest is a ViewportLockRequest subclass, so order matters.
    if isinstance(request, AllViewportLockRequest):
        return plan_all_viewports_lock(request)
    if isinstance(request, ViewportLockRequest):
        return plan_viewport_lock(request)
    for request_type, planner in planners.items():
        if isinstance(request, request_type):
            return planner(request)
    raise TypeError(f"unsupported Batch 29 request: {type(request).__name__}")


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


def _validate_lock_results(request: ViewportLockRequest) -> None:
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
            or target.is_paper_viewport != source.is_paper_viewport
            or not target.display_locked
        ):
            raise ValueError("Batch 29 viewport lock may change only DisplayLocked to true")


def _snapshot_matches(evidence: LiveViewportEvidence, snapshot: ViewportSnapshot) -> bool:
    return (
        evidence.handle.casefold() == snapshot.entity.handle.casefold()
        and evidence.object_name.casefold() == snapshot.entity.entity_type.casefold()
        and evidence.layout_name.casefold() == snapshot.layout_name.casefold()
        and evidence.center == snapshot.center
        and evidence.width == snapshot.width
        and evidence.height == snapshot.height
        and evidence.display_locked == snapshot.display_locked
        and (evidence.viewport_number == 1) == snapshot.is_paper_viewport
    )


def _viewport_handles_in_layout(doc: Any, layout_name: str) -> set[str]:
    return {
        str(entity.Handle).casefold()
        for entity, actual_layout in _entities(doc).values()
        if actual_layout.casefold() == layout_name.casefold()
        and str(entity.ObjectName).casefold() == "acdbviewport"
        and getattr(entity, "Number", None) != 1
    }


def _lock_payload(request: ViewportLockRequest, plan: Any, sources: tuple[LiveViewportEvidence, ...]) -> dict[str, Any]:
    return {
        "command_alias": plan.command_alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
    }


def _preview_lock(request: ViewportLockRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _plan(request)
    _validate_lock_results(request)
    doc = _drawing(request.document_id)
    sources = tuple(_viewport_evidence(doc, item.entity.handle)[0] for item in request.viewports)
    for evidence, snapshot in zip(sources, request.viewports, strict=True):
        if not _snapshot_matches(evidence, snapshot):
            raise ValueError(f"Batch 29 viewport does not match snapshot: {snapshot.entity.handle}")
    if isinstance(request, AllViewportLockRequest):
        actual = _viewport_handles_in_layout(doc, request.layout_name)
        declared = {handle.casefold() for handle in request.complete_viewport_handles}
        if actual != declared:
            raise ValueError("Batch 29 VLL declared scope is not the complete live layout viewport set")
    payload = _lock_payload(request, plan, sources)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "only DisplayLocked=false-to-true is permitted; geometry, layout, and entity identity are stale-checked and full legacy equivalence is not claimed",
    }


def preview_live_vl(request: ViewportLockRequest) -> dict[str, Any]:
    return _preview_lock(request)


def preview_live_vll(request: AllViewportLockRequest) -> dict[str, Any]:
    return _preview_lock(request)


def _execute_lock(
    request: ViewportLockRequest,
    expected_sources: tuple[LiveViewportEvidence, ...],
    approval_fingerprint: str,
) -> LiveBatch29Result:
    plan = _plan(request)
    _validate_lock_results(request)
    payload = _lock_payload(request, plan, expected_sources)
    if approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 29 viewport-lock preview")
    doc = _drawing(request.document_id)
    current_pairs = tuple(_viewport_evidence(doc, item.entity.handle) for item in request.viewports)
    current = tuple(item[0] for item in current_pairs)
    if current != expected_sources:
        raise ValueError("Batch 29 viewport state no longer matches the approved preview")
    if isinstance(request, AllViewportLockRequest):
        actual = _viewport_handles_in_layout(doc, request.layout_name)
        declared = {handle.casefold() for handle in request.complete_viewport_handles}
        if actual != declared:
            raise ValueError("Batch 29 VLL live layout scope changed after approval")

    entities = {evidence.handle.casefold(): entity for evidence, entity in current_pairs}
    doc.StartUndoMark()
    try:
        for result in request.exact_results:
            entities[result.source_handle.casefold()].DisplayLocked = True
    finally:
        doc.EndUndoMark()

    for result in request.exact_results:
        evidence, _ = _viewport_evidence(doc, result.source_handle)
        target = result.exact_viewport
        if (
            not evidence.display_locked
            or evidence.handle.casefold() != target.entity.handle.casefold()
            or evidence.layout_name.casefold() != target.layout_name.casefold()
            or evidence.center != target.center
            or evidence.width != target.width
            or evidence.height != target.height
        ):
            raise RuntimeError(f"{plan.command_alias} postcondition failed for viewport: {result.source_handle}")
    return LiveBatch29Result(
        document_name=str(doc.Name),
        command_alias=plan.command_alias,
        changed_handles=tuple(item.source_handle for item in request.exact_results),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def execute_live_vl(request: LiveVLExecuteRequest) -> LiveBatch29Result:
    return _execute_lock(request.request, request.expected_sources, request.approval_fingerprint)


def execute_live_vll(request: LiveVLLExecuteRequest) -> LiveBatch29Result:
    return _execute_lock(request.request, request.expected_sources, request.approval_fingerprint)


def preview_live_rbp(request: RemoveBindPrefixRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_wsl(request: WindowSymbolRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_xcx(request: XclipExplodeRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_xrc(request: XrefColorRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_xrr(request: ResetXrefLayersRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_p2m(request: PaperToModelRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_va(request: ViewportAlignRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_vgl(request: ViewportGuideLineRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_vmo(request: ViewportMakeObjectRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_vpp(request: ViewportLayerPropertyRequest) -> dict[str, Any]: return _preview_blocked(request)


def register_live_batch29_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(title="Preview live xiCAD Batch 29 operation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    execute = ToolAnnotations(title="Execute live xiCAD Batch 29 operation", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
    functions = {
        "rbp": preview_live_rbp, "wsl": preview_live_wsl, "xcx": preview_live_xcx,
        "xrc": preview_live_xrc, "xrr": preview_live_xrr, "p2m": preview_live_p2m,
        "va": preview_live_va, "vgl": preview_live_vgl, "vl": preview_live_vl,
        "vll": preview_live_vll, "vmo": preview_live_vmo, "vpp": preview_live_vpp,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
    mcp.tool(name="xicad_execute_live_vl", annotations=execute)(execute_live_vl)
    mcp.tool(name="xicad_execute_live_vll", annotations=execute)(execute_live_vll)
