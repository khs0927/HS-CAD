from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from math import radians
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch9 import LayerEntitySnapshot, LayerSnapshot
from .headless_core_batch11 import (
    AllLayerStateRequest,
    DimensionConvertRequest,
    DimensionKind,
    DimensionSnapshot,
    DimensionSourceDisposition,
    DimensionTextEditRequest,
    DimensionTextMode,
    LinearDimensionKind,
    SelectedLayerUnlockRequest,
    plan_all_layers_thaw,
    plan_all_layers_unlock,
    plan_dimension_convert,
    plan_dimension_text_edit,
    plan_selected_layers_unlock,
    plan_toggle_layer_on_off,
)
from .live_layer_batch9a import ZWCADLiveLayer9aAdapter


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _models(items: tuple[BaseModel, ...]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)


class LiveAllLayerStatePreviewRequest(_Request):
    include_xref_layers: bool = False
    current_layer_policy: str = Field(default="keep_on", pattern=r"^(keep_on|error)$")


class LiveAllLayerStateExecuteRequest(LiveAllLayerStatePreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveLuPreviewRequest(_Request):
    selected_entity_handles: tuple[str, ...] = Field(min_length=1)
    xref_layer_policy: str = Field(default="skip", pattern=r"^(skip|error)$")


class LiveLuExecuteRequest(LiveLuPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_entities: tuple[LayerEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveCdePreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: DimensionTextMode
    text: str = ""
    measurement_token: str = "<>"


class LiveCdeExecuteRequest(LiveCdePreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_dimensions: tuple[DimensionSnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveDcvPreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    target_kind: LinearDimensionKind
    rotation_degrees: float | None = None
    source_disposition: DimensionSourceDisposition
    preserve_text_override: bool
    preserve_style: bool
    dimension_line_points: dict[str, Point3D]


class LiveDcvExecuteRequest(LiveDcvPreviewRequest):
    expected_layers: tuple[LayerSnapshot, ...]
    expected_dimensions: tuple[DimensionSnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveBatch11aResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_layers: tuple[str, ...] = ()
    changed_handles: tuple[str, ...] = ()
    created_handles: tuple[str, ...] = ()
    erased_handles: tuple[str, ...] = ()
    postcondition_verified: bool


class ZWCADLiveBatch11aAdapter(ZWCADLiveLayer9aAdapter):
    @staticmethod
    def _point(value: Any, property_name: str) -> Point3D:
        try:
            coordinates = tuple(float(item) for item in value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"ZWCAD returned invalid {property_name}") from exc
        if len(coordinates) != 3:
            raise RuntimeError(f"ZWCAD returned invalid {property_name}")
        return Point3D(x=coordinates[0], y=coordinates[1], z=coordinates[2])

    def dimensions(
        self,
        handles: tuple[str, ...],
        dimension_line_points: dict[str, Point3D] | None = None,
    ) -> tuple[DimensionSnapshot, ...]:
        objects = self.entity_objects()
        doc = self.connect()
        result = []
        for handle in handles:
            entity = objects.get(handle.casefold())
            if entity is None:
                raise ValueError(f"dimension not found: {handle}")
            object_name = str(entity.ObjectName).casefold()
            if "aligneddimension" in object_name:
                kind = DimensionKind.ALIGNED
            elif "rotateddimension" in object_name:
                kind = DimensionKind.ROTATED
            else:
                raise ValueError(f"CDE/DCV live adapter currently supports aligned/rotated dimensions only: {handle}")
            layer = str(entity.Layer)
            try:
                text_position = self._point(entity.TextPosition, "TextPosition")
                first = self._point(entity.ExtLine1Point, "ExtLine1Point")
                second = self._point(entity.ExtLine2Point, "ExtLine2Point")
                fixed_length = float(entity.ExtLineFixedLen)
                snapshot = DimensionSnapshot(
                    handle=str(entity.Handle),
                    kind=kind,
                    layer=layer,
                    style=str(entity.StyleName),
                    measurement=float(entity.Measurement),
                    text_override=str(entity.TextOverride),
                    text_position=text_position,
                    default_text_position=text_position,
                    dimension_line_point=(
                        dimension_line_points[handle.casefold()] if dimension_line_points is not None else text_position
                    ),
                    first_extension_origin=first,
                    second_extension_origin=second,
                    first_extension_suppressed=bool(entity.ExtLine1Suppress),
                    second_extension_suppressed=bool(entity.ExtLine2Suppress),
                    first_extension_length=fixed_length,
                    second_extension_length=fixed_length,
                    dimscale=max(float(doc.GetVariable("DIMSCALE")), 1e-12),
                    ltscale=max(float(entity.LinetypeScale), 1e-12),
                    object_scale=1.0,
                    locked_layer=bool(doc.Layers.Item(layer).Lock),
                    is_xref="|" in layer,
                )
            except Exception as exc:
                raise RuntimeError(f"ZWCAD cannot provide the exact linear dimension state: {handle}") from exc
            result.append(snapshot)
        return tuple(result)

    def vector(self, point: Point3D) -> Any:
        import pythoncom
        import win32com.client

        return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])


def _approval(execute: bool, fingerprint: str | None = None) -> Approval:
    return Approval(approved=execute, fingerprint=fingerprint)


def _same(actual: tuple[BaseModel, ...], expected: tuple[BaseModel, ...], alias: str) -> None:
    if _models(actual) != _models(expected):
        raise ValueError(f"{alias} inventory no longer matches the approved snapshot")


def _layer_payload(
    request: BaseModel, layers: tuple[LayerSnapshot, ...], entities: tuple[LayerEntitySnapshot, ...], plan: BaseModel
) -> dict[str, Any]:
    body = {
        **request.model_dump(mode="json"),
        "expected_layers": _models(layers),
        "expected_entities": _models(entities),
    }
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def _dimension_payload(
    request: BaseModel, layers: tuple[LayerSnapshot, ...], dimensions: tuple[DimensionSnapshot, ...], plan: BaseModel
) -> dict[str, Any]:
    body = {
        **request.model_dump(mode="json"),
        "expected_layers": _models(layers),
        "expected_dimensions": _models(dimensions),
    }
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def _all_core(
    request: LiveAllLayerStatePreviewRequest, execute: bool, fingerprint: str | None = None
) -> AllLayerStateRequest:
    return AllLayerStateRequest(
        document_id=request.document_name,
        include_xref_layers=request.include_xref_layers,
        current_layer_policy=request.current_layer_policy,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def _protect_layer_plan(plan: Any) -> Any:
    on_changes = tuple(
        c for c in plan.on_freeze_changes if c.layer.casefold() not in {"0", "defpoints"} and "|" not in c.layer
    )
    lock_changes = tuple(
        c for c in plan.lock_changes if c.layer.casefold() not in {"0", "defpoints"} and "|" not in c.layer
    )
    return plan.model_copy(update={"on_freeze_changes": on_changes, "lock_changes": lock_changes})


def _preview_all(request: LiveAllLayerStatePreviewRequest, planner: Callable[..., Any]) -> dict[str, Any]:
    adapter = ZWCADLiveBatch11aAdapter(request.document_name)
    layers, entities = adapter.layers(), adapter.inventory()
    plan = _protect_layer_plan(planner(_all_core(request, False), layers))
    return _layer_payload(request, layers, entities, plan)


def preview_live_lt(request: LiveAllLayerStatePreviewRequest) -> dict[str, Any]:
    return _preview_all(request, plan_all_layers_thaw)


def preview_live_ltg(request: LiveAllLayerStatePreviewRequest) -> dict[str, Any]:
    return _preview_all(request, plan_toggle_layer_on_off)


def preview_live_luk(request: LiveAllLayerStatePreviewRequest) -> dict[str, Any]:
    return _preview_all(request, plan_all_layers_unlock)


def _execute_all(
    request: LiveAllLayerStateExecuteRequest, alias: str, planner: Callable[..., Any]
) -> LiveBatch11aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError(f"approval fingerprint does not match the exact {alias} request")
    adapter = ZWCADLiveBatch11aAdapter(request.document_name)
    layers, entities = adapter.layers(), adapter.inventory()
    _same(layers, request.expected_layers, alias)
    _same(entities, request.expected_entities, alias)
    plan = _protect_layer_plan(planner(_all_core(request, True, request.approval_fingerprint), layers))
    records = adapter.layer_objects()
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.on_freeze_changes:
            record = records[change.layer.casefold()]
            record.LayerOn = change.replacement_on
            record.Freeze = change.replacement_frozen
        for change in plan.lock_changes:
            records[change.layer.casefold()].Lock = change.replacement_locked
    finally:
        doc.EndUndoMark()
    after = {x.name.casefold(): x for x in adapter.layers()}
    verified = all(
        after[c.layer.casefold()].is_on == c.replacement_on
        and after[c.layer.casefold()].is_frozen == c.replacement_frozen
        for c in plan.on_freeze_changes
    ) and all(after[c.layer.casefold()].is_locked == c.replacement_locked for c in plan.lock_changes)
    if not verified:
        raise RuntimeError(f"{alias} postcondition failed")
    return LiveBatch11aResult(
        document_name=str(doc.Name),
        command_alias=alias,
        changed_layers=tuple(c.layer for c in (*plan.on_freeze_changes, *plan.lock_changes)),
        postcondition_verified=True,
    )


def register_live_batch11a_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 11A operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 11A operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_lt", preview_live_lt, preview),
        ("xicad_execute_live_lt", execute_live_lt, execute),
        ("xicad_preview_live_ltg", preview_live_ltg, preview),
        ("xicad_execute_live_ltg", execute_live_ltg, execute),
        ("xicad_preview_live_lu", preview_live_lu, preview),
        ("xicad_execute_live_lu", execute_live_lu, execute),
        ("xicad_preview_live_luk", preview_live_luk, preview),
        ("xicad_execute_live_luk", execute_live_luk, execute),
        ("xicad_preview_live_cde", preview_live_cde, preview),
        ("xicad_execute_live_cde", execute_live_cde, execute),
        ("xicad_preview_live_dcv", preview_live_dcv, preview),
        ("xicad_execute_live_dcv", execute_live_dcv, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)


def execute_live_lt(request: LiveAllLayerStateExecuteRequest) -> LiveBatch11aResult:
    return _execute_all(request, "LT", plan_all_layers_thaw)


def execute_live_ltg(request: LiveAllLayerStateExecuteRequest) -> LiveBatch11aResult:
    return _execute_all(request, "LTG", plan_toggle_layer_on_off)


def execute_live_luk(request: LiveAllLayerStateExecuteRequest) -> LiveBatch11aResult:
    return _execute_all(request, "LUK", plan_all_layers_unlock)


def _lu_core(
    request: LiveLuPreviewRequest, execute: bool, fingerprint: str | None = None
) -> SelectedLayerUnlockRequest:
    return SelectedLayerUnlockRequest(
        document_id=request.document_name,
        selected_entity_handles=request.selected_entity_handles,
        xref_layer_policy=request.xref_layer_policy,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_lu(request: LiveLuPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveBatch11aAdapter(request.document_name)
    layers, entities = adapter.layers(), adapter.inventory()
    plan = _protect_layer_plan(plan_selected_layers_unlock(_lu_core(request, False), layers, entities))
    return _layer_payload(request, layers, entities, plan)


def execute_live_lu(request: LiveLuExecuteRequest) -> LiveBatch11aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact LU request")
    adapter = ZWCADLiveBatch11aAdapter(request.document_name)
    layers, entities = adapter.layers(), adapter.inventory()
    _same(layers, request.expected_layers, "LU")
    _same(entities, request.expected_entities, "LU")
    plan = _protect_layer_plan(
        plan_selected_layers_unlock(_lu_core(request, True, request.approval_fingerprint), layers, entities)
    )
    records = adapter.layer_objects()
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.lock_changes:
            records[change.layer.casefold()].Lock = change.replacement_locked
    finally:
        doc.EndUndoMark()
    after = {x.name.casefold(): x for x in adapter.layers()}
    if not all(after[c.layer.casefold()].is_locked == c.replacement_locked for c in plan.lock_changes):
        raise RuntimeError("LU postcondition failed")
    return LiveBatch11aResult(
        document_name=str(doc.Name),
        command_alias="LU",
        changed_layers=tuple(c.layer for c in plan.lock_changes),
        postcondition_verified=True,
    )


def _cde_core(
    request: LiveCdePreviewRequest, execute: bool, fingerprint: str | None = None
) -> DimensionTextEditRequest:
    return DimensionTextEditRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        mode=request.mode,
        text=request.text,
        measurement_token=request.measurement_token,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_cde(request: LiveCdePreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveBatch11aAdapter(request.document_name)
    layers = adapter.layers()
    dims = adapter.dimensions(request.target_handles)
    plan = plan_dimension_text_edit(_cde_core(request, False), dims)
    return _dimension_payload(request, layers, dims, plan)


def execute_live_cde(request: LiveCdeExecuteRequest) -> LiveBatch11aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact CDE request")
    adapter = ZWCADLiveBatch11aAdapter(request.document_name)
    layers = adapter.layers()
    dims = adapter.dimensions(request.target_handles)
    _same(layers, request.expected_layers, "CDE")
    _same(dims, request.expected_dimensions, "CDE")
    plan = plan_dimension_text_edit(_cde_core(request, True, request.approval_fingerprint), dims)
    objects = adapter.entity_objects()
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            objects[change.handle.casefold()].TextOverride = change.replacement_override
    finally:
        doc.EndUndoMark()
    if not all(str(objects[c.handle.casefold()].TextOverride) == c.replacement_override for c in plan.changes):
        raise RuntimeError("CDE postcondition failed")
    return LiveBatch11aResult(
        document_name=str(doc.Name),
        command_alias="CDE",
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )


def _dcv_core(request: LiveDcvPreviewRequest, execute: bool, fingerprint: str | None = None) -> DimensionConvertRequest:
    return DimensionConvertRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        target_kind=request.target_kind,
        rotation_degrees=request.rotation_degrees,
        source_disposition=request.source_disposition,
        preserve_text_override=request.preserve_text_override,
        preserve_style=request.preserve_style,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_dcv(request: LiveDcvPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveBatch11aAdapter(request.document_name)
    layers = adapter.layers()
    points = {handle.casefold(): point for handle, point in request.dimension_line_points.items()}
    if len(points) != len(request.dimension_line_points) or set(points) != {
        handle.casefold() for handle in request.target_handles
    }:
        raise ValueError("DCV dimension_line_points must contain every target handle exactly")
    dims = adapter.dimensions(request.target_handles, points)
    plan = plan_dimension_convert(_dcv_core(request, False), dims)
    return _dimension_payload(request, layers, dims, plan)


def execute_live_dcv(request: LiveDcvExecuteRequest) -> LiveBatch11aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact DCV request")
    adapter = ZWCADLiveBatch11aAdapter(request.document_name)
    layers = adapter.layers()
    points = {handle.casefold(): point for handle, point in request.dimension_line_points.items()}
    if len(points) != len(request.dimension_line_points) or set(points) != {
        handle.casefold() for handle in request.target_handles
    }:
        raise ValueError("DCV dimension_line_points must contain every target handle exactly")
    dims = adapter.dimensions(request.target_handles, points)
    _same(layers, request.expected_layers, "DCV")
    _same(dims, request.expected_dimensions, "DCV")
    plan = plan_dimension_convert(_dcv_core(request, True, request.approval_fingerprint), dims)
    before = {d.handle.casefold(): d for d in dims}
    objects = adapter.entity_objects()
    doc = adapter.connect()
    created = []
    doc.StartUndoMark()
    try:
        for spec in plan.creates:
            if spec.target_kind is LinearDimensionKind.ALIGNED:
                entity = doc.ModelSpace.AddDimAligned(
                    adapter.vector(spec.first_extension_origin),
                    adapter.vector(spec.second_extension_origin),
                    adapter.vector(spec.dimension_line_point),
                )
            else:
                entity = doc.ModelSpace.AddDimRotated(
                    adapter.vector(spec.first_extension_origin),
                    adapter.vector(spec.second_extension_origin),
                    adapter.vector(spec.dimension_line_point),
                    radians(spec.rotation_degrees),
                )
            source = before[spec.source_handle.casefold()]
            entity.Layer = source.layer
            if spec.style is not None:
                entity.StyleName = spec.style
            entity.TextOverride = spec.text_override
            created.append(entity)
            if spec.erase_source:
                objects[spec.source_handle.casefold()].Delete()
    finally:
        doc.EndUndoMark()
    created_handles = tuple(str(e.Handle) for e in created)
    erased = tuple(s.source_handle for s in plan.creates if s.erase_source)
    after_objects = adapter.entity_objects()
    verified = all(h.casefold() in after_objects for h in created_handles) and all(
        h.casefold() not in after_objects for h in erased
    )
    verified = verified and all(
        (
            ("aligneddimension" in str(e.ObjectName).casefold())
            if s.target_kind is LinearDimensionKind.ALIGNED
            else ("rotateddimension" in str(e.ObjectName).casefold())
        )
        and str(e.Layer) == before[s.source_handle.casefold()].layer
        and str(e.TextOverride) == s.text_override
        and (s.style is None or str(e.StyleName) == s.style)
        for e, s in zip(created, plan.creates, strict=True)
    )
    if not verified:
        raise RuntimeError("DCV postcondition failed")
    return LiveBatch11aResult(
        document_name=str(doc.Name),
        command_alias="DCV",
        created_handles=created_handles,
        erased_handles=erased,
        postcondition_verified=True,
    )
