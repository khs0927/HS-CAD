from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch19a import (
    HatchDefinition,
    HatchMergeRequest,
    HatchPatternRequest,
    RandomSolidRequest,
    SolidHatchRequest,
    TableRequest,
    TableTextRequest,
    TableTextSnapshot,
    plan_hatch_merge,
    plan_hatch_pattern,
    plan_random_solid,
    plan_solid_hatch,
    plan_table,
    plan_table_text,
)
from .headless_core_batch19b import (
    BreakAndTextRequest,
    BreakOverRequest,
    BreakToCurrentRequest,
    CircleBreakRequest,
    CutterRequest,
    DivideToPolylineRequest,
    plan_break_and_text,
    plan_break_over,
    plan_break_to_current,
    plan_circle_break,
    plan_cutter,
    plan_divide_to_polyline,
)


class LiveLayerEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    color: int
    linetype: str
    locked: bool
    is_xref: bool


class LiveCircleEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    handle: str
    center: Point3D
    radius: float = Field(gt=0)
    layer: str
    color: int
    linetype: str
    locked_layer: bool
    is_xref: bool


class LiveCbExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: CircleBreakRequest
    expected_circle: LiveCircleEvidence
    expected_target_layer: LiveLayerEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch19Result(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    erased_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


BLOCKED = {
    "HM": "merged hatch associativity and legacy property precedence are not recovered",
    "HPM": "PAT/file output and legacy geometry-to-pattern conversion are explicitly blocked",
    "RDS": "legacy random selection probability and seed algorithm are unrecovered",
    "SOL": "boundary loop/island provenance and associative ownership are not snapshotted",
    "TB": "legacy CAD/general table style, merges, and formatting are unspecified",
    "TBT": "table cell contents, merge state, formatting, and traversal semantics are incomplete",
    "BAT": "break-gap application requires source-curve parameterization and exact residual segments",
    "BB": "isolated segment is specified but the two retained source residuals are not",
    "BRO": "caller-supplied intersections lack target-curve parameter and residual-segment provenance",
    "CUT": "containment is caller-preclassified and explode/solid conversion output is not fully specified",
    "DTP": "sampled vertices lack verifiable source-curve parameter and chord-error provenance",
}


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


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


def _angle_close(actual: float, expected: float, tolerance: float = 1e-9) -> bool:
    difference = (actual - expected + math.pi) % (2 * math.pi) - math.pi
    return abs(difference) <= tolerance


def _variant(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])


def _layer(doc: Any, name: str) -> LiveLayerEvidence:
    try:
        layer = doc.Layers.Item(name)
    except Exception as exc:
        raise ValueError(f"target layer is unavailable: {name}") from exc
    actual = str(layer.Name)
    state = LiveLayerEvidence(
        name=actual,
        color=int(layer.Color),
        linetype=str(layer.Linetype),
        locked=bool(layer.Lock),
        is_xref="|" in actual,
    )
    if state.locked or state.is_xref:
        raise ValueError(f"target layer is locked or xref-dependent: {name}")
    return state


def _circle(doc: Any, handle: str) -> tuple[LiveCircleEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"circle not found: {handle}")
    if str(entity.ObjectName).casefold() != "acdbcircle":
        raise ValueError("live CB source must be AcDbCircle")
    layer = str(entity.Layer)
    state = LiveCircleEvidence(
        handle=str(entity.Handle),
        center=_point(entity.Center),
        radius=float(entity.Radius),
        layer=layer,
        color=int(entity.Color),
        linetype=str(entity.Linetype),
        locked_layer=bool(doc.Layers.Item(layer).Lock),
        is_xref="|" in layer,
    )
    if state.locked_layer or state.is_xref:
        raise ValueError("live CB source circle is locked or xref-dependent")
    return state, entity


def _payload(alias: str, request: Any, **evidence: Any) -> dict[str, Any]:
    return {"command_alias": alias, "request": request.model_dump(mode="json"), **evidence}


def preview_live_cb(request: CircleBreakRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    circle, _entity = _circle(doc, request.source_handle)
    if circle.center != request.center or abs(circle.radius - request.radius) > 1e-9:
        raise ValueError("CB request center/radius do not match the source circle")
    plan = plan_circle_break(request)
    target_layer = _layer(doc, plan.create_arc.layer)
    payload = _payload(
        "CB",
        request,
        expected_circle=circle.model_dump(mode="json"),
        expected_target_layer=target_layer.model_dump(mode="json"),
    )
    return {
        **payload,
        "plan": plan.model_dump(mode="json"),
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
    }


def execute_live_cb(request: LiveCbExecuteRequest) -> LiveBatch19Result:
    payload = _payload(
        "CB",
        request.request,
        expected_circle=request.expected_circle.model_dump(mode="json"),
        expected_target_layer=request.expected_target_layer.model_dump(mode="json"),
    )
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact CB request")
    doc = _drawing(request.request.document_id)
    current, source = _circle(doc, request.expected_circle.handle)
    if current != request.expected_circle or _layer(doc, request.expected_target_layer.name) != request.expected_target_layer:
        raise ValueError("CB circle or target-layer state no longer matches the approved plan")
    plan = plan_circle_break(request.request)
    spec = plan.create_arc
    start = math.radians(spec.start_angle_degrees % 360)
    end = math.radians(spec.end_angle_degrees % 360)
    doc.StartUndoMark()
    try:
        arc = doc.ModelSpace.AddArc(_variant(spec.center), spec.radius, start, end)
        arc.Layer = spec.layer
        source.Delete()
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    if (
        str(arc.Handle).casefold() not in available
        or request.expected_circle.handle.casefold() in available
        or _point(arc.Center) != spec.center
        or abs(float(arc.Radius) - spec.radius) > 1e-9
        or not _angle_close(float(arc.StartAngle), start)
        or not _angle_close(float(arc.EndAngle), end)
        or str(arc.Layer).casefold() != spec.layer.casefold()
    ):
        raise RuntimeError("CB postcondition failed")
    return LiveBatch19Result(
        document_name=str(doc.Name),
        command_alias="CB",
        created_handles=(str(arc.Handle),),
        erased_handles=(request.expected_circle.handle,),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def _blocked(alias: str, request: Any, plan: Any, **evidence: Any) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    payload = _payload(alias, request, plan=plan.model_dump(mode="json"), **evidence)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "live_executable": False,
        "blocked_reason": BLOCKED[alias],
    }


def preview_live_hm(request: HatchMergeRequest, snapshots: tuple[HatchDefinition, ...]) -> dict[str, Any]:
    return _blocked("HM", request, plan_hatch_merge(request, snapshots), expected_hatches=[s.model_dump(mode="json") for s in snapshots])


def preview_live_hpm(request: HatchPatternRequest) -> dict[str, Any]:
    return _blocked("HPM", request, plan_hatch_pattern(request))


def preview_live_rds(request: RandomSolidRequest) -> dict[str, Any]:
    return _blocked("RDS", request, plan_random_solid(request))


def preview_live_sol(request: SolidHatchRequest) -> dict[str, Any]:
    return _blocked("SOL", request, plan_solid_hatch(request))


def preview_live_tb(request: TableRequest) -> dict[str, Any]:
    return _blocked("TB", request, plan_table(request))


def preview_live_tbt(request: TableTextRequest, snapshots: tuple[TableTextSnapshot, ...]) -> dict[str, Any]:
    return _blocked("TBT", request, plan_table_text(request, snapshots), expected_tables=[s.model_dump(mode="json") for s in snapshots])


def preview_live_bat(request: BreakAndTextRequest) -> dict[str, Any]:
    return _blocked("BAT", request, plan_break_and_text(request))


def preview_live_bb(request: BreakToCurrentRequest) -> dict[str, Any]:
    return _blocked("BB", request, plan_break_to_current(request))


def preview_live_bro(request: BreakOverRequest) -> dict[str, Any]:
    return _blocked("BRO", request, plan_break_over(request))


def preview_live_cut(request: CutterRequest) -> dict[str, Any]:
    return _blocked("CUT", request, plan_cutter(request))


def preview_live_dtp(request: DivideToPolylineRequest) -> dict[str, Any]:
    return _blocked("DTP", request, plan_divide_to_polyline(request))


def register_live_batch19_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(title="Preview live xiCAD Batch 19 operation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    execute = ToolAnnotations(title="Execute live xiCAD Batch 19 operation", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
    registrations = (
        ("xicad_preview_live_hm", preview_live_hm, preview),
        ("xicad_preview_live_hpm", preview_live_hpm, preview),
        ("xicad_preview_live_rds", preview_live_rds, preview),
        ("xicad_preview_live_sol", preview_live_sol, preview),
        ("xicad_preview_live_tb", preview_live_tb, preview),
        ("xicad_preview_live_tbt", preview_live_tbt, preview),
        ("xicad_preview_live_bat", preview_live_bat, preview),
        ("xicad_preview_live_bb", preview_live_bb, preview),
        ("xicad_preview_live_bro", preview_live_bro, preview),
        ("xicad_preview_live_cb", preview_live_cb, preview),
        ("xicad_execute_live_cb", execute_live_cb, execute),
        ("xicad_preview_live_cut", preview_live_cut, preview),
        ("xicad_preview_live_dtp", preview_live_dtp, preview),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
