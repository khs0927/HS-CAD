from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch27a import (
    AddObjectsToBlockRequest,
    AllBlocksExplodeRequest,
    BlockAutoMakeRequest,
    BlockToXrefRequest,
    LineBetweenBlocksRequest,
    SymbolDrawRequest,
    plan_add_objects_to_block,
    plan_all_blocks_explode,
    plan_block_auto_make,
    plan_block_to_xref,
    plan_line_between_blocks,
    plan_xz_symbol,
)
from .headless_core_batch27b import (
    BlockConditionChangeRequest,
    BlockLayerChangeRequest,
    ChangeBlockRequest,
    CopyBlockDefinitionRequest,
    ExportBlockRequest,
    RebaseBlockRequest,
    plan_block_condition_change,
    plan_block_layer_change,
    plan_change_block,
    plan_copy_block_definition,
    plan_export_block,
    plan_rebase_block,
)


class LiveBlockEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    block_name: str
    layer: str
    insertion_point: Point3D
    state_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    locked_layer: bool
    is_xref: bool


class LiveLayerEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    locked: bool
    is_xref: bool


class LiveBBLExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: LineBetweenBlocksRequest
    expected_sources: tuple[LiveBlockEvidence, ...]
    expected_target_layer: LiveLayerEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch27Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


BLOCKED = {
    "XZ": "compiled symbol geometry and ProposedEntity geometry-payload decoding are unrecovered",
    "ABX": "compiled explode ordering, property inheritance, nested-block, attribute, and dynamic-block behavior are unrecovered",
    "B2X": "external DWG creation, overwrite, dependency, file-version, and xref attachment semantics are unrecovered",
    "BAD": "compiled block-definition editing, nested ownership, attribute, and dynamic-block behavior are unrecovered",
    "BAM": "compiled block naming, definition ownership, attribute, unit, and source-replacement behavior are unrecovered",
    "BCC": "compiled definition traversal, nested explode, property inheritance, and dynamic-block behavior are unrecovered",
    "BCH": "external definition import, attributes, dynamic properties, nested replacement, and dependency behavior are unrecovered",
    "BCO": "compiled nested transform composition, destination ownership, and extracted-property inheritance are unrecovered",
    "BEX": "external DWG/DXF version, units, dependencies, overwrite, and atomic file-output behavior are unrecovered",
    "BIN": "compiled base-point compensation, attributes, dynamic blocks, and nested-reference behavior are unrecovered",
    "BLA": "compiled definition selection scope, nested traversal, dynamic blocks, and outer-reference treatment are unrecovered",
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
    coordinates = tuple(float(item) for item in value)
    return Point3D(x=coordinates[0], y=coordinates[1], z=coordinates[2] if len(coordinates) > 2 else 0.0)


def _variant_points(points: tuple[Point3D, ...]) -> Any:
    import pythoncom
    import win32com.client

    values = [coordinate for point in points for coordinate in (point.x, point.y)]
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)


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


def _block_evidence(doc: Any, handle: str) -> tuple[LiveBlockEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"Batch 27 block reference does not exist: {handle}")
    if str(entity.ObjectName).casefold() != "acdbblockreference":
        raise ValueError(f"Batch 27 BBL source is not a block reference: {handle}")
    name = str(getattr(entity, "EffectiveName", "") or entity.Name)
    layer = str(entity.Layer)
    insertion = _point(entity.InsertionPoint)
    locked = bool(doc.Layers.Item(layer).Lock)
    xref = _is_xref(doc, entity, name, layer)
    if locked or xref:
        raise ValueError(f"Batch 27 block reference is locked or xref-dependent: {handle}")
    state = {
        "handle": str(entity.Handle),
        "block_name": name,
        "layer": layer,
        "insertion_point": insertion.model_dump(mode="json"),
        "rotation": float(entity.Rotation),
        "x_scale": float(entity.XScaleFactor),
        "y_scale": float(entity.YScaleFactor),
        "z_scale": float(entity.ZScaleFactor),
    }
    return (
        LiveBlockEvidence(
            handle=str(entity.Handle),
            block_name=name,
            layer=layer,
            insertion_point=insertion,
            state_fingerprint=_fingerprint(state),
            locked_layer=locked,
            is_xref=xref,
        ),
        entity,
    )


def _layer(doc: Any, name: str) -> LiveLayerEvidence:
    try:
        layer = doc.Layers.Item(name)
    except Exception as exc:
        raise ValueError(f"Batch 27 target layer does not exist: {name}") from exc
    actual = str(layer.Name)
    result = LiveLayerEvidence(name=actual, locked=bool(layer.Lock), is_xref="|" in actual)
    if result.locked or result.is_xref:
        raise ValueError(f"Batch 27 target layer is locked or xref-dependent: {name}")
    return result


def _plan(request: Any) -> Any:
    planners = {
        SymbolDrawRequest: plan_xz_symbol,
        AllBlocksExplodeRequest: plan_all_blocks_explode,
        BlockToXrefRequest: plan_block_to_xref,
        AddObjectsToBlockRequest: plan_add_objects_to_block,
        BlockAutoMakeRequest: plan_block_auto_make,
        LineBetweenBlocksRequest: plan_line_between_blocks,
        BlockConditionChangeRequest: plan_block_condition_change,
        ChangeBlockRequest: plan_change_block,
        CopyBlockDefinitionRequest: plan_copy_block_definition,
        ExportBlockRequest: plan_export_block,
        RebaseBlockRequest: plan_rebase_block,
        BlockLayerChangeRequest: plan_block_layer_change,
    }
    for request_type, planner in planners.items():
        if isinstance(request, request_type):
            return planner(request)
    raise TypeError(f"unsupported Batch 27 request: {type(request).__name__}")


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


def _bbl_payload(
    request: LineBetweenBlocksRequest,
    plan: Any,
    sources: tuple[LiveBlockEvidence, ...],
    layer: LiveLayerEvidence,
) -> dict[str, Any]:
    return {
        "command_alias": "BBL",
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
        "expected_target_layer": layer.model_dump(mode="json"),
    }


def preview_live_bbl(request: LineBetweenBlocksRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = plan_line_between_blocks(request)
    doc = _drawing(request.document_id)
    pairs = tuple(_block_evidence(doc, handle) for handle in request.ordered_handles)
    sources = tuple(pair[0] for pair in pairs)
    snapshots = {item.handle.casefold(): item for item in request.blocks}
    for evidence in sources:
        snapshot = snapshots[evidence.handle.casefold()]
        if (
            evidence.block_name.casefold() != snapshot.block_name.casefold()
            or evidence.layer.casefold() != snapshot.layer.casefold()
            or evidence.insertion_point != snapshot.insertion_point
        ):
            raise ValueError(f"Batch 27 BBL source does not match snapshot: {snapshot.handle}")
    layer = _layer(doc, request.output_layer)
    payload = _bbl_payload(request, plan, sources, layer)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "exact insertion points are stale-checked and joined in caller-approved order; legacy equivalence is not claimed",
    }


def preview_live_xz(request: SymbolDrawRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_abx(request: AllBlocksExplodeRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_b2x(request: BlockToXrefRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_bad(request: AddObjectsToBlockRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_bam(request: BlockAutoMakeRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_bcc(request: BlockConditionChangeRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_bch(request: ChangeBlockRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_bco(request: CopyBlockDefinitionRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_bex(request: ExportBlockRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_bin(request: RebaseBlockRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_bla(request: BlockLayerChangeRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def execute_live_bbl(request: LiveBBLExecuteRequest) -> LiveBatch27Result:
    plan = plan_line_between_blocks(request.request)
    payload = _bbl_payload(request.request, plan, request.expected_sources, request.expected_target_layer)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 27 BBL preview")
    doc = _drawing(request.request.document_id)
    current = tuple(_block_evidence(doc, handle)[0] for handle in request.request.ordered_handles)
    if current != request.expected_sources:
        raise ValueError("Batch 27 BBL source state no longer matches the approved preview")
    if _layer(doc, request.expected_target_layer.name) != request.expected_target_layer:
        raise ValueError("Batch 27 BBL target-layer state no longer matches the approved preview")

    doc.StartUndoMark()
    entity: Any | None = None
    try:
        entity = doc.ModelSpace.AddLightWeightPolyline(_variant_points(plan.vertices))
        entity.Layer = plan.output_layer
        entity.Closed = plan.closed
    finally:
        doc.EndUndoMark()

    if entity is None:
        raise RuntimeError("BBL postcondition failed: output was not created")
    available = _entities(doc)
    if str(entity.Handle).casefold() not in available:
        raise RuntimeError("BBL postcondition failed: output entity is missing")
    coordinates = tuple(float(value) for value in entity.Coordinates)
    expected = tuple(value for point in plan.vertices for value in (point.x, point.y))
    if (
        coordinates != expected
        or bool(entity.Closed) is not plan.closed
        or str(entity.Layer).casefold() != plan.output_layer.casefold()
    ):
        raise RuntimeError("BBL postcondition failed: polyline differs from the approved plan")
    return LiveBatch27Result(
        document_name=str(doc.Name),
        command_alias="BBL",
        created_handles=(str(entity.Handle),),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_batch27_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 27 operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 27 operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    functions = {
        "xz": preview_live_xz,
        "abx": preview_live_abx,
        "b2x": preview_live_b2x,
        "bad": preview_live_bad,
        "bam": preview_live_bam,
        "bbl": preview_live_bbl,
        "bcc": preview_live_bcc,
        "bch": preview_live_bch,
        "bco": preview_live_bco,
        "bex": preview_live_bex,
        "bin": preview_live_bin,
        "bla": preview_live_bla,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
    mcp.tool(name="xicad_execute_live_bbl", annotations=execute)(execute_live_bbl)
