"""Help-verified, line-bounded live adapters for xiCAD batches 19 and 20.

Only operations whose public xiCAD behavior can be reproduced exactly from
the existing structured contract are executable here:

* BAT ``POSITION`` mode for AcDbLine sources
* BB for one AcDbLine source
* BRO for AcDbLine targets and cutters

The other requested aliases remain intentionally absent.  In particular, the
current RDS contract models explicit boundary selection, while the public help
defines random assignment from at least three existing hatch colours.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch19b import (
    BatPlacementMode,
    BreakAndTextRequest,
    BreakOverRequest,
    BreakToCurrentRequest,
    plan_break_and_text,
    plan_break_over,
    plan_break_to_current,
)

XI_HELP_BAT = "https://izzarder.com/487"
XI_HELP_BB = "https://izzarder.com/412"
XI_HELP_BRO = "https://izzarder.com/415"

_EPSILON = 1e-8


class LiveLineEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    handle: str = Field(min_length=1)
    start: Point3D
    end: Point3D
    layer: str = Field(min_length=1)
    color: int
    linetype: str = Field(min_length=1)
    lineweight: int
    thickness: float
    locked_layer: bool
    is_xref: bool


class LiveLinePart(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    source_handle: str = Field(min_length=1)
    start: Point3D
    end: Point3D
    layer: str = Field(min_length=1)


class LiveTextPart(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    source_handle: str = Field(min_length=1)
    insertion_point: Point3D
    text: str = Field(min_length=1)
    height: float = Field(gt=0)
    rotation_degrees: float
    layer: str = Field(min_length=1)


class LiveBatExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request: BreakAndTextRequest
    expected_sources: tuple[LiveLineEvidence, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBbExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request: BreakToCurrentRequest
    expected_source: LiveLineEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBroExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request: BreakOverRequest
    expected_target: LiveLineEvidence
    expected_cutters: tuple[LiveLineEvidence, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveGap1920Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    erased_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    rollback_performed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _drawing(name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [document for document in app.Documents if str(document.Name).casefold() == name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _modelspace_entities(doc: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for entity in doc.ModelSpace:
        handle = str(entity.Handle)
        if handle.casefold() in result:
            raise RuntimeError(f"duplicate ModelSpace handle: {handle}")
        result[handle.casefold()] = entity
    return result


def _point(value: Any) -> Point3D:
    values = tuple(float(item) for item in value)
    return Point3D(x=values[0], y=values[1], z=values[2])


def _variant(point: Point3D) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        [point.x, point.y, point.z],
    )


def _layer_state(doc: Any, name: str) -> tuple[bool, bool]:
    try:
        layer = doc.Layers.Item(name)
    except Exception as exc:
        raise ValueError(f"required layer does not exist: {name}") from exc
    actual = str(layer.Name)
    return bool(layer.Lock), "|" in actual


def _line(doc: Any, handle: str) -> tuple[LiveLineEvidence, Any]:
    entity = _modelspace_entities(doc).get(handle.casefold())
    if entity is None:
        raise ValueError(f"line does not exist in ModelSpace: {handle}")
    if str(entity.ObjectName).casefold() != "acdbline":
        raise ValueError(f"this bounded live adapter requires AcDbLine: {handle}")
    layer = str(entity.Layer)
    locked, is_xref = _layer_state(doc, layer)
    state = LiveLineEvidence(
        handle=str(entity.Handle),
        start=_point(entity.StartPoint),
        end=_point(entity.EndPoint),
        layer=layer,
        color=int(entity.Color),
        linetype=str(entity.Linetype),
        lineweight=int(entity.Lineweight),
        thickness=float(entity.Thickness),
        locked_layer=locked,
        is_xref=is_xref,
    )
    if state.start == state.end:
        raise ValueError(f"zero-length source line is not executable: {handle}")
    if locked or is_xref:
        raise ValueError(f"line is locked or xref-dependent: {handle}")
    return state, entity


def _require_target_layer(doc: Any, name: str) -> None:
    locked, is_xref = _layer_state(doc, name)
    if locked or is_xref:
        raise ValueError(f"target layer is locked or xref-dependent: {name}")


def _distance(left: Point3D, right: Point3D) -> float:
    return math.dist((left.x, left.y, left.z), (right.x, right.y, right.z))


def _at(line: LiveLineEvidence, parameter: float) -> Point3D:
    return Point3D(
        x=line.start.x + (line.end.x - line.start.x) * parameter,
        y=line.start.y + (line.end.y - line.start.y) * parameter,
        z=line.start.z + (line.end.z - line.start.z) * parameter,
    )


def _parameter(line: LiveLineEvidence, point: Point3D) -> float:
    vector = (
        line.end.x - line.start.x,
        line.end.y - line.start.y,
        line.end.z - line.start.z,
    )
    delta = (point.x - line.start.x, point.y - line.start.y, point.z - line.start.z)
    denominator = sum(value * value for value in vector)
    parameter = sum(left * right for left, right in zip(delta, vector, strict=True)) / denominator
    projected = _at(line, parameter)
    tolerance = max(_EPSILON, math.sqrt(denominator) * 1e-8)
    if _distance(projected, point) > tolerance or parameter < -_EPSILON or parameter > 1 + _EPSILON:
        raise ValueError(f"point is not on finite source line {line.handle}: {point}")
    return min(1.0, max(0.0, parameter))


def _parts_outside_intervals(
    line: LiveLineEvidence,
    intervals: list[tuple[float, float]],
    *,
    layer: str | None = None,
) -> tuple[LiveLinePart, ...]:
    ordered = sorted(intervals)
    if any(low < -_EPSILON or high > 1 + _EPSILON or high < low for low, high in ordered):
        raise ValueError(f"break interval is outside source line: {line.handle}")
    if any(right[0] < left[1] - _EPSILON for left, right in zip(ordered, ordered[1:], strict=False)):
        raise ValueError(f"break intervals overlap on source line: {line.handle}")
    parameters = [0.0]
    for low, high in ordered:
        parameters.extend((max(0.0, low), min(1.0, high)))
    parameters.append(1.0)
    return tuple(
        LiveLinePart(
            source_handle=line.handle,
            start=_at(line, start),
            end=_at(line, end),
            layer=layer or line.layer,
        )
        for start, end in zip(parameters[::2], parameters[1::2], strict=True)
        if end - start > _EPSILON
    )


def _gap_interval(line: LiveLineEvidence, center: Point3D, gap: float) -> tuple[float, float]:
    parameter = _parameter(line, center)
    length = _distance(line.start, line.end)
    half = gap / (2 * length)
    return parameter - half, parameter + half


def _cross(left: tuple[float, float], right: tuple[float, float]) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _line_intersection(left: LiveLineEvidence, right: LiveLineEvidence) -> Point3D:
    if abs(left.start.z - left.end.z) > _EPSILON or abs(right.start.z - right.end.z) > _EPSILON:
        raise ValueError("BRO bounded execution supports coplanar XY lines only")
    p = (left.start.x, left.start.y)
    r = (left.end.x - left.start.x, left.end.y - left.start.y)
    q = (right.start.x, right.start.y)
    s = (right.end.x - right.start.x, right.end.y - right.start.y)
    denominator = _cross(r, s)
    if abs(denominator) <= _EPSILON:
        raise ValueError("BRO cutters must intersect the target at a single point")
    qp = (q[0] - p[0], q[1] - p[1])
    t = _cross(qp, s) / denominator
    u = _cross(qp, r) / denominator
    if not (-_EPSILON <= t <= 1 + _EPSILON and -_EPSILON <= u <= 1 + _EPSILON):
        raise ValueError("BRO cutter does not intersect the finite target")
    return Point3D(x=p[0] + t * r[0], y=p[1] + t * r[1], z=left.start.z)


def _bat_parts(
    request: BreakAndTextRequest,
    sources: tuple[LiveLineEvidence, ...],
) -> tuple[tuple[LiveLinePart, ...], tuple[LiveTextPart, ...]]:
    if request.placement_mode is not BatPlacementMode.POSITION:
        raise ValueError("bounded BAT live execution supports official POSITION/AcDbLine mode only")
    by_handle = {item.handle.casefold(): item for item in sources}
    intervals: dict[str, list[tuple[float, float]]] = defaultdict(list)
    texts: list[LiveTextPart] = []
    for station in request.stations:
        line = by_handle.get(station.source_handle.casefold())
        if line is None:
            raise ValueError(f"BAT station source was not captured: {station.source_handle}")
        intervals[line.handle.casefold()].append(_gap_interval(line, station.break_center, request.break_gap))
        texts.append(
            LiveTextPart(
                source_handle=line.handle,
                insertion_point=station.text_point,
                text=request.text,
                height=request.text_height,
                rotation_degrees=station.rotation_degrees,
                layer=request.text_layer,
            )
        )
    parts = tuple(
        part for line in sources for part in _parts_outside_intervals(line, intervals[line.handle.casefold()])
    )
    return parts, tuple(texts)


def _bb_parts(request: BreakToCurrentRequest, source: LiveLineEvidence) -> tuple[LiveLinePart, ...]:
    first = _parameter(source, request.first_break_point)
    second = _parameter(source, request.second_break_point)
    low, high = sorted((first, second))
    if high - low <= _EPSILON:
        raise ValueError("BB break points collapse within line tolerance")
    parts: list[LiveLinePart] = []
    if low > _EPSILON:
        parts.append(
            LiveLinePart(
                source_handle=source.handle,
                start=source.start,
                end=_at(source, low),
                layer=source.layer,
            )
        )
    parts.append(
        LiveLinePart(
            source_handle=source.handle,
            start=_at(source, low),
            end=_at(source, high),
            layer=request.current_layer,
        )
    )
    if high < 1 - _EPSILON:
        parts.append(
            LiveLinePart(
                source_handle=source.handle,
                start=_at(source, high),
                end=source.end,
                layer=source.layer,
            )
        )
    return tuple(parts)


def _bro_parts(
    request: BreakOverRequest,
    target: LiveLineEvidence,
    cutters: tuple[LiveLineEvidence, ...],
) -> tuple[LiveLinePart, ...]:
    actual = tuple(_line_intersection(target, cutter) for cutter in cutters)
    requested = request.intersection_points
    if len(actual) != len(requested):
        raise ValueError("BRO requires exactly one intersection point per cutter")
    unmatched = list(actual)
    tolerance = max(_EPSILON, _distance(target.start, target.end) * 1e-8)
    for point in requested:
        match = next((item for item in unmatched if _distance(item, point) <= tolerance), None)
        if match is None:
            raise ValueError("BRO caller intersection does not match target/cutter geometry")
        unmatched.remove(match)
    intervals = [_gap_interval(target, point, request.gap) for point in requested]
    return _parts_outside_intervals(target, intervals)


def _payload(
    alias: str,
    request: Any,
    sources: tuple[LiveLineEvidence, ...],
    lines: tuple[LiveLinePart, ...],
    texts: tuple[LiveTextPart, ...] = (),
) -> dict[str, Any]:
    return {
        "command_alias": alias,
        "request": request.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
        "output_lines": [item.model_dump(mode="json") for item in lines],
        "output_texts": [item.model_dump(mode="json") for item in texts],
        "semantic_evidence": {
            "BAT": XI_HELP_BAT,
            "BB": XI_HELP_BB,
            "BRO": XI_HELP_BRO,
        }[alias],
    }


def _require_dry_run(request: Any) -> None:
    if not request.dry_run:
        raise ValueError("live preview and execution wrapper require the structured request in dry-run mode")


def preview_live_bat(request: BreakAndTextRequest) -> dict[str, Any]:
    _require_dry_run(request)
    plan_break_and_text(request)
    doc = _drawing(request.document_id)
    _require_target_layer(doc, request.text_layer)
    handles = tuple(dict.fromkeys(station.source_handle.casefold() for station in request.stations))
    sources = tuple(_line(doc, handle)[0] for handle in handles)
    lines, texts = _bat_parts(request, sources)
    payload = _payload("BAT", request, sources, lines, texts)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "official BAT POSITION mode; AcDbLine sources; exact gap/text geometry",
    }


def preview_live_bb(request: BreakToCurrentRequest) -> dict[str, Any]:
    _require_dry_run(request)
    plan_break_to_current(request)
    doc = _drawing(request.document_id)
    _require_target_layer(doc, request.current_layer)
    source = _line(doc, request.source_handle)[0]
    lines = _bb_parts(request, source)
    payload = _payload("BB", request, (source,), lines)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "official BB for AcDbLine; middle segment moves to current layer",
    }


def preview_live_bro(request: BreakOverRequest) -> dict[str, Any]:
    _require_dry_run(request)
    plan_break_over(request)
    doc = _drawing(request.document_id)
    target = _line(doc, request.target_handle)[0]
    cutters = tuple(_line(doc, handle)[0] for handle in request.cutter_handles)
    lines = _bro_parts(request, target, cutters)
    payload = _payload("BRO", request, (target, *cutters), lines)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "official BRO for finite coplanar AcDbLine target/cutters",
    }


def _apply_line_properties(entity: Any, source: LiveLineEvidence, layer: str) -> None:
    entity.Layer = layer
    entity.Color = source.color
    entity.Linetype = source.linetype
    entity.Lineweight = source.lineweight
    entity.Thickness = source.thickness


def _restore_sources(doc: Any, sources: tuple[LiveLineEvidence, ...]) -> list[str]:
    restored: list[str] = []
    existing = _modelspace_entities(doc)
    for source in sources:
        if source.handle.casefold() in existing:
            continue
        entity = doc.ModelSpace.AddLine(_variant(source.start), _variant(source.end))
        _apply_line_properties(entity, source, source.layer)
        restored.append(str(entity.Handle))
    return restored


def _rollback(doc: Any, created: list[Any], sources: tuple[LiveLineEvidence, ...]) -> None:
    errors: list[str] = []
    for entity in reversed(created):
        try:
            entity.Delete()
        except Exception as exc:
            errors.append(f"delete created {getattr(entity, 'Handle', '?')}: {exc}")
    try:
        _restore_sources(doc, sources)
    except Exception as exc:
        errors.append(f"restore sources: {exc}")
    if errors:
        raise RuntimeError("line-operation rollback was incomplete: " + "; ".join(errors))


def _execute(
    *,
    alias: str,
    document_name: str,
    request: Any,
    expected_sources: tuple[LiveLineEvidence, ...],
    expected_fingerprint: str,
    planned_lines: tuple[LiveLinePart, ...],
    planned_texts: tuple[LiveTextPart, ...] = (),
    erased_handles: tuple[str, ...],
) -> LiveGap1920Result:
    payload = _payload(alias, request, expected_sources, planned_lines, planned_texts)
    if expected_fingerprint != _fingerprint(payload):
        raise ValueError(f"{alias} approval fingerprint does not match exact source/output state")
    doc = _drawing(document_name)
    current_pairs = tuple(_line(doc, item.handle) for item in expected_sources)
    if tuple(item[0] for item in current_pairs) != expected_sources:
        raise ValueError(f"{alias} source state is stale")
    source_by_handle = {item.handle.casefold(): item for item in expected_sources}
    created: list[Any] = []
    deleted: list[Any] = []
    opened = False
    closed = False
    rollback = False
    doc.StartUndoMark()
    opened = True
    try:
        for spec in planned_lines:
            source = source_by_handle[spec.source_handle.casefold()]
            entity = doc.ModelSpace.AddLine(_variant(spec.start), _variant(spec.end))
            _apply_line_properties(entity, source, spec.layer)
            created.append(entity)
        for spec in planned_texts:
            entity = doc.ModelSpace.AddText(spec.text, _variant(spec.insertion_point), spec.height)
            entity.Layer = spec.layer
            entity.Rotation = math.radians(spec.rotation_degrees)
            created.append(entity)
        current_entities = _modelspace_entities(doc)
        for handle in erased_handles:
            entity = current_entities.get(handle.casefold())
            if entity is None:
                raise RuntimeError(f"{alias} source vanished during execution: {handle}")
            entity.Delete()
            deleted.append(entity)

        available = _modelspace_entities(doc)
        for entity, spec in zip(created[: len(planned_lines)], planned_lines, strict=True):
            source = source_by_handle[spec.source_handle.casefold()]
            if (
                str(entity.Handle).casefold() not in available
                or _point(entity.StartPoint) != spec.start
                or _point(entity.EndPoint) != spec.end
                or str(entity.Layer).casefold() != spec.layer.casefold()
                or int(entity.Color) != source.color
                or str(entity.Linetype).casefold() != source.linetype.casefold()
                or int(entity.Lineweight) != source.lineweight
                or abs(float(entity.Thickness) - source.thickness) > _EPSILON
            ):
                raise RuntimeError(f"{alias} line postcondition failed")
        for entity, spec in zip(created[len(planned_lines) :], planned_texts, strict=True):
            if (
                str(entity.Handle).casefold() not in available
                or str(entity.TextString) != spec.text
                or _point(entity.InsertionPoint) != spec.insertion_point
                or abs(float(entity.Height) - spec.height) > _EPSILON
                or abs(float(entity.Rotation) - math.radians(spec.rotation_degrees)) > _EPSILON
                or str(entity.Layer).casefold() != spec.layer.casefold()
            ):
                raise RuntimeError(f"{alias} text postcondition failed")
        if any(handle.casefold() in available for handle in erased_handles):
            raise RuntimeError(f"{alias} erase postcondition failed")
    except Exception:
        rollback = True
        _rollback(doc, created, expected_sources if deleted else ())
        raise
    finally:
        doc.EndUndoMark()
        closed = True
    return LiveGap1920Result(
        document_name=str(doc.Name),
        command_alias=alias,
        created_handles=tuple(str(entity.Handle) for entity in created),
        erased_handles=erased_handles,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
        rollback_performed=rollback,
        postcondition_verified=True,
    )


def execute_live_bat(request: LiveBatExecuteRequest) -> LiveGap1920Result:
    _require_dry_run(request.request)
    lines, texts = _bat_parts(request.request, request.expected_sources)
    erased = tuple(dict.fromkeys(item.handle for item in request.expected_sources))
    return _execute(
        alias="BAT",
        document_name=request.request.document_id,
        request=request.request,
        expected_sources=request.expected_sources,
        expected_fingerprint=request.approval_fingerprint,
        planned_lines=lines,
        planned_texts=texts,
        erased_handles=erased,
    )


def execute_live_bb(request: LiveBbExecuteRequest) -> LiveGap1920Result:
    _require_dry_run(request.request)
    lines = _bb_parts(request.request, request.expected_source)
    return _execute(
        alias="BB",
        document_name=request.request.document_id,
        request=request.request,
        expected_sources=(request.expected_source,),
        expected_fingerprint=request.approval_fingerprint,
        planned_lines=lines,
        erased_handles=(request.expected_source.handle,),
    )


def execute_live_bro(request: LiveBroExecuteRequest) -> LiveGap1920Result:
    _require_dry_run(request.request)
    lines = _bro_parts(request.request, request.expected_target, request.expected_cutters)
    return _execute(
        alias="BRO",
        document_name=request.request.document_id,
        request=request.request,
        expected_sources=(request.expected_target, *request.expected_cutters),
        expected_fingerprint=request.approval_fingerprint,
        planned_lines=lines,
        erased_handles=(request.expected_target.handle,),
    )


def register_live_gap_19_20_next_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview help-verified xiCAD line mutation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute help-verified xiCAD line mutation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    for name, function, tool_annotations in (
        ("xicad_preview_live_bat_exact", preview_live_bat, preview),
        ("xicad_execute_live_bat_exact", execute_live_bat, execute),
        ("xicad_preview_live_bb_exact", preview_live_bb, preview),
        ("xicad_execute_live_bb_exact", execute_live_bb, execute),
        ("xicad_preview_live_bro_exact", preview_live_bro, preview),
        ("xicad_execute_live_bro_exact", execute_live_bro, execute),
    ):
        mcp.tool(name=name, annotations=tool_annotations)(function)
