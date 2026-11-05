"""Truthful Batch 32 previews and an evidence-bounded RR rotation adapter."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch32 import (
    BlockLibraryRequest,
    BreakMultiRequest,
    CenterlineRequest,
    EndConnectRequest,
    FilletLRequest,
    MaskRequest,
    ObjectInfoRequest,
    OffsetCloseRequest,
    Point3D,
    ReferenceRotateRequest,
    ScaleListDeleteRequest,
    XSymbolRequest,
    plan_block_library,
    plan_break_multi,
    plan_centerline,
    plan_end_connect,
    plan_fillet_l,
    plan_mask,
    plan_object_info,
    plan_offset_close,
    plan_reference_rotate,
    plan_scale_list_delete,
    plan_x_symbol,
)

HELP_URLS = {
    "CE": "https://izzarder.com/201",
    "BBB": "https://izzarder.com/411",
    "FF": "https://izzarder.com/363",
    "WQ": "https://izzarder.com/417",
    "WE": "https://izzarder.com/526",
    "XX": "https://izzarder.com/185",
    "Q11": "https://izzarder.com/166",
    "MK": "https://izzarder.com/585",
    "RR": "https://izzarder.com/114",
    "LII": "https://izzarder.com/246",
    "SLD": None,
}

BLOCKED = {
    "CE": "pairing, nested traversal, center geometry, and exact output properties remain compiled",
    "BBB": "curve projection, split topology, tolerance, and replacement ordering remain compiled",
    "FF": "wall and centerline classification plus zero-radius cleanup topology remain compiled",
    "WQ": "offset side, joins, arc handling, end caps, and source-retention behavior remain compiled",
    "WE": "endpoint discovery, parallel tolerance, conflict pairing, and duplicate cleanup remain compiled",
    "XX": "the help image does not define acquisition order, diagonal geometry, scale, or properties",
    "Q11": "block-library insertion and file mutations require filesystem/resource transaction recovery",
    "MK": "ActiveX guarantees BackgroundFill but not the documented configurable color/width as portable COM properties",
    "LII": "nested traversal and ByBlock/ByLayer property resolution remain compiled; this is report-only, not mutation",
    "SLD": "the shortcut evidence explicitly marks ZWCAD unsupported and no official command article was found",
}

_ROTATABLE_OBJECTS = {"acdbtext", "acdbmtext", "acdbblockreference"}


class LiveRREntityEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    handle: str
    object_name: str
    layer: str
    insertion_point: Point3D
    rotation_radians: float
    state_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveRRExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ReferenceRotateRequest
    expected_sources: tuple[LiveRREntityEvidence, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveRRResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    document_name: str
    command_alias: str = "RR"
    changed_handles: tuple[str, ...]
    rotation_delta_radians: float
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


def _point(value: Any) -> Point3D:
    coordinates = tuple(float(item) for item in value)
    return Point3D(x=coordinates[0], y=coordinates[1], z=coordinates[2] if len(coordinates) > 2 else 0.0)


def _entity(doc: Any, handle: str) -> Any:
    try:
        return doc.HandleToObject(handle)
    except Exception as error:
        raise ValueError(f"RR source handle {handle!r} is not present in the active document") from error


def _entity_type_matches(request_type: str, object_name: str) -> bool:
    requested = request_type.casefold().removeprefix("acdb")
    actual = object_name.casefold().removeprefix("acdb")
    return requested == actual or (requested == "block" and actual == "blockreference")


def _validate_layer_and_xref(doc: Any, entity: Any) -> None:
    layer = str(entity.Layer)
    if "|" in layer or bool(doc.Layers.Item(layer).Lock):
        raise ValueError("RR source layer is locked or xref-dependent")
    if str(entity.ObjectName).casefold() == "acdbblockreference":
        name = str(getattr(entity, "EffectiveName", entity.Name))
        if bool(doc.Blocks.Item(name).IsXRef):
            raise ValueError("RR does not mutate xref block references")


def _evidence(doc: Any, source: Any) -> LiveRREntityEvidence:
    entity = _entity(doc, source.handle)
    object_name = str(entity.ObjectName)
    if object_name.casefold() not in _ROTATABLE_OBJECTS:
        raise ValueError("RR live execution is limited to text, mtext, and non-xref block references")
    if not _entity_type_matches(source.entity_type, object_name):
        raise ValueError("RR live entity type does not match the approved source snapshot")
    _validate_layer_and_xref(doc, entity)
    state = {
        "handle": str(entity.Handle),
        "object_name": object_name,
        "layer": str(entity.Layer),
        "insertion_point": _point(entity.InsertionPoint).model_dump(mode="json"),
        "rotation_radians": float(entity.Rotation),
    }
    return LiveRREntityEvidence(**state, state_fingerprint=_fingerprint(state))


def _angle(start: Point3D, end: Point3D) -> float:
    return math.atan2(end.y - start.y, end.x - start.x)


def _delta(request: ReferenceRotateRequest) -> float:
    return _angle(request.destination_start, request.destination_end) - _angle(
        request.reference_start, request.reference_end
    )


def _rotate(point: Point3D, base: Point3D, angle: float) -> Point3D:
    cosine, sine = math.cos(angle), math.sin(angle)
    dx, dy = point.x - base.x, point.y - base.y
    return Point3D(
        x=base.x + dx * cosine - dy * sine,
        y=base.y + dx * sine + dy * cosine,
        z=point.z,
    )


def _rotation_base(entity: Any, base: Point3D) -> Any:
    """Return the typed SAFEARRAY required by real ZWCAD COM objects."""
    coordinates = (base.x, base.y, base.z)
    if not hasattr(entity, "_oleobj_"):
        return coordinates
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, coordinates)


def _same_angle(first: float, second: float, tolerance: float = 1e-9) -> bool:
    return abs(math.atan2(math.sin(first - second), math.cos(first - second))) <= tolerance


def _same_point(first: Point3D, second: Point3D, tolerance: float = 1e-8) -> bool:
    return all(
        math.isclose(a, b, rel_tol=0, abs_tol=tolerance)
        for a, b in ((first.x, second.x), (first.y, second.y), (first.z, second.z))
    )


def _validate_exact_changes(request: ReferenceRotateRequest, evidence: tuple[LiveRREntityEvidence, ...]) -> None:
    changes = request.exact_changes
    if changes.erased_handles:
        raise ValueError("RR exact atomic rotation cannot erase entities")
    results = {item.result_id.casefold(): item for item in changes.created_or_updated}
    if len(results) != len(evidence) or set(results) != {item.handle.casefold() for item in evidence}:
        raise ValueError("RR exact changes require one updated result per source handle")
    for item in evidence:
        result = results[item.handle.casefold()]
        if (
            not _entity_type_matches(result.entity_type, item.object_name)
            or result.layer.casefold() != item.layer.casefold()
        ):
            raise ValueError("RR exact rotation cannot change entity type or layer")


def _rr_payload(
    request: ReferenceRotateRequest,
    plan: Any,
    sources: tuple[LiveRREntityEvidence, ...],
) -> dict[str, Any]:
    return {
        "command_alias": "RR",
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
        "rotation_delta_radians": _delta(request),
    }


def preview_live_rr(request: ReferenceRotateRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = plan_reference_rotate(request)
    if _same_angle(_delta(request), 0.0):
        raise ValueError("RR live execution requires a non-zero reference rotation")
    doc = _drawing(request.document_id)
    sources = tuple(_evidence(doc, item) for item in request.sources)
    _validate_exact_changes(request, sources)
    payload = _rr_payload(request, plan, sources)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "official_help_url": HELP_URLS["RR"],
        "scope_note": "exact atomic reference rotation for top-level text, mtext, and non-xref block references",
    }


def execute_live_rr(request: LiveRRExecuteRequest) -> LiveRRResult:
    plan = plan_reference_rotate(request.request)
    payload = _rr_payload(request.request, plan, request.expected_sources)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 32 RR preview")
    doc = _drawing(request.request.document_id)
    current = tuple(_evidence(doc, item) for item in request.request.sources)
    if current != request.expected_sources:
        raise ValueError("Batch 32 RR source state no longer matches the approved preview")
    _validate_exact_changes(request.request, current)
    angle = _delta(request.request)
    base = request.request.base_point
    entities = tuple(_entity(doc, item.handle) for item in current)
    doc.StartUndoMark()
    closed = False
    changed: list[tuple[Any, LiveRREntityEvidence]] = []
    try:
        try:
            for entity, before in zip(entities, current, strict=True):
                entity.Rotate(_rotation_base(entity, base), angle)
                changed.append((entity, before))
            for entity, before in changed:
                expected_point = _rotate(before.insertion_point, base, angle)
                if not _same_point(_point(entity.InsertionPoint), expected_point) or not _same_angle(
                    float(entity.Rotation), before.rotation_radians + angle
                ):
                    raise RuntimeError("RR rotation postcondition failed")
        except Exception:
            for entity, _before in reversed(changed):
                entity.Rotate(_rotation_base(entity, base), -angle)
            raise
    finally:
        doc.EndUndoMark()
        closed = True
    return LiveRRResult(
        document_name=str(doc.Name),
        changed_handles=tuple(item.handle for item in current),
        rotation_delta_radians=angle,
        undo_mark_opened=True,
        undo_mark_closed=closed,
        postcondition_verified=True,
    )


_PLANNERS: dict[type[Any], Callable[[Any], Any]] = {
    CenterlineRequest: plan_centerline,
    BreakMultiRequest: plan_break_multi,
    FilletLRequest: plan_fillet_l,
    OffsetCloseRequest: plan_offset_close,
    EndConnectRequest: plan_end_connect,
    XSymbolRequest: plan_x_symbol,
    BlockLibraryRequest: plan_block_library,
    MaskRequest: plan_mask,
    ObjectInfoRequest: plan_object_info,
    ScaleListDeleteRequest: plan_scale_list_delete,
}


def _preview_blocked(request: Any) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _PLANNERS[type(request)](request)
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
        "official_help_url": HELP_URLS[plan.command_alias],
    }


def preview_live_ce(request: CenterlineRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_bbb(request: BreakMultiRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_ff(request: FilletLRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_wq(request: OffsetCloseRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_we(request: EndConnectRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_xx(request: XSymbolRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_q11(request: BlockLibraryRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_mk(request: MaskRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_lii(request: ObjectInfoRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_sld(request: ScaleListDeleteRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def register_live_batch32_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 32 operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 32 RR operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    functions = {
        "ce": preview_live_ce,
        "bbb": preview_live_bbb,
        "ff": preview_live_ff,
        "wq": preview_live_wq,
        "we": preview_live_we,
        "xx": preview_live_xx,
        "q11": preview_live_q11,
        "mk": preview_live_mk,
        "rr": preview_live_rr,
        "lii": preview_live_lii,
        "sld": preview_live_sld,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
    mcp.tool(name="xicad_execute_live_rr", annotations=execute)(execute_live_rr)
