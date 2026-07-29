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
    TableKind,
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


class LiveTableEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    handle: str
    row_count: int = Field(gt=0)
    column_count: int = Field(gt=0)
    layer: str
    locked_layer: bool
    is_xref: bool
    cells: tuple[tuple[int, int, str], ...]


class LiveTbExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: TableRequest
    expected_target_layer: LiveLayerEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveTbtExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: TableTextRequest
    expected_table: LiveTableEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBoundaryEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    handle: str
    object_name: str
    layer: str
    geometry: tuple[float, ...]
    locked_layer: bool
    is_xref: bool


class LiveSolExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: SolidHatchRequest
    expected_boundaries: tuple[LiveBoundaryEvidence, ...]
    expected_target_layer: LiveLayerEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch19Result(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    erased_handles: tuple[str, ...]
    changed_handles: tuple[str, ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


BLOCKED = {
    "HM": "merged hatch associativity and legacy property precedence are not recovered",
    "HPM": "PAT/file output and legacy geometry-to-pattern conversion are explicitly blocked",
    "RDS": "legacy random selection probability and seed algorithm are unrecovered",
    "SOL": "only closed top-level polyline/circle boundaries with one hatch per boundary are live",
    "TB": "CAD-table style, merged cells, and formatting are unspecified; general line tables are live",
    "TBT": "only explicit existing CAD-table cell writes are live; interactive traversal remains unsupported",
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


def _table(doc: Any, handle: str, cells: tuple[tuple[int, int], ...]) -> tuple[LiveTableEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None or str(entity.ObjectName).casefold() != "acdbtable":
        raise ValueError(f"TBT source must be an existing AcDbTable: {handle}")
    layer = str(entity.Layer)
    row_count, column_count = int(entity.Rows), int(entity.Columns)
    if any(row >= row_count or column >= column_count for row, column in cells):
        raise ValueError("TBT cell outside the live table bounds")
    state = LiveTableEvidence(
        handle=str(entity.Handle),
        row_count=row_count,
        column_count=column_count,
        layer=layer,
        locked_layer=bool(doc.Layers.Item(layer).Lock),
        is_xref="|" in layer,
        cells=tuple((row, column, str(entity.GetText(row, column))) for row, column in cells),
    )
    if state.locked_layer or state.is_xref:
        raise ValueError("TBT source table is locked or xref-dependent")
    return state, entity


def _boundary(doc: Any, handle: str) -> tuple[LiveBoundaryEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"SOL boundary not found: {handle}")
    object_name = str(entity.ObjectName)
    folded = object_name.casefold()
    if folded in {"acdbpolyline", "acdb2dpolyline"}:
        if not bool(entity.Closed):
            raise ValueError(f"SOL polyline boundary must be closed: {handle}")
        geometry = tuple(float(value) for value in entity.Coordinates) + (float(getattr(entity, "Elevation", 0.0)),)
    elif folded == "acdbcircle":
        geometry = tuple(float(value) for value in entity.Center) + (float(entity.Radius),)
    else:
        raise ValueError(f"SOL live boundary must be a closed polyline or circle: {handle}")
    layer = str(entity.Layer)
    state = LiveBoundaryEvidence(
        handle=str(entity.Handle),
        object_name=object_name,
        layer=layer,
        geometry=geometry,
        locked_layer=bool(doc.Layers.Item(layer).Lock),
        is_xref="|" in layer,
    )
    if state.locked_layer or state.is_xref:
        raise ValueError(f"SOL boundary is locked or xref-dependent: {handle}")
    return state, entity


def _dispatch_variant(entities: tuple[Any, ...]) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, entities)


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


def preview_live_sol(request: SolidHatchRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    boundaries = tuple(_boundary(doc, handle)[0] for handle in request.boundary_handles)
    target_layer = _layer(doc, request.layer)
    plan = plan_solid_hatch(request)
    payload = _payload(
        "SOL",
        request,
        expected_boundaries=[state.model_dump(mode="json") for state in boundaries],
        expected_target_layer=target_layer.model_dump(mode="json"),
        plan=plan.model_dump(mode="json"),
    )
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "official SOL result for separate closed polyline/circle boundaries",
        "legacy_equivalence_verified_in_cad": False,
    }


def execute_live_sol(request: LiveSolExecuteRequest) -> LiveBatch19Result:
    plan = plan_solid_hatch(request.request)
    payload = _payload(
        "SOL",
        request.request,
        expected_boundaries=[state.model_dump(mode="json") for state in request.expected_boundaries],
        expected_target_layer=request.expected_target_layer.model_dump(mode="json"),
        plan=plan.model_dump(mode="json"),
    )
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact SOL plan")
    doc = _drawing(request.request.document_id)
    current = tuple(_boundary(doc, state.handle) for state in request.expected_boundaries)
    if tuple(state for state, _entity in current) != request.expected_boundaries:
        raise ValueError("SOL boundary state no longer matches the approved preview")
    if _layer(doc, request.expected_target_layer.name) != request.expected_target_layer:
        raise ValueError("SOL target-layer state no longer matches the approved preview")
    by_handle = {state.handle.casefold(): entity for state, entity in current}
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        for spec in plan.creates:
            hatch = doc.ModelSpace.AddHatch(0, "SOLID", bool(spec.associative))
            hatch.AppendOuterLoop(_dispatch_variant((by_handle[spec.boundary_handle.casefold()],)))
            hatch.Layer = spec.layer
            hatch.Color = spec.color
            hatch.Evaluate()
            created.append(hatch)
    except Exception:
        for entity in reversed(created):
            entity.Delete()
        raise
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    if len(created) != len(plan.creates) or any(
        str(entity.Handle).casefold() not in available
        or str(entity.Layer).casefold() != request.request.layer.casefold()
        or int(entity.Color) != request.request.color
        or str(entity.PatternName).casefold() != "solid"
        for entity in created
    ):
        for entity in reversed(created):
            entity.Delete()
        raise RuntimeError("SOL postcondition failed; created hatches were rolled back")
    return LiveBatch19Result(
        document_name=str(doc.Name),
        command_alias="SOL",
        created_handles=tuple(str(entity.Handle) for entity in created),
        erased_handles=(),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def preview_live_tb(request: TableRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    if request.kind is not TableKind.GENERAL:
        return _blocked("TB", request, plan_table(request))
    doc = _drawing(request.document_id)
    target_layer = _layer(doc, request.layer)
    plan = plan_table(request)
    payload = _payload(
        "TB",
        request,
        expected_target_layer=target_layer.model_dump(mode="json"),
        plan=plan.model_dump(mode="json"),
    )
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "official TB general-table mode; explicit line grid only",
    }


def execute_live_tb(request: LiveTbExecuteRequest) -> LiveBatch19Result:
    if request.request.kind is not TableKind.GENERAL:
        raise ValueError("live TB currently supports only the official general line-table mode")
    plan = plan_table(request.request)
    payload = _payload(
        "TB",
        request.request,
        expected_target_layer=request.expected_target_layer.model_dump(mode="json"),
        plan=plan.model_dump(mode="json"),
    )
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact TB plan")
    doc = _drawing(request.request.document_id)
    if _layer(doc, request.expected_target_layer.name) != request.expected_target_layer:
        raise ValueError("TB target-layer state no longer matches the approved preview")
    origin = request.request.insertion_point
    x0, y0, z0 = origin.x, origin.y, origin.z
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        for offset in plan.x_offsets:
            line = doc.ModelSpace.AddLine(
                _variant(Point3D(x=x0 + offset, y=y0 + plan.y_offsets[0], z=z0)),
                _variant(Point3D(x=x0 + offset, y=y0 + plan.y_offsets[-1], z=z0)),
            )
            line.Layer = request.request.layer
            created.append(line)
        for offset in plan.y_offsets:
            line = doc.ModelSpace.AddLine(
                _variant(Point3D(x=x0 + plan.x_offsets[0], y=y0 + offset, z=z0)),
                _variant(Point3D(x=x0 + plan.x_offsets[-1], y=y0 + offset, z=z0)),
            )
            line.Layer = request.request.layer
            created.append(line)
    except Exception:
        for entity in reversed(created):
            entity.Delete()
        raise
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    if len(created) != len(plan.x_offsets) + len(plan.y_offsets) or any(
        str(entity.Handle).casefold() not in available
        or str(entity.Layer).casefold() != request.request.layer.casefold()
        for entity in created
    ):
        for entity in reversed(created):
            entity.Delete()
        raise RuntimeError("TB postcondition failed; created grid was rolled back")
    return LiveBatch19Result(
        document_name=str(doc.Name),
        command_alias="TB",
        created_handles=tuple(str(entity.Handle) for entity in created),
        erased_handles=(),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def preview_live_tbt(request: TableTextRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    positions = tuple((cell.row, cell.column) for cell in request.cells)
    expected_table, _entity = _table(doc, request.table_handle, positions)
    snapshot = TableTextSnapshot(
        handle=expected_table.handle,
        row_count=expected_table.row_count,
        column_count=expected_table.column_count,
        locked_layer=expected_table.locked_layer,
    )
    plan = plan_table_text(request, (snapshot,))
    if not request.overwrite_nonempty and any(value for _row, _column, value in expected_table.cells):
        raise ValueError("TBT overwrite_nonempty=false requires every selected live cell to be empty")
    payload = _payload(
        "TBT",
        request,
        expected_table=expected_table.model_dump(mode="json"),
        plan=plan.model_dump(mode="json"),
    )
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "official TBT explicit CAD-table cell text input; no interactive traversal",
    }


def execute_live_tbt(request: LiveTbtExecuteRequest) -> LiveBatch19Result:
    positions = tuple((cell.row, cell.column) for cell in request.request.cells)
    snapshot = TableTextSnapshot(
        handle=request.expected_table.handle,
        row_count=request.expected_table.row_count,
        column_count=request.expected_table.column_count,
        locked_layer=request.expected_table.locked_layer,
    )
    plan = plan_table_text(request.request, (snapshot,))
    payload = _payload(
        "TBT",
        request.request,
        expected_table=request.expected_table.model_dump(mode="json"),
        plan=plan.model_dump(mode="json"),
    )
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact TBT plan")
    doc = _drawing(request.request.document_id)
    current, entity = _table(doc, request.expected_table.handle, positions)
    if current != request.expected_table:
        raise ValueError("TBT table state no longer matches the approved preview")
    originals = {(row, column): value for row, column, value in request.expected_table.cells}
    doc.StartUndoMark()
    try:
        for cell in plan.cells:
            entity.SetText(cell.row, cell.column, cell.text)
    except Exception:
        for (row, column), value in originals.items():
            entity.SetText(row, column, value)
        raise
    finally:
        doc.EndUndoMark()
    if any(str(entity.GetText(cell.row, cell.column)) != cell.text for cell in plan.cells):
        for (row, column), value in originals.items():
            entity.SetText(row, column, value)
        raise RuntimeError("TBT postcondition failed; cell contents were rolled back")
    return LiveBatch19Result(
        document_name=str(doc.Name),
        command_alias="TBT",
        created_handles=(),
        changed_handles=(str(entity.Handle),),
        erased_handles=(),
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
        ("xicad_execute_live_sol", execute_live_sol, execute),
        ("xicad_preview_live_tb", preview_live_tb, preview),
        ("xicad_execute_live_tb", execute_live_tb, execute),
        ("xicad_preview_live_tbt", preview_live_tbt, preview),
        ("xicad_execute_live_tbt", execute_live_tbt, execute),
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
