from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch23a import (
    ChangeBlockDimensionScaleRequest,
    CheckPlotBoxRequest,
    FindFrameScaleRequest,
    FrameSortRequest,
    MakeDrawingListRequest,
    TitleNumberingRequest,
    plan_change_block_dimension_scale,
    plan_check_plot_box,
    plan_find_frame_scale,
    plan_frame_sort,
    plan_make_drawing_list,
    plan_title_numbering,
)
from .headless_core_batch23b import (
    AreaElementsRequest,
    BuildingDistanceRequest,
    BunAreaRequest,
    MapAreaRequest,
    ObjectToBlockRequest,
    ZoomRememberRequest,
    plan_area_elements,
    plan_building_distance,
    plan_bun_area,
    plan_map_area,
    plan_object_to_block,
    plan_zoom_remember,
)

ExecutableRequest = FrameSortRequest | TitleNumberingRequest


class LiveBlockReferenceEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    object_name: str
    block_name: str
    insertion_point: Point3D
    layer: str
    rotation: float
    x_scale: float
    y_scale: float
    z_scale: float
    locked_layer: bool
    is_xref: bool


class LiveAttributeEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_reference_handle: str
    handle: str
    object_name: str
    tag: str
    text: str
    layer: str
    locked_layer: bool
    is_xref: bool


class LiveBatch23ExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ExecutableRequest
    expected_blocks: tuple[LiveBlockReferenceEvidence, ...]
    expected_attributes: tuple[LiveAttributeEvidence, ...] = ()
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch23Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


BLOCKED = {
    "DFS": "frame extent discovery, legacy rounding/text output, and safe drawing-variable application scope are unrecovered",
    "DSB": "nested-dimension discovery and block-definition versus instance mutation scope are unrecovered",
    "MDL": "registered-frame extraction, table insertion point/formatting, and multi-file I/O are unrecovered",
    "PBS": "plot-boundary discovery, accepted entity types, and legacy visual marking are unrecovered",
    "TOB": "plot-box recognition, block registration, and exact block-definition construction are unrecovered",
    "ZR": "zoom persistence file format, revision rules, and viewport-state restoration semantics are unrecovered",
    "AE": "area extraction and xiCAD text/field formatting are unrecovered",
    "AHM": "boundary recognition and xiCAD triangulation policy are unrecovered",
    "BA": "legacy allocation/rounding and xiCAD text/field formatting are unrecovered",
    "CDB": "building recognition, closest-pair search, and legal threshold selection are unrecovered",
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
    result: dict[str, Any] = {}
    for block in doc.Blocks:
        if bool(block.IsLayout):
            for entity in block:
                result[str(entity.Handle).casefold()] = entity
    return result


def _point(value: Any) -> Point3D:
    values = tuple(float(item) for item in value)
    return Point3D(x=values[0], y=values[1], z=values[2])


def _variant(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])


def _block(doc: Any, handle: str) -> tuple[LiveBlockReferenceEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None or str(entity.ObjectName).casefold() != "acdbblockreference":
        raise ValueError(f"Batch 23 requires an AcDbBlockReference: {handle}")
    layer = str(entity.Layer)
    locked = bool(doc.Layers.Item(layer).Lock)
    is_xref = "|" in layer
    if locked or is_xref:
        raise ValueError(f"Batch 23 block is locked or xref-dependent: {handle}")
    state = LiveBlockReferenceEvidence(
        handle=str(entity.Handle),
        object_name=str(entity.ObjectName),
        block_name=str(getattr(entity, "EffectiveName", entity.Name)),
        insertion_point=_point(entity.InsertionPoint),
        layer=layer,
        rotation=float(entity.Rotation),
        x_scale=float(entity.XScaleFactor),
        y_scale=float(entity.YScaleFactor),
        z_scale=float(entity.ZScaleFactor),
        locked_layer=locked,
        is_xref=is_xref,
    )
    return state, entity


def _attribute(doc: Any, block: Any, handle: str) -> tuple[LiveAttributeEvidence, Any]:
    matches = [item for item in block.GetAttributes() if str(item.Handle).casefold() == handle.casefold()]
    if len(matches) != 1:
        raise ValueError(f"TN expected exactly one writable attribute {handle!r}, found {len(matches)}")
    entity = matches[0]
    layer = str(entity.Layer)
    locked = bool(doc.Layers.Item(layer).Lock)
    is_xref = "|" in layer
    if locked or is_xref:
        raise ValueError(f"TN attribute is locked or xref-dependent: {handle}")
    return (
        LiveAttributeEvidence(
            block_reference_handle=str(block.Handle),
            handle=str(entity.Handle),
            object_name=str(entity.ObjectName),
            tag=str(entity.TagString),
            text=str(entity.TextString),
            layer=layer,
            locked_layer=locked,
            is_xref=is_xref,
        ),
        entity,
    )


def _plan(request: Any) -> Any:
    if isinstance(request, FrameSortRequest):
        return plan_frame_sort(request)
    if isinstance(request, FindFrameScaleRequest):
        return plan_find_frame_scale(request)
    if isinstance(request, ChangeBlockDimensionScaleRequest):
        return plan_change_block_dimension_scale(request)
    if isinstance(request, MakeDrawingListRequest):
        return plan_make_drawing_list(request)
    if isinstance(request, CheckPlotBoxRequest):
        return plan_check_plot_box(request)
    if isinstance(request, TitleNumberingRequest):
        return plan_title_numbering(request)
    if isinstance(request, ObjectToBlockRequest):
        return plan_object_to_block(request)
    if isinstance(request, ZoomRememberRequest):
        return plan_zoom_remember(request)
    if isinstance(request, AreaElementsRequest):
        return plan_area_elements(request)
    if isinstance(request, MapAreaRequest):
        return plan_map_area(request)
    if isinstance(request, BunAreaRequest):
        return plan_bun_area(request)
    return plan_building_distance(request)


def _payload(
    request: ExecutableRequest,
    plan: Any,
    blocks: tuple[LiveBlockReferenceEvidence, ...],
    attributes: tuple[LiveAttributeEvidence, ...],
) -> dict[str, Any]:
    return {
        "command_alias": plan.command_alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_blocks": [item.model_dump(mode="json") for item in blocks],
        "expected_attributes": [item.model_dump(mode="json") for item in attributes],
    }


def _preview_executable(request: ExecutableRequest, expected_alias: str) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _plan(request)
    if plan.command_alias != expected_alias:
        raise ValueError(f"{expected_alias} preview received a different request type")
    doc = _drawing(request.document_id)
    blocks: list[LiveBlockReferenceEvidence] = []
    attributes: list[LiveAttributeEvidence] = []
    if isinstance(request, FrameSortRequest):
        for placement in request.placements:
            state, _ = _block(doc, placement.block_reference_handle)
            if state.insertion_point != placement.source_anchor:
                raise ValueError(f"DBS source anchor does not match block {placement.block_reference_handle}")
            blocks.append(state)
    else:
        for target in request.ordered_targets:
            block_state, block = _block(doc, target.block_reference_handle)
            attribute_state, _ = _attribute(doc, block, target.attribute_handle)
            if (
                attribute_state.tag.casefold() != target.attribute_tag.casefold()
                or attribute_state.text != target.old_text
            ):
                raise ValueError(f"TN attribute state does not match request: {target.attribute_handle}")
            blocks.append(block_state)
            attributes.append(attribute_state)
    block_tuple, attribute_tuple = tuple(blocks), tuple(attributes)
    payload = _payload(request, plan, block_tuple, attribute_tuple)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "exact block/attribute handles and mutable properties are stale-checked before one Undo group",
    }


def _preview_blocked(request: Any) -> dict[str, Any]:
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


def preview_live_dbs(request: FrameSortRequest) -> dict[str, Any]:
    return _preview_executable(request, "DBS")


def preview_live_dfs(request: FindFrameScaleRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_dsb(request: ChangeBlockDimensionScaleRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_mdl(request: MakeDrawingListRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_pbs(request: CheckPlotBoxRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_tn(request: TitleNumberingRequest) -> dict[str, Any]:
    return _preview_executable(request, "TN")


def preview_live_tob(request: ObjectToBlockRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_zr(request: ZoomRememberRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_ae(request: AreaElementsRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_ahm(request: MapAreaRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_ba(request: BunAreaRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_cdb(request: BuildingDistanceRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def execute_live_batch23(request: LiveBatch23ExecuteRequest) -> LiveBatch23Result:
    plan = _plan(request.request)
    payload = _payload(request.request, plan, request.expected_blocks, request.expected_attributes)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 23 preview")
    doc = _drawing(request.request.document_id)
    current_blocks = tuple(_block(doc, item.handle) for item in request.expected_blocks)
    if tuple(item[0] for item in current_blocks) != request.expected_blocks:
        raise ValueError("Batch 23 block state no longer matches the approved preview")
    block_objects = {state.handle.casefold(): entity for state, entity in current_blocks}
    current_attributes: list[tuple[LiveAttributeEvidence, Any]] = []
    for expected in request.expected_attributes:
        block = block_objects.get(expected.block_reference_handle.casefold())
        if block is None:
            raise ValueError(f"TN approved block is unavailable: {expected.block_reference_handle}")
        current_attributes.append(_attribute(doc, block, expected.handle))
    if tuple(item[0] for item in current_attributes) != request.expected_attributes:
        raise ValueError("Batch 23 attribute state no longer matches the approved preview")
    attribute_objects = {state.handle.casefold(): entity for state, entity in current_attributes}
    changed: list[Any] = []
    doc.StartUndoMark()
    try:
        if plan.command_alias == "DBS":
            for placement, move in zip(request.request.placements, plan.moves, strict=True):
                entity = block_objects[move.block_reference_handle.casefold()]
                target = Point3D(
                    x=placement.source_anchor.x + move.displacement.x,
                    y=placement.source_anchor.y + move.displacement.y,
                    z=placement.source_anchor.z + move.displacement.z,
                )
                entity.InsertionPoint = _variant(target)
                changed.append(entity)
        elif plan.command_alias == "TN":
            for update in plan.updates:
                entity = attribute_objects[update.attribute_handle.casefold()]
                entity.TextString = update.new_text
                changed.append(entity)
        else:
            raise ValueError(f"Batch 23 live execution is not exposed for {plan.command_alias}")
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    if any(str(entity.Handle).casefold() not in available for entity in block_objects.values()):
        raise RuntimeError(f"{plan.command_alias} postcondition failed: block reference missing")
    if plan.command_alias == "DBS":
        for placement in request.request.placements:
            if _point(block_objects[placement.block_reference_handle.casefold()].InsertionPoint) != placement.target_anchor:
                raise RuntimeError("DBS postcondition failed: block insertion point mismatch")
    else:
        for update in plan.updates:
            if str(attribute_objects[update.attribute_handle.casefold()].TextString) != update.new_text:
                raise RuntimeError("TN postcondition failed: attribute text mismatch")
    return LiveBatch23Result(
        document_name=str(doc.Name),
        command_alias=plan.command_alias,
        changed_handles=tuple(str(item.Handle) for item in changed),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_batch23_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 23 operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 23 operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    functions = {
        "dbs": preview_live_dbs,
        "dfs": preview_live_dfs,
        "dsb": preview_live_dsb,
        "mdl": preview_live_mdl,
        "pbs": preview_live_pbs,
        "tn": preview_live_tn,
        "tob": preview_live_tob,
        "zr": preview_live_zr,
        "ae": preview_live_ae,
        "ahm": preview_live_ahm,
        "ba": preview_live_ba,
        "cdb": preview_live_cdb,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
        if alias.upper() not in BLOCKED:
            mcp.tool(name=f"xicad_execute_live_{alias}", annotations=execute)(execute_live_batch23)
