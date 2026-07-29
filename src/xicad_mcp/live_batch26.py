from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch26a import (
    PolylineJoinRequest,
    PolylineWidthRequest,
    ProposedPolylineResult,
    VertexAddRequest,
    VertexDeleteRequest,
    VertexListTableRequest,
    VertexRemoveCleanRequest,
    plan_polyline_join,
    plan_polyline_width,
    plan_vertex_add,
    plan_vertex_delete,
    plan_vertex_list_table,
    plan_vertex_remove_clean,
)
from .headless_core_batch26a import (
    PolylineSnapshot as PolylineSnapshot26A,
)
from .headless_core_batch26b import (
    PolylineWidthOutlineRequest,
    RoundSurfaceRequest,
    SolidRectangleRequest,
    ThreePointRectangleRequest,
    UnfoldPolylineRequest,
    VSymbolRequest,
    plan_polyline_width_outline,
    plan_round_surface,
    plan_solid_rectangle,
    plan_three_point_rectangle,
    plan_unfold_polyline,
    plan_v_symbol,
)

ExecutableRequest = (
    PolylineJoinRequest
    | VertexAddRequest
    | VertexRemoveCleanRequest
    | VertexDeleteRequest
    | PolylineWidthRequest
    | ThreePointRectangleRequest
    | SolidRectangleRequest
    | VSymbolRequest
)


class LivePolylineEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    object_name: str
    layer: str
    color: int
    linetype: str
    linetype_scale: float
    lineweight: int
    topology_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    locked_layer: bool
    is_xref: bool


class LiveLayerEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    locked: bool
    is_xref: bool


class LiveBatch26ExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ExecutableRequest
    expected_sources: tuple[LivePolylineEvidence, ...]
    expected_target_layers: tuple[LiveLayerEvidence, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch26Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    changed_handles: tuple[str, ...]
    erased_handles: tuple[str, ...] = ()
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


BLOCKED = {
    "PVL": "compiled table columns, formatting, ordering, coordinate system, and table geometry are unrecovered",
    "PWD": "compiled offset joins/caps, outline topology, and source treatment are unrecovered",
    "RND": "compiled curve construction, view convention, primitive properties, and component count are unrecovered",
    "UFD": "compiled unfold direction, base point, bulge treatment, closed seam, and source treatment are unrecovered",
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


def _variant_points(points: tuple[Point3D, ...]) -> Any:
    import pythoncom
    import win32com.client

    values = [coordinate for point in points for coordinate in (point.x, point.y)]
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)


def _variant_point(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])


def _topology(entity: Any) -> dict[str, Any]:
    coordinates = tuple(float(value) for value in entity.Coordinates)
    count = len(coordinates) // 2
    bulges: list[float] = []
    widths: list[tuple[float, float]] = []
    for index in range(count):
        try:
            bulges.append(float(entity.GetBulge(index)))
        except Exception:
            bulges.append(0.0)
        try:
            start, end = entity.GetWidth(index)
            widths.append((float(start), float(end)))
        except Exception:
            widths.append((0.0, 0.0))
    return {
        "coordinates": coordinates,
        "bulges": tuple(bulges),
        "widths": tuple(widths),
        "closed": bool(entity.Closed),
        "layer": str(entity.Layer),
        "color": int(entity.Color),
        "linetype": str(entity.Linetype),
        "linetype_scale": float(entity.LinetypeScale),
        "lineweight": int(entity.Lineweight),
    }


def _polyline_evidence(doc: Any, handle: str) -> tuple[LivePolylineEvidence, Any]:
    entity = _entities(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"Batch 26 polyline does not exist: {handle}")
    if str(entity.ObjectName).casefold() not in {"acdbpolyline", "acdblwpolyline"}:
        raise ValueError(f"Batch 26 executable topology requires LWPOLYLINE: {handle}")
    layer = str(entity.Layer)
    locked = bool(doc.Layers.Item(layer).Lock)
    is_xref = "|" in layer
    if locked or is_xref:
        raise ValueError(f"Batch 26 polyline is locked or xref-dependent: {handle}")
    topology = _topology(entity)
    evidence = LivePolylineEvidence(
        handle=str(entity.Handle),
        object_name=str(entity.ObjectName),
        layer=layer,
        color=topology["color"],
        linetype=topology["linetype"],
        linetype_scale=topology["linetype_scale"],
        lineweight=topology["lineweight"],
        topology_fingerprint=_fingerprint(topology),
        locked_layer=locked,
        is_xref=is_xref,
    )
    return evidence, entity


def _layer(doc: Any, name: str) -> LiveLayerEvidence:
    try:
        layer = doc.Layers.Item(name)
    except Exception as exc:
        raise ValueError(f"Batch 26 target layer does not exist: {name}") from exc
    actual = str(layer.Name)
    state = LiveLayerEvidence(name=actual, locked=bool(layer.Lock), is_xref="|" in actual)
    if state.locked or state.is_xref:
        raise ValueError(f"Batch 26 target layer is locked or xref-dependent: {name}")
    return state


def _plan(request: Any) -> Any:
    planners = {
        PolylineJoinRequest: plan_polyline_join,
        VertexAddRequest: plan_vertex_add,
        VertexListTableRequest: plan_vertex_list_table,
        VertexRemoveCleanRequest: plan_vertex_remove_clean,
        VertexDeleteRequest: plan_vertex_delete,
        PolylineWidthRequest: plan_polyline_width,
        PolylineWidthOutlineRequest: plan_polyline_width_outline,
        ThreePointRectangleRequest: plan_three_point_rectangle,
        RoundSurfaceRequest: plan_round_surface,
        SolidRectangleRequest: plan_solid_rectangle,
        UnfoldPolylineRequest: plan_unfold_polyline,
        VSymbolRequest: plan_v_symbol,
    }
    for request_type, planner in planners.items():
        if isinstance(request, request_type):
            return planner(request)
    raise TypeError(f"unsupported Batch 26 request: {type(request).__name__}")


def _source_snapshots(request: ExecutableRequest) -> tuple[PolylineSnapshot26A, ...]:
    if isinstance(request, PolylineJoinRequest):
        return request.sources
    if isinstance(request, (VertexAddRequest, VertexRemoveCleanRequest, VertexDeleteRequest, PolylineWidthRequest)):
        return (request.source,)
    return ()


def _target_layers(request: ExecutableRequest) -> tuple[str, ...]:
    if isinstance(request, PolylineJoinRequest):
        return (request.exact_result.layer,)
    if isinstance(request, (VertexAddRequest, VertexRemoveCleanRequest, VertexDeleteRequest, PolylineWidthRequest)):
        return (request.exact_result.layer,)
    if isinstance(request, ThreePointRectangleRequest):
        return (request.exact_rectangle.layer,)
    return (request.layer,)


def _assert_snapshot(snapshot: PolylineSnapshot26A, entity: Any) -> None:
    if snapshot.entity_type != "LWPOLYLINE":
        raise ValueError("Batch 26 live mutation supports only explicit LWPOLYLINE snapshots")
    topology = _topology(entity)
    coordinates = tuple(value for vertex in snapshot.vertices for value in (vertex.point.x, vertex.point.y))
    bulges = tuple(vertex.bulge for vertex in snapshot.vertices)
    widths = tuple((vertex.start_width, vertex.end_width) for vertex in snapshot.vertices)
    if (
        topology["coordinates"] != coordinates
        or topology["bulges"] != bulges
        or topology["widths"] != widths
        or topology["closed"] is not snapshot.closed
        or topology["layer"].casefold() != snapshot.layer.casefold()
    ):
        raise ValueError(f"Batch 26 source topology does not match snapshot: {snapshot.handle}")


def _payload(
    request: ExecutableRequest,
    plan: Any,
    sources: tuple[LivePolylineEvidence, ...],
    layers: tuple[LiveLayerEvidence, ...],
) -> dict[str, Any]:
    return {
        "command_alias": plan.command_alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
        "expected_target_layers": [item.model_dump(mode="json") for item in layers],
    }


def _preview_executable(request: ExecutableRequest, expected_alias: str) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _plan(request)
    if plan.command_alias != expected_alias:
        raise ValueError(f"{expected_alias} preview received a different request type")
    doc = _drawing(request.document_id)
    pairs = tuple(_polyline_evidence(doc, item.handle) for item in _source_snapshots(request))
    for snapshot, (_, entity) in zip(_source_snapshots(request), pairs, strict=True):
        _assert_snapshot(snapshot, entity)
    sources = tuple(pair[0] for pair in pairs)
    layers = tuple(_layer(doc, name) for name in dict.fromkeys(_target_layers(request)))
    payload = _payload(request, plan, sources, layers)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "exact LWPOLYLINE topology or caller-approved primitive is stale-checked around one Undo group; legacy equivalence is not claimed",
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


def preview_live_pj(request: PolylineJoinRequest) -> dict[str, Any]:
    return _preview_executable(request, "PJ")


def preview_live_pv(request: VertexAddRequest) -> dict[str, Any]:
    return _preview_executable(request, "PV")


def preview_live_pvl(request: VertexListTableRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_pvr(request: VertexRemoveCleanRequest) -> dict[str, Any]:
    return _preview_executable(request, "PVR")


def preview_live_pvv(request: VertexDeleteRequest) -> dict[str, Any]:
    return _preview_executable(request, "PVV")


def preview_live_pw(request: PolylineWidthRequest) -> dict[str, Any]:
    return _preview_executable(request, "PW")


def preview_live_pwd(request: PolylineWidthOutlineRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_r3(request: ThreePointRectangleRequest) -> dict[str, Any]:
    return _preview_executable(request, "R3")


def preview_live_rnd(request: RoundSurfaceRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_rs(request: SolidRectangleRequest) -> dict[str, Any]:
    return _preview_executable(request, "RS")


def preview_live_ufd(request: UnfoldPolylineRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_v(request: VSymbolRequest) -> dict[str, Any]:
    return _preview_executable(request, "V")


def _apply_polyline(entity: Any, result: ProposedPolylineResult) -> None:
    entity.Coordinates = _variant_points(tuple(vertex.point for vertex in result.vertices))
    entity.Layer = result.layer
    entity.Closed = result.closed
    for index, vertex in enumerate(result.vertices):
        entity.SetBulge(index, vertex.bulge)
        entity.SetWidth(index, vertex.start_width, vertex.end_width)


def _add_polyline(doc: Any, points: tuple[Point3D, ...], layer: str, closed: bool) -> Any:
    entity = doc.ModelSpace.AddLightWeightPolyline(_variant_points(points))
    entity.Layer = layer
    entity.Closed = closed
    return entity


def _solid_points(entity: Any) -> tuple[tuple[float, float, float], ...]:
    try:
        values = tuple(float(value) for value in entity.Coordinates)
        if len(values) == 12:
            return tuple((values[index], values[index + 1], values[index + 2]) for index in range(0, 12, 3))
    except Exception:
        pass
    coordinate = entity.Coordinate
    return tuple(
        tuple(float(value) for value in (coordinate(index) if callable(coordinate) else coordinate[index]))
        for index in range(4)
    )


def execute_live_batch26(request: LiveBatch26ExecuteRequest) -> LiveBatch26Result:
    plan = _plan(request.request)
    payload = _payload(request.request, plan, request.expected_sources, request.expected_target_layers)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 26 preview")
    doc = _drawing(request.request.document_id)
    snapshots = _source_snapshots(request.request)
    current_pairs = tuple(_polyline_evidence(doc, item.handle) for item in snapshots)
    if tuple(pair[0] for pair in current_pairs) != request.expected_sources:
        raise ValueError("Batch 26 source state no longer matches the approved preview")
    for snapshot, (_, entity) in zip(snapshots, current_pairs, strict=True):
        _assert_snapshot(snapshot, entity)
    if tuple(_layer(doc, item.name) for item in request.expected_target_layers) != request.expected_target_layers:
        raise ValueError("Batch 26 target-layer state no longer matches the approved preview")

    created: list[Any] = []
    changed: list[Any] = []
    erased_handles: list[str] = []
    expected_polyline: tuple[Any, tuple[Point3D, ...], str, bool] | None = None
    expected_solid: tuple[Any, tuple[Point3D, ...], str, int | None] | None = None
    doc.StartUndoMark()
    try:
        if plan.command_alias == "PJ":
            exact = request.request.exact_result
            entity = _add_polyline(
                doc,
                tuple(vertex.point for vertex in exact.vertices),
                exact.layer,
                exact.closed,
            )
            for index, vertex in enumerate(exact.vertices):
                entity.SetBulge(index, vertex.bulge)
                entity.SetWidth(index, vertex.start_width, vertex.end_width)
            created.append(entity)
            expected_polyline = (
                entity,
                tuple(vertex.point for vertex in exact.vertices),
                exact.layer,
                exact.closed,
            )
            delete_set = {handle.casefold() for handle in plan.delete_source_handles}
            for evidence, source in current_pairs:
                if evidence.handle.casefold() in delete_set:
                    erased_handles.append(str(source.Handle))
                    source.Delete()
        elif plan.command_alias in {"PV", "PVR", "PVV", "PW"}:
            entity = current_pairs[0][1]
            _apply_polyline(entity, request.request.exact_result)
            changed.append(entity)
        elif plan.command_alias == "R3":
            entity = _add_polyline(doc, plan.rectangle.vertices, plan.rectangle.layer, True)
            created.append(entity)
            expected_polyline = (entity, plan.rectangle.vertices, plan.rectangle.layer, True)
        elif plan.command_alias == "V":
            entity = _add_polyline(doc, plan.vertices, plan.layer, False)
            created.append(entity)
            expected_polyline = (entity, plan.vertices, plan.layer, False)
        elif plan.command_alias == "RS":
            points = plan.solid_vertices
            entity = doc.ModelSpace.AddSolid(*(_variant_point(point) for point in points))
            entity.Layer = plan.layer
            if plan.color_index is not None:
                entity.Color = plan.color_index
            created.append(entity)
            expected_solid = (entity, points, plan.layer, plan.color_index)
        else:
            raise ValueError(f"Batch 26 live execution is not exposed for {plan.command_alias}")
    finally:
        doc.EndUndoMark()

    available = _entities(doc)
    if any(str(item.Handle).casefold() not in available for item in created + changed):
        raise RuntimeError(f"{plan.command_alias} postcondition failed: output entity is missing")
    if any(handle.casefold() in available for handle in erased_handles):
        raise RuntimeError(f"{plan.command_alias} postcondition failed: source entity was not erased")
    if changed:
        expected = request.request.exact_result
        entity = changed[0]
        expected_topology = {
            "coordinates": tuple(value for vertex in expected.vertices for value in (vertex.point.x, vertex.point.y)),
            "bulges": tuple(vertex.bulge for vertex in expected.vertices),
            "widths": tuple((vertex.start_width, vertex.end_width) for vertex in expected.vertices),
            "closed": expected.closed,
            "layer": expected.layer,
        }
        actual = _topology(entity)
        if any(actual[key] != value for key, value in expected_topology.items()):
            raise RuntimeError(f"{plan.command_alias} postcondition failed: topology differs")
        approved = request.expected_sources[0]
        if (
            int(entity.Color) != approved.color
            or str(entity.Linetype) != approved.linetype
            or float(entity.LinetypeScale) != approved.linetype_scale
            or int(entity.Lineweight) != approved.lineweight
        ):
            raise RuntimeError(f"{plan.command_alias} postcondition failed: non-topology properties changed")
    if expected_polyline is not None:
        entity, points, layer, closed = expected_polyline
        coordinates = tuple(float(value) for value in entity.Coordinates)
        expected_coordinates = tuple(value for point in points for value in (point.x, point.y))
        if (
            coordinates != expected_coordinates
            or bool(entity.Closed) is not closed
            or str(entity.Layer).casefold() != layer.casefold()
        ):
            raise RuntimeError(f"{plan.command_alias} postcondition failed: polyline differs")
    if expected_solid is not None:
        entity, points, layer, color = expected_solid
        actual_points = _solid_points(entity)
        expected_points = tuple((point.x, point.y, point.z) for point in points)
        if (
            actual_points != expected_points
            or str(entity.Layer).casefold() != layer.casefold()
            or (color is not None and int(entity.Color) != color)
        ):
            raise RuntimeError("RS postcondition failed: solid properties differ")
    return LiveBatch26Result(
        document_name=str(doc.Name),
        command_alias=plan.command_alias,
        created_handles=tuple(str(item.Handle) for item in created),
        changed_handles=tuple(str(item.Handle) for item in changed),
        erased_handles=tuple(erased_handles),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_batch26_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 26 operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 26 operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    functions = {
        "pj": preview_live_pj,
        "pv": preview_live_pv,
        "pvl": preview_live_pvl,
        "pvr": preview_live_pvr,
        "pvv": preview_live_pvv,
        "pw": preview_live_pw,
        "pwd": preview_live_pwd,
        "r3": preview_live_r3,
        "rnd": preview_live_rnd,
        "rs": preview_live_rs,
        "ufd": preview_live_ufd,
        "v": preview_live_v,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
        if alias.upper() not in BLOCKED:
            mcp.tool(name=f"xicad_execute_live_{alias}", annotations=execute)(execute_live_batch26)
