from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Point3D
from .headless_core_batch24a import (
    DistanceMemoryRequest,
    DynamicAreaRequest,
    EnergyElevationRequest,
    FindFieldObjectsRequest,
    NorthReviewRequest,
    RectangleAreaLabelRequest,
    TextAnchor,
    plan_check_dist_north,
    plan_distance_memory,
    plan_draw_energy_elevation,
    plan_dynamic_area,
    plan_find_field_objects,
    plan_rectangle_area_label,
)
from .headless_core_batch24b import (
    AnnotationMode,
    HwAreaRequest,
    MakeAreaCenterRequest,
    RoomTableRequest,
    ScaleAreaRequest,
    SelectSameRequest,
    SiteAreaRequest,
    plan_hw_area,
    plan_make_area_center,
    plan_room_table,
    plan_scale_area,
    plan_select_same,
    plan_site_area,
)

ExecutableRequest = RectangleAreaLabelRequest | HwAreaRequest


class LiveEntityEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    object_name: str
    layer: str
    geometry_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    locked_layer: bool
    is_xref: bool


class LiveTextEvidence(LiveEntityEvidence):
    text: str
    height: float
    insertion_point: Point3D


class LiveLayerEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    locked: bool
    is_xref: bool


class LiveBatch24ExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ExecutableRequest
    expected_sources: tuple[LiveEntityEvidence, ...]
    expected_replacement_text: LiveTextEvidence | None = None
    expected_target_layer: LiveLayerEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch24Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    changed_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


BLOCKED = {
    "CDN": "compiled legal north-daylight calculation, building discovery, and compliance decision are unrecovered",
    "DAR": "legacy dynamic FIELD expression, accepted source types, and number formatting are unrecovered",
    "DEE": "energy-standard interpretation and compiled elevation graphic construction are unrecovered",
    "DM": "legacy memory location, persistence lifetime, and serialization are unrecovered; the planner result is CAD-free",
    "FFO": "FIELD-code parsing, object-ID resolution, and highlight lifetime/style are unrecovered",
    "MAC": "centerline-to-boundary recognition, layer toggling, and basis-table geometry are unrecovered",
    "MRT": "room recognition, exclusion extraction, live FIELD linkage, and exact table geometry are unrecovered",
    "SAR": "survey component recognition, ordering geometry, and calculation-table layout are unrecovered",
    "SCA": "legacy scale meaning, anchor, source retention, and geometry algorithm are unrecovered",
    "SE": "selection-set side effects, nested-block scope, and several legacy comparison modes are unrecovered",
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


def _json_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return [_json_value(item) for item in value]
    except TypeError:
        return str(value)


def _geometry_fingerprint(item: Any) -> str:
    payload: dict[str, Any] = {}
    for name in (
        "Coordinates",
        "StartPoint",
        "EndPoint",
        "Center",
        "Radius",
        "StartAngle",
        "EndAngle",
        "Closed",
        "Area",
        "Length",
    ):
        try:
            payload[name] = _json_value(getattr(item, name))
        except Exception:
            continue
    return _fingerprint(payload)


def _entity(doc: Any, handle: str) -> tuple[LiveEntityEvidence, Any]:
    item = _entities(doc).get(handle.casefold())
    if item is None:
        raise ValueError(f"Batch 24 entity does not exist: {handle}")
    layer = str(item.Layer)
    locked = bool(doc.Layers.Item(layer).Lock)
    is_xref = "|" in layer
    if locked or is_xref:
        raise ValueError(f"Batch 24 entity is locked or xref-dependent: {handle}")
    return (
        LiveEntityEvidence(
            handle=str(item.Handle),
            object_name=str(item.ObjectName),
            layer=layer,
            geometry_fingerprint=_geometry_fingerprint(item),
            locked_layer=locked,
            is_xref=is_xref,
        ),
        item,
    )


def _text(doc: Any, handle: str) -> tuple[LiveTextEvidence, Any]:
    state, item = _entity(doc, handle)
    if state.object_name.casefold() not in {"acdbtext", "acdbmtext"}:
        raise ValueError(f"HW replacement requires AcDbText or AcDbMText: {handle}")
    return (
        LiveTextEvidence(
            **state.model_dump(),
            text=str(item.TextString),
            height=float(item.Height),
            insertion_point=_point(item.InsertionPoint),
        ),
        item,
    )


def _layer(doc: Any, name: str) -> LiveLayerEvidence:
    try:
        layer = doc.Layers.Item(name)
    except Exception as exc:
        raise ValueError(f"Batch 24 target layer does not exist: {name}") from exc
    actual = str(layer.Name)
    result = LiveLayerEvidence(name=actual, locked=bool(layer.Lock), is_xref="|" in actual)
    if result.locked or result.is_xref:
        raise ValueError(f"Batch 24 target layer is locked or xref-dependent: {name}")
    return result


def _plan(request: Any) -> Any:
    planners = {
        NorthReviewRequest: plan_check_dist_north,
        DynamicAreaRequest: plan_dynamic_area,
        EnergyElevationRequest: plan_draw_energy_elevation,
        DistanceMemoryRequest: plan_distance_memory,
        FindFieldObjectsRequest: plan_find_field_objects,
        RectangleAreaLabelRequest: plan_rectangle_area_label,
        HwAreaRequest: plan_hw_area,
        MakeAreaCenterRequest: plan_make_area_center,
        RoomTableRequest: plan_room_table,
        SiteAreaRequest: plan_site_area,
        ScaleAreaRequest: plan_scale_area,
        SelectSameRequest: plan_select_same,
    }
    for request_type, planner in planners.items():
        if isinstance(request, request_type):
            return planner(request)
    raise TypeError(f"unsupported Batch 24 request: {type(request).__name__}")


def _payload(
    request: ExecutableRequest,
    plan: Any,
    sources: tuple[LiveEntityEvidence, ...],
    replacement: LiveTextEvidence | None,
    layer: LiveLayerEvidence,
) -> dict[str, Any]:
    return {
        "command_alias": plan.command_alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_sources": [item.model_dump(mode="json") for item in sources],
        "expected_replacement_text": None if replacement is None else replacement.model_dump(mode="json"),
        "expected_target_layer": layer.model_dump(mode="json"),
    }


def _preview_executable(request: ExecutableRequest, expected_alias: str) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _plan(request)
    if plan.command_alias != expected_alias:
        raise ValueError(f"{expected_alias} preview received a different request type")
    doc = _drawing(request.document_id)
    sources: list[LiveEntityEvidence] = []
    replacement: LiveTextEvidence | None = None
    if isinstance(request, RectangleAreaLabelRequest):
        for rectangle in request.rectangles:
            sources.append(_entity(doc, rectangle.source_handle)[0])
        layer = _layer(doc, request.layer)
    else:
        sources.append(_entity(doc, request.triangle.source_id)[0])
        layer = _layer(doc, request.exact_annotation.layer)
        if request.annotation_mode is AnnotationMode.REPLACE_TEXT:
            replacement = _text(doc, request.exact_annotation.replace_text_handle or "")[0]
    source_tuple = tuple(sources)
    payload = _payload(request, plan, source_tuple, replacement, layer)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "exact handles, target layer, caller-supplied text, insertion point, and height are stale-checked around one Undo group; legacy equivalence is not claimed",
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


def preview_live_cdn(request: NorthReviewRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_dar(request: DynamicAreaRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_dee(request: EnergyElevationRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_dm(request: DistanceMemoryRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_ffo(request: FindFieldObjectsRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_hv(request: RectangleAreaLabelRequest) -> dict[str, Any]:
    return _preview_executable(request, "HV")


def preview_live_hw(request: HwAreaRequest) -> dict[str, Any]:
    return _preview_executable(request, "HW")


def preview_live_mac(request: MakeAreaCenterRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_mrt(request: RoomTableRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_sar(request: SiteAreaRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_sca(request: ScaleAreaRequest) -> dict[str, Any]:
    return _preview_blocked(request)


def preview_live_se(request: SelectSameRequest) -> dict[str, Any]:
    return _preview_blocked(request)


_ATTACHMENT = {
    TextAnchor.TOP_LEFT: 1,
    TextAnchor.TOP_CENTER: 2,
    TextAnchor.TOP_RIGHT: 3,
    TextAnchor.MIDDLE_LEFT: 4,
    TextAnchor.MIDDLE_CENTER: 5,
    TextAnchor.MIDDLE_RIGHT: 6,
    TextAnchor.BOTTOM_LEFT: 7,
    TextAnchor.BOTTOM_CENTER: 8,
    TextAnchor.BOTTOM_RIGHT: 9,
}


def _add_mtext(doc: Any, point: Point3D, text: str, height: float, layer: str, attachment: int) -> Any:
    entity = doc.ModelSpace.AddMText(_variant(point), 0.0, text)
    entity.Height = height
    entity.Layer = layer
    entity.AttachmentPoint = attachment
    entity.InsertionPoint = _variant(point)
    return entity


def execute_live_batch24(request: LiveBatch24ExecuteRequest) -> LiveBatch24Result:
    plan = _plan(request.request)
    payload = _payload(
        request.request,
        plan,
        request.expected_sources,
        request.expected_replacement_text,
        request.expected_target_layer,
    )
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 24 preview")
    doc = _drawing(request.request.document_id)
    current_sources = tuple(_entity(doc, item.handle) for item in request.expected_sources)
    if tuple(item[0] for item in current_sources) != request.expected_sources:
        raise ValueError("Batch 24 source state no longer matches the approved preview")
    if _layer(doc, request.expected_target_layer.name) != request.expected_target_layer:
        raise ValueError("Batch 24 target-layer state no longer matches the approved preview")
    replacement_object: Any | None = None
    if request.expected_replacement_text is not None:
        current_replacement, replacement_object = _text(doc, request.expected_replacement_text.handle)
        if current_replacement != request.expected_replacement_text:
            raise ValueError("Batch 24 replacement text no longer matches the approved preview")
    created: list[Any] = []
    changed: list[Any] = []
    expected: list[tuple[Any, str, float, Point3D, str, int | None]] = []
    doc.StartUndoMark()
    try:
        if plan.command_alias == "HV":
            text = "\n".join(label.text for label in plan.labels)
            entity = _add_mtext(
                doc,
                plan.insertion_point,
                text,
                plan.text_height,
                plan.layer,
                _ATTACHMENT[plan.anchor],
            )
            created.append(entity)
            expected.append(
                (entity, text, plan.text_height, plan.insertion_point, plan.layer, _ATTACHMENT[plan.anchor])
            )
        elif plan.command_alias == "HW":
            annotation = plan.annotation
            text = annotation.formula_text + "\n" + annotation.result_text
            if plan.annotation_mode is AnnotationMode.CREATE_TEXT:
                entity = _add_mtext(doc, annotation.insertion_point, text, annotation.text_height, annotation.layer, 1)
                created.append(entity)
                expected.append((entity, text, annotation.text_height, annotation.insertion_point, annotation.layer, 1))
            else:
                if replacement_object is None:
                    raise RuntimeError("HW approved replacement object is unavailable")
                replacement_object.TextString = text
                replacement_object.Height = annotation.text_height
                replacement_object.Layer = annotation.layer
                changed.append(replacement_object)
                expected.append(
                    (
                        replacement_object,
                        text,
                        annotation.text_height,
                        request.expected_replacement_text.insertion_point,
                        annotation.layer,
                        None,
                    )
                )
        else:
            raise ValueError(f"Batch 24 live execution is not exposed for {plan.command_alias}")
    finally:
        doc.EndUndoMark()
    available = _entities(doc)
    if any(str(item.Handle).casefold() not in available for item in created + changed):
        raise RuntimeError(f"{plan.command_alias} postcondition failed: output text is missing")
    for entity, text, height, point, layer, attachment in expected:
        if (
            str(entity.TextString) != text
            or abs(float(entity.Height) - height) > 1e-9
            or _point(entity.InsertionPoint) != point
            or str(entity.Layer).casefold() != layer.casefold()
            or (attachment is not None and int(entity.AttachmentPoint) != attachment)
        ):
            raise RuntimeError(f"{plan.command_alias} postcondition failed: text properties differ")
    return LiveBatch24Result(
        document_name=str(doc.Name),
        command_alias=plan.command_alias,
        created_handles=tuple(str(item.Handle) for item in created),
        changed_handles=tuple(str(item.Handle) for item in changed),
        undo_mark_opened=True,
        undo_mark_closed=True,
        postcondition_verified=True,
    )


def register_live_batch24_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 24 operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 24 operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    functions = {
        "cdn": preview_live_cdn,
        "dar": preview_live_dar,
        "dee": preview_live_dee,
        "dm": preview_live_dm,
        "ffo": preview_live_ffo,
        "hv": preview_live_hv,
        "hw": preview_live_hw,
        "mac": preview_live_mac,
        "mrt": preview_live_mrt,
        "sar": preview_live_sar,
        "sca": preview_live_sca,
        "se": preview_live_se,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
        if alias.upper() not in BLOCKED:
            mcp.tool(name=f"xicad_execute_live_{alias}", annotations=execute)(execute_live_batch24)
