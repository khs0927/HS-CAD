from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch14 import GeometrySnapshot
from .headless_core_batch15 import (
    ContentKind,
    ContentSnapshot,
    CopyContentsRequest,
    DateStampRequest,
    FlattenRequest,
    plan_copy_contents,
    plan_date_stamp,
    plan_flatten,
)


class LiveContentEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    snapshot: ContentSnapshot
    object_name: str
    layer: str


class LiveLayerEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    locked: bool
    is_xref: bool


class LiveCtExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: CopyContentsRequest
    expected_contents: tuple[LiveContentEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveDtsExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: DateStampRequest
    expected_layer: LiveLayerEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveGeometryEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    snapshot: GeometrySnapshot
    object_name: str
    layer: str


class LiveFltExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: FlattenRequest
    expected_geometry: tuple[LiveGeometryEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch15aResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...] = ()
    changed_handles: tuple[str, ...] = ()
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


def _entities(doc: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for block in doc.Blocks:
        if bool(block.IsLayout):
            for entity in block:
                result[str(entity.Handle).casefold()] = entity
    return result


def _content(doc: Any, handle: str, kind: ContentKind) -> tuple[LiveContentEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"CT entity does not exist: {handle}")
    layer = str(entity.Layer)
    locked = bool(doc.Layers.Item(layer).Lock)
    xref = "|" in layer
    name = str(entity.ObjectName)
    if kind is ContentKind.TEXT:
        if not hasattr(entity, "TextString"):
            raise ValueError(f"CT text content is unavailable: {handle}")
        value: str | float = str(entity.TextString)
    elif kind is ContentKind.POLYLINE_WIDTH:
        if name.casefold() not in {"acdbpolyline", "acdblwpolyline"} or not hasattr(entity, "ConstantWidth"):
            raise ValueError(f"CT polyline width is unavailable: {handle}")
        value = float(entity.ConstantWidth)
    else:
        raise ValueError("live CT supports only exact text-content or polyline-width copy; circle/block replacement is blocked")
    if locked or xref:
        raise ValueError(f"CT entity is locked or xref-dependent: {handle}")
    return LiveContentEvidence(
        snapshot=ContentSnapshot(handle=str(entity.Handle), kind=kind, value=value, locked_layer=locked, is_xref=xref),
        object_name=name,
        layer=layer,
    ), entity


def _layer(doc: Any, name: str) -> LiveLayerEvidence:
    try:
        layer = doc.Layers.Item(name)
    except Exception as exc:
        raise ValueError(f"DTS layer does not exist: {name}") from exc
    actual = str(layer.Name)
    evidence = LiveLayerEvidence(name=actual, locked=bool(layer.Lock), is_xref="|" in actual)
    if evidence.locked or evidence.is_xref:
        raise ValueError(f"DTS layer is locked or xref-dependent: {name}")
    return evidence


def _point(value: Any) -> Point3D:
    xyz = tuple(float(item) for item in value)
    return Point3D(x=xyz[0], y=xyz[1], z=xyz[2])


def _line_geometry(doc: Any, handle: str) -> tuple[LiveGeometryEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None or str(entity.ObjectName).casefold() != "acdbline":
        raise ValueError(f"live FLT currently supports exact AcDbLine geometry only: {handle}")
    layer = str(entity.Layer)
    locked = bool(doc.Layers.Item(layer).Lock)
    xref = "|" in layer
    if locked or xref:
        raise ValueError(f"FLT entity is locked or xref-dependent: {handle}")
    snapshot = GeometrySnapshot(
        handle=str(entity.Handle), entity_type="LINE", vertices=(_point(entity.StartPoint), _point(entity.EndPoint)),
        layer=layer, locked_layer=locked, is_xref=xref,
    )
    return LiveGeometryEvidence(snapshot=snapshot, object_name=str(entity.ObjectName), layer=layer), entity


def _ct_payload(request: CopyContentsRequest, contents: tuple[LiveContentEvidence, ...]) -> dict[str, Any]:
    return {
        "command_alias": "CT",
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "expected_contents": [item.model_dump(mode="json") for item in contents],
    }


def preview_live_ct(request: CopyContentsRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    doc = _drawing(request.document_id)
    handles = (request.source_handle,) + request.target_handles
    pairs = tuple(_content(doc, handle, request.expected_kind) for handle in handles)
    contents = tuple(pair[0] for pair in pairs)
    plan = plan_copy_contents(request, tuple(item.snapshot for item in contents))
    payload = _ct_payload(request, contents)
    return {
        **payload,
        "plan": plan.model_dump(mode="json"),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "exact text or LWPOLYLINE constant-width copy only; optional legacy property-copy and circle/block replacement are excluded",
    }


def execute_live_ct(request: LiveCtExecuteRequest) -> LiveBatch15aResult:
    payload = _ct_payload(request.request, request.expected_contents)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match CT preview")
    doc = _drawing(request.request.document_id)
    handles = (request.request.source_handle,) + request.request.target_handles
    pairs = tuple(_content(doc, handle, request.request.expected_kind) for handle in handles)
    if tuple(pair[0] for pair in pairs) != request.expected_contents:
        raise ValueError("CT content state no longer matches approved preview")
    plan = plan_copy_contents(request.request, tuple(item.snapshot for item in request.expected_contents))
    targets = {str(entity.Handle).casefold(): entity for _, entity in pairs[1:]}
    doc.StartUndoMark()
    try:
        for handle, value in plan.changes.items():
            entity = targets[handle.casefold()]
            if request.request.expected_kind is ContentKind.TEXT:
                entity.TextString = value
            else:
                entity.ConstantWidth = value
    finally:
        doc.EndUndoMark()
    for handle, value in plan.changes.items():
        entity = targets[handle.casefold()]
        actual = entity.TextString if request.request.expected_kind is ContentKind.TEXT else entity.ConstantWidth
        if actual != value:
            raise RuntimeError(f"CT postcondition failed: {handle}")
    return LiveBatch15aResult(
        document_name=str(doc.Name), command_alias="CT", changed_handles=tuple(plan.changes),
        undo_mark_opened=True, undo_mark_closed=True, postcondition_verified=True,
    )


def _dts_payload(request: DateStampRequest, layer: LiveLayerEvidence) -> dict[str, Any]:
    return {
        "command_alias": "DTS",
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "expected_layer": layer.model_dump(mode="json"),
    }


def preview_live_dts(request: DateStampRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    doc = _drawing(request.document_id)
    layer = _layer(doc, request.layer)
    try:
        doc.TextStyles.Item(request.text_style)
    except Exception as exc:
        raise ValueError(f"DTS text style does not exist: {request.text_style}") from exc
    plan = plan_date_stamp(request)
    payload = _dts_payload(request, layer)
    return {
        **payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _fingerprint(payload),
        "mutation": True, "live_executable": True,
    }


def _variant(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])


def execute_live_dts(request: LiveDtsExecuteRequest) -> LiveBatch15aResult:
    payload = _dts_payload(request.request, request.expected_layer)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match DTS preview")
    doc = _drawing(request.request.document_id)
    if _layer(doc, request.expected_layer.name) != request.expected_layer:
        raise ValueError("DTS layer state no longer matches approved preview")
    try:
        doc.TextStyles.Item(request.request.text_style)
    except Exception as exc:
        raise ValueError(f"DTS text style does not exist: {request.request.text_style}") from exc
    plan = plan_date_stamp(request.request)
    spec = plan.create
    doc.StartUndoMark()
    try:
        entity = doc.ModelSpace.AddText(spec.text, _variant(spec.insertion_point), spec.height)
        entity.Layer = spec.layer
        entity.StyleName = spec.style
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    if (
        str(entity.Handle).casefold() not in available
        or str(entity.TextString) != spec.text
        or str(entity.Layer).casefold() != spec.layer.casefold()
        or str(entity.StyleName).casefold() != spec.style.casefold()
        or float(entity.Height) != spec.height
    ):
        raise RuntimeError("DTS postcondition failed")
    return LiveBatch15aResult(
        document_name=str(doc.Name), command_alias="DTS", created_handles=(str(entity.Handle),),
        undo_mark_opened=True, undo_mark_closed=True, postcondition_verified=True,
    )


def _flt_payload(request: FlattenRequest, geometry: tuple[LiveGeometryEvidence, ...]) -> dict[str, Any]:
    return {
        "command_alias": "FLT", "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "expected_geometry": [item.model_dump(mode="json") for item in geometry],
    }


def preview_live_flt(request: FlattenRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    doc = _drawing(request.document_id)
    pairs = tuple(_line_geometry(doc, handle) for handle in request.target_handles)
    geometry = tuple(pair[0] for pair in pairs)
    plan = plan_flatten(request, tuple(item.snapshot for item in geometry))
    payload = _flt_payload(request, geometry)
    return {
        **payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _fingerprint(payload),
        "mutation": True, "live_executable": True,
        "scope_note": "exact AcDbLine endpoint flattening only; unsupported 3D solids/surfaces and implicit deletion are excluded",
    }


def execute_live_flt(request: LiveFltExecuteRequest) -> LiveBatch15aResult:
    payload = _flt_payload(request.request, request.expected_geometry)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match FLT preview")
    doc = _drawing(request.request.document_id)
    pairs = tuple(_line_geometry(doc, handle) for handle in request.request.target_handles)
    if tuple(pair[0] for pair in pairs) != request.expected_geometry:
        raise ValueError("FLT geometry state no longer matches approved preview")
    plan = plan_flatten(request.request, tuple(item.snapshot for item in request.expected_geometry))
    objects = {str(entity.Handle).casefold(): entity for _, entity in pairs}
    doc.StartUndoMark()
    try:
        for handle, vertices in plan.target_vertices.items():
            entity = objects[handle.casefold()]
            entity.StartPoint = _variant(vertices[0])
            entity.EndPoint = _variant(vertices[1])
    finally:
        doc.EndUndoMark()
    for handle, vertices in plan.target_vertices.items():
        entity = objects[handle.casefold()]
        if (_point(entity.StartPoint), _point(entity.EndPoint)) != vertices:
            raise RuntimeError(f"FLT postcondition failed: {handle}")
    return LiveBatch15aResult(
        document_name=str(doc.Name), command_alias="FLT", changed_handles=tuple(plan.target_vertices),
        undo_mark_opened=True, undo_mark_closed=True, postcondition_verified=True,
    )


def register_live_batch15a_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(title="Preview live xiCAD Batch 15A operation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    execute = ToolAnnotations(title="Execute live xiCAD Batch 15A operation", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
    for name, function, tool_annotations in (
        ("xicad_preview_live_ct", preview_live_ct, preview),
        ("xicad_execute_live_ct", execute_live_ct, execute),
        ("xicad_preview_live_dts", preview_live_dts, preview),
        ("xicad_execute_live_dts", execute_live_dts, execute),
        ("xicad_preview_live_flt", preview_live_flt, preview),
        ("xicad_execute_live_flt", execute_live_flt, execute),
    ):
        mcp.tool(name=name, annotations=tool_annotations)(function)
