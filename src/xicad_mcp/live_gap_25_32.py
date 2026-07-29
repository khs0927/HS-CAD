"""Help-verified live promotions for selected frozen xiCAD Batch 25-32 gaps.

The adapters in this module intentionally expose only COM-observable subsets:

* TX: rectangular polyline borders, without masking or grouping.
* BRN: collision-free rename of static, non-xref block definitions.

Every preview binds live evidence into an approval fingerprint.  Execution
rejects stale evidence, locked/xref state, and unsupported variants, wraps the
mutation in one undo mark, restores properties on failure, and verifies exact
postconditions.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch25b import (
    MaskMode,
    TextBoxRequest,
    TextBoxShape,
    plan_text_box,
)
from .headless_core_batch28a import RenameBlocksRequest, plan_rename_blocks

HELP_URLS = {
    "TX": "https://izzarder.com/355",
    "BRN": "https://izzarder.com/343",
}

BLOCKED = {
    "MK": (
        "ZWCAD 2026 exposes BackgroundFill but not the official color/width DXF "
        "settings through COM; SendCommand DXF probing did not provide a bounded "
        "synchronous completion signal, so atomic postcondition verification is unavailable"
    ),
}

class LiveEntityEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    handle: str
    object_name: str
    layer: str
    locked_layer: bool
    is_xref: bool
    state_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBlockEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    name: str
    base_point: tuple[float, float, float]
    member_handles: tuple[str, ...]
    member_state_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    is_xref: bool
    is_layout: bool


class LiveTXExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: TextBoxRequest
    expected_sources: tuple[LiveEntityEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBRNExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: RenameBlocksRequest
    expected_sources: tuple[LiveBlockEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveGapResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...] = ()
    changed_handles: tuple[str, ...] = ()
    renamed_blocks: tuple[tuple[str, str], ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    rollback_performed: bool = False
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return [_json_value(item) for item in value]
    except TypeError:
        return str(value)


def _drawing(name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _entity(doc: Any, handle: str) -> Any:
    try:
        return doc.HandleToObject(handle)
    except Exception as error:
        raise ValueError(f"entity handle {handle!r} is not present in the active document") from error


def _point3(value: Any) -> tuple[float, float, float]:
    if all(hasattr(value, name) for name in ("x", "y")):
        return (float(value.x), float(value.y), float(getattr(value, "z", 0.0)))
    items = tuple(float(item) for item in value)
    return (items[0], items[1], items[2] if len(items) > 2 else 0.0)


def _same_point(first: Any, second: Any, tolerance: float = 1e-8) -> bool:
    return all(
        math.isclose(a, b, rel_tol=0, abs_tol=tolerance)
        for a, b in zip(_point3(first), _point3(second), strict=True)
    )


def _layer_state(doc: Any, layer_name: str) -> tuple[bool, bool]:
    try:
        layer = doc.Layers.Item(layer_name)
    except Exception as error:
        raise ValueError(f"required layer {layer_name!r} does not exist") from error
    actual = str(layer.Name)
    return bool(layer.Lock), "|" in actual


def _assert_writable_layer(doc: Any, layer_name: str) -> None:
    locked, is_xref = _layer_state(doc, layer_name)
    if locked or is_xref:
        raise ValueError(f"layer {layer_name!r} is locked or xref-dependent")


def _entity_state(doc: Any, entity: Any, *, mode: str) -> LiveEntityEvidence:
    layer = str(entity.Layer)
    locked, is_xref = _layer_state(doc, layer)
    if locked or is_xref:
        raise ValueError(f"entity {entity.Handle} is on a locked or xref-dependent layer")
    object_name = str(entity.ObjectName)
    payload: dict[str, Any] = {
        "handle": str(entity.Handle),
        "object_name": object_name,
        "layer": layer,
    }
    if mode == "TX":
        if object_name.casefold() not in {"acdbtext", "acdbmtext"}:
            raise ValueError("TX live subset requires top-level TEXT or MTEXT")
        minimum, maximum = entity.GetBoundingBox()
        payload.update(
            text=str(entity.TextString),
            style=str(entity.StyleName),
            height=float(entity.Height),
            bounds=(_json_value(minimum), _json_value(maximum)),
        )
    else:  # pragma: no cover - callers own the closed set
        raise AssertionError(mode)
    return LiveEntityEvidence(
        handle=str(entity.Handle),
        object_name=object_name,
        layer=layer,
        locked_layer=locked,
        is_xref=is_xref,
        state_fingerprint=_fingerprint(payload),
    )


def _tx_validate_scope(doc: Any, request: TextBoxRequest) -> None:
    if request.shape is not TextBoxShape.RECTANGLE:
        raise ValueError("TX live promotion is limited to the official straight rectangular border")
    if request.mask_mode is not MaskMode.NONE:
        raise ValueError("TX masking is not exposed because MK color/width postconditions are unavailable")
    if request.group_results:
        raise ValueError("TX live promotion does not claim compiled associative grouping semantics")
    if request.corner_radius != 0:
        raise ValueError("TX straight rectangular subset requires corner_radius=0")
    _assert_writable_layer(doc, request.text_layer)
    _assert_writable_layer(doc, request.boundary_layer)
    try:
        doc.TextStyles.Item(request.text_style)
    except Exception as error:
        raise ValueError(f"TX text style {request.text_style!r} does not exist") from error
    for boundary in request.exact_boundaries:
        if boundary.boundary_layer.casefold() != request.boundary_layer.casefold():
            raise ValueError("TX exact boundary layer must equal the reviewed boundary layer")
        if len(boundary.exact_vertices) != 4:
            raise ValueError("TX rectangular live subset requires exactly four explicit vertices")
        if boundary.group_id is not None:
            raise ValueError("TX non-grouped live subset cannot contain group ids")


def _tx_sources(doc: Any, request: TextBoxRequest) -> tuple[LiveEntityEvidence, ...]:
    evidence: list[LiveEntityEvidence] = []
    for snapshot in request.sources:
        entity = _entity(doc, snapshot.handle)
        current = _entity_state(doc, entity, mode="TX")
        minimum, maximum = entity.GetBoundingBox()
        if str(entity.TextString) != snapshot.text:
            raise ValueError(f"TX text snapshot is stale for {snapshot.handle}")
        if not _same_point(minimum, snapshot.bounds_min) or not _same_point(maximum, snapshot.bounds_max):
            raise ValueError(f"TX bounds snapshot is stale for {snapshot.handle}")
        evidence.append(current)
    return tuple(evidence)


def _payload(alias: str, request: Any, plan: Any, sources: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
    }


def preview_live_tx(request: TextBoxRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    doc = _drawing(request.document_id)
    _tx_validate_scope(doc, request)
    sources = _tx_sources(doc, request)
    payload = _payload("TX", request, plan_text_box(request), sources)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "official_help_url": HELP_URLS["TX"],
        "scope_note": "straight rectangular polyline border; no mask and no associative group",
    }


def _lwpolyline(space: Any, vertices: Any) -> Any:
    import pythoncom
    import win32com.client

    coordinates = [coordinate for point in vertices for coordinate in (point.x, point.y)]
    variant = win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        coordinates,
    )
    return space.AddLightWeightPolyline(variant)


def execute_live_tx(request: LiveTXExecuteRequest) -> LiveGapResult:
    plan = plan_text_box(request.request)
    payload = _payload("TX", request.request, plan, request.expected_sources)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact TX preview")
    doc = _drawing(request.request.document_id)
    _tx_validate_scope(doc, request.request)
    current = _tx_sources(doc, request.request)
    if current != request.expected_sources:
        raise ValueError("TX source state no longer matches the approved preview")
    source_by_handle = {
        item.handle.casefold(): _entity(doc, item.handle) for item in request.request.sources
    }
    boundaries = {
        item.source_handle.casefold(): item for item in request.request.exact_boundaries
    }
    ordered_boundaries = tuple(
        boundaries[item.handle.casefold()] for item in request.request.sources
    )
    backups: list[tuple[Any, str, str, str, float]] = []
    created: list[Any] = []
    doc.StartUndoMark()
    closed = False
    try:
        for snapshot in request.request.sources:
            entity = source_by_handle[snapshot.handle.casefold()]
            backups.append(
                (entity, str(entity.TextString), str(entity.StyleName), str(entity.Layer), float(entity.Height))
            )
            entity.TextString = snapshot.text.upper() if request.request.uppercase else snapshot.text
            entity.StyleName = request.request.text_style
            entity.Layer = request.request.text_layer
            entity.Height = request.request.text_height
            boundary = boundaries[snapshot.handle.casefold()]
            polyline = _lwpolyline(doc.ModelSpace, boundary.exact_vertices)
            polyline.Closed = True
            polyline.Layer = boundary.boundary_layer
            created.append(polyline)
        doc.Regen(1)
        for entity, snapshot in zip(
            (source_by_handle[item.handle.casefold()] for item in request.request.sources),
            request.request.sources,
            strict=True,
        ):
            expected_text = snapshot.text.upper() if request.request.uppercase else snapshot.text
            if (
                str(entity.TextString) != expected_text
                or str(entity.StyleName).casefold() != request.request.text_style.casefold()
                or str(entity.Layer).casefold() != request.request.text_layer.casefold()
                or not math.isclose(float(entity.Height), request.request.text_height, abs_tol=1e-9)
            ):
                raise RuntimeError("TX text postcondition failed")
        for polyline, boundary in zip(created, ordered_boundaries, strict=True):
            actual = tuple(float(value) for value in polyline.Coordinates)
            expected = tuple(
                coordinate for point in boundary.exact_vertices for coordinate in (point.x, point.y)
            )
            if (
                not bool(polyline.Closed)
                or str(polyline.Layer).casefold() != boundary.boundary_layer.casefold()
                or len(actual) != len(expected)
                or any(not math.isclose(a, b, abs_tol=1e-8) for a, b in zip(actual, expected, strict=True))
            ):
                raise RuntimeError("TX boundary postcondition failed")
        doc.EndUndoMark()
        closed = True
        return LiveGapResult(
            document_name=str(doc.Name),
            command_alias="TX",
            created_handles=tuple(str(item.Handle) for item in created),
            changed_handles=tuple(str(item.Handle) for item, *_ in backups),
            undo_mark_opened=True,
            undo_mark_closed=True,
            postcondition_verified=True,
        )
    except Exception:
        for entity in reversed(created):
            try:
                entity.Delete()
            except Exception:
                pass
        for entity, text, style, layer, height in reversed(backups):
            try:
                entity.TextString, entity.StyleName, entity.Layer, entity.Height = text, style, layer, height
            except Exception:
                pass
        if not closed:
            doc.EndUndoMark()
        raise


def _block(doc: Any, name: str) -> Any:
    try:
        return doc.Blocks.Item(name)
    except Exception as error:
        raise ValueError(f"block definition {name!r} does not exist") from error


def _block_evidence(doc: Any, snapshot: Any) -> LiveBlockEvidence:
    block = _block(doc, snapshot.name)
    if bool(block.IsXRef) or bool(block.IsLayout):
        raise ValueError(f"BRN does not rename xref/layout block {snapshot.name!r}")
    if str(block.Name).startswith("*"):
        raise ValueError("BRN live subset does not rename anonymous/dynamic block definitions")
    try:
        owners = tuple(doc.Blocks)
    except TypeError:
        owners = ()
    for owner in owners:
        try:
            owned_entities = tuple(owner)
        except TypeError:
            continue
        for entity in owned_entities:
            if str(getattr(entity, "ObjectName", "")).casefold() != "acdbblockreference":
                continue
            name = str(getattr(entity, "Name", ""))
            effective_name = str(getattr(entity, "EffectiveName", name))
            if effective_name.casefold() == snapshot.name.casefold() and name.casefold() != effective_name.casefold():
                raise ValueError("BRN live subset excludes dynamic block references")
    members = tuple(block)
    by_handle = {str(item.Handle).casefold(): item for item in members}
    if set(by_handle) != {item.handle.casefold() for item in snapshot.members}:
        raise ValueError(f"BRN member snapshot is stale for {snapshot.name!r}")
    member_payload: list[dict[str, Any]] = []
    for source in snapshot.members:
        entity = by_handle[source.handle.casefold()]
        if str(entity.ObjectName).casefold().removeprefix("acdb") != source.entity_type.casefold().removeprefix("acdb"):
            raise ValueError(f"BRN member type is stale for {source.handle!r}")
        if str(entity.Layer).casefold() != source.layer.casefold():
            raise ValueError(f"BRN member layer is stale for {source.handle!r}")
        _assert_writable_layer(doc, str(entity.Layer))
        member_payload.append(
            {
                "handle": str(entity.Handle),
                "object_name": str(entity.ObjectName),
                "layer": str(entity.Layer),
                "geometry": {
                    name: _json_value(getattr(entity, name))
                    for name in (
                        "Coordinates",
                        "StartPoint",
                        "EndPoint",
                        "Center",
                        "Radius",
                        "TextString",
                        "InsertionPoint",
                        "Rotation",
                        "ScaleFactor",
                    )
                    if hasattr(entity, name)
                },
            }
        )
    base_point = _point3(block.Origin)
    if not _same_point(base_point, snapshot.base_point):
        raise ValueError(f"BRN base point snapshot is stale for {snapshot.name!r}")
    return LiveBlockEvidence(
        name=str(block.Name),
        base_point=base_point,
        member_handles=tuple(str(item.Handle) for item in members),
        member_state_fingerprint=_fingerprint({"members": member_payload}),
        is_xref=False,
        is_layout=False,
    )


def _brn_validate_scope(doc: Any, request: RenameBlocksRequest) -> None:
    if request.copy_instead_of_rename:
        raise ValueError("BRN live subset does not claim compiled copy-and-rebind semantics")
    if request.ignore_existing_name_collisions:
        raise ValueError("BRN live subset requires collision-free target names")
    source_names = {item.name.casefold() for item in request.definitions}
    for result in request.exact_results:
        if result.result_name.casefold() in source_names:
            raise ValueError("BRN atomic rename does not permit cyclic/source-name targets")
        try:
            doc.Blocks.Item(result.result_name)
        except Exception:
            continue
        raise ValueError(f"BRN target block name already exists: {result.result_name!r}")


def _brn_sources(doc: Any, request: RenameBlocksRequest) -> tuple[LiveBlockEvidence, ...]:
    return tuple(_block_evidence(doc, item) for item in request.definitions)


def preview_live_brn(request: RenameBlocksRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    doc = _drawing(request.document_id)
    _brn_validate_scope(doc, request)
    sources = _brn_sources(doc, request)
    payload = _payload("BRN", request, plan_rename_blocks(request), sources)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "official_help_url": HELP_URLS["BRN"],
        "scope_note": "whole static block-definition rename with absent unique targets",
    }


def execute_live_brn(request: LiveBRNExecuteRequest) -> LiveGapResult:
    plan = plan_rename_blocks(request.request)
    payload = _payload("BRN", request.request, plan, request.expected_sources)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact BRN preview")
    doc = _drawing(request.request.document_id)
    _brn_validate_scope(doc, request.request)
    current = _brn_sources(doc, request.request)
    if current != request.expected_sources:
        raise ValueError("BRN source state no longer matches the approved preview")
    results = {item.source_name.casefold(): item for item in request.request.exact_results}
    changed: list[tuple[Any, str, str]] = []
    doc.StartUndoMark()
    closed = False
    try:
        for evidence in current:
            block = _block(doc, evidence.name)
            target = results[evidence.name.casefold()].result_name
            original = str(block.Name)
            block.Name = target
            changed.append((block, original, target))
        for block, _, target in changed:
            if str(block.Name).casefold() != target.casefold():
                raise RuntimeError("BRN block-name postcondition failed")
            if str(_block(doc, target).Name).casefold() != target.casefold():
                raise RuntimeError("BRN block-table postcondition failed")
        doc.Regen(1)
        doc.EndUndoMark()
        closed = True
        return LiveGapResult(
            document_name=str(doc.Name),
            command_alias="BRN",
            renamed_blocks=tuple((original, target) for _, original, target in changed),
            undo_mark_opened=True,
            undo_mark_closed=True,
            postcondition_verified=True,
        )
    except Exception:
        for block, original, _ in reversed(changed):
            try:
                block.Name = original
            except Exception:
                pass
        if not closed:
            doc.EndUndoMark()
        raise


def register_live_gap_25_32_tools(mcp: FastMCP) -> None:
    preview_annotations = ToolAnnotations(
        title="Preview help-verified xiCAD Batch 25-32 live gap",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute_annotations = ToolAnnotations(
        title="Execute help-verified xiCAD Batch 25-32 live gap",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    mcp.tool(name="xicad_preview_live_tx", annotations=preview_annotations)(preview_live_tx)
    mcp.tool(name="xicad_execute_live_tx", annotations=execute_annotations)(execute_live_tx)
    mcp.tool(name="xicad_preview_live_brn", annotations=preview_annotations)(preview_live_brn)
    mcp.tool(name="xicad_execute_live_brn", annotations=execute_annotations)(execute_live_brn)
