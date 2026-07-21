from __future__ import annotations

import hashlib
import json
from math import hypot
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch11 import DimensionKind, DimensionSnapshot
from .headless_core_batch13 import (
    FlattenPolicy,
    JoinPolylineRequest,
    Polyline3DConvertRequest,
    PolylineSnapshot,
    ProjectionPolicy,
    ProjectionRequest,
    SourceDisposition,
    SplitDimensionRequest,
    plan_3dpoly_to_lwpoly,
    plan_join_polylines,
    plan_projection,
    plan_split_dimension,
)
from .live_batch11a import ZWCADLiveBatch11aAdapter


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _models(items: tuple[BaseModel, ...]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)


class LiveLxPreviewRequest(_Request):
    request: dict[str, Any]


class LiveTlPreviewRequest(_Request):
    request: dict[str, Any]


class LiveSdPreviewRequest(_Request):
    source_handle: str = Field(min_length=1)
    split_points: tuple[Point3D, ...] = Field(min_length=1)
    dimension_line_point: Point3D
    source_disposition: SourceDisposition
    preserve_style: bool = True
    preserve_text_override: bool = False


class LiveSdExecuteRequest(LiveSdPreviewRequest):
    expected_source: DimensionSnapshot
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LivePolylineState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    snapshot: PolylineSnapshot
    object_name: str


class Live2dpPreviewRequest(_Request):
    source_handles: tuple[str, ...] = Field(min_length=1)
    source_boundary_handle: str
    target_boundary_handle: str
    policy: ProjectionPolicy
    affine_matrix_4x4: tuple[tuple[float, float, float, float], ...] | None = None
    normalized_output_vertices: dict[str, tuple[Point3D, ...]] = {}
    target_layer: str = Field(min_length=1)
    source_disposition: SourceDisposition


class Live2dpExecuteRequest(Live2dpPreviewRequest):
    expected_geometry: tuple[LivePolylineState, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class Live3tpPreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    flatten_policy: FlattenPolicy
    constant_z: float | None = None
    projected_vertices: dict[str, tuple[Point3D, ...]] = {}
    source_disposition: SourceDisposition


class Live3tpExecuteRequest(Live3tpPreviewRequest):
    expected_geometry: tuple[LivePolylineState, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveBooPreviewRequest(_Request):
    ordered_handles: tuple[str, ...] = Field(min_length=2)
    reverse_handles: tuple[str, ...] = ()
    tolerance: float = Field(ge=0)
    close_result: bool = False
    target_layer: str = Field(min_length=1)
    source_disposition: SourceDisposition


class LiveBooExecuteRequest(LiveBooPreviewRequest):
    expected_geometry: tuple[LivePolylineState, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveBatch13aResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...] = ()
    erased_handles: tuple[str, ...] = ()
    postcondition_verified: bool


class ZWCADLiveBatch13aAdapter(ZWCADLiveBatch11aAdapter):
    def validate_output_layer(self, name: str) -> None:
        try:
            layer = self.connect().Layers.Item(name)
        except Exception as exc:
            raise ValueError(f"output layer not found: {name}") from exc
        if bool(layer.Lock):
            raise ValueError(f"output layer is locked: {name}")
        if "|" in name:
            raise ValueError(f"xref-dependent output layer is not writable: {name}")

    def polylines(self, handles: tuple[str, ...]) -> tuple[LivePolylineState, ...]:
        objects = self.entity_objects()
        result = []
        for handle in handles:
            entity = objects.get(handle.casefold())
            if entity is None:
                raise ValueError(f"polyline not found: {handle}")
            name = str(entity.ObjectName).casefold()
            values = tuple(float(value) for value in entity.Coordinates)
            if name == "acdbpolyline":
                elevation = float(getattr(entity, "Elevation", 0.0))
                vertices = tuple(Point3D(x=values[i], y=values[i + 1], z=elevation) for i in range(0, len(values), 2))
            elif "3dpolyline" in name:
                vertices = tuple(
                    Point3D(x=values[i], y=values[i + 1], z=values[i + 2]) for i in range(0, len(values), 3)
                )
            else:
                raise ValueError(f"unsupported polyline type: {handle} ({entity.ObjectName})")
            layer = str(entity.Layer)
            result.append(
                LivePolylineState(
                    snapshot=PolylineSnapshot(
                        handle=str(entity.Handle),
                        vertices=vertices,
                        closed=bool(entity.Closed),
                        layer=layer,
                        locked_layer=bool(self.connect().Layers.Item(layer).Lock),
                        is_xref="|" in layer,
                    ),
                    object_name=str(entity.ObjectName),
                )
            )
        return tuple(result)

    def lwpolyline(self, vertices: tuple[Point3D, ...], closed: bool, layer: str) -> Any:
        z_values = {round(vertex.z, 9) for vertex in vertices}
        if len(z_values) != 1:
            raise ValueError("live lightweight polyline output requires one constant elevation")
        import pythoncom
        import win32com.client

        coordinates = [coordinate for vertex in vertices for coordinate in (vertex.x, vertex.y)]
        value = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, coordinates)
        entity = self.connect().ModelSpace.AddLightWeightPolyline(value)
        entity.Elevation = vertices[0].z
        entity.Closed = closed
        entity.Layer = layer
        return entity


def _approval(execute: bool, fingerprint: str | None = None) -> Approval:
    return Approval(approved=execute, fingerprint=fingerprint)


def _same(actual: tuple[BaseModel, ...], expected: tuple[BaseModel, ...], alias: str) -> None:
    if _models(actual) != _models(expected):
        raise ValueError(f"{alias} geometry changed after approval")


def preview_live_lx(request: LiveLxPreviewRequest) -> dict[str, Any]:
    del request
    raise RuntimeError(
        "LX is blocked: ZWCAD ActiveX MLeader content/style/end-shape equivalence cannot be fully verified"
    )


def execute_live_lx(_request: Any) -> LiveBatch13aResult:
    raise RuntimeError("LX cannot execute through the conservative ActiveX adapter")


def preview_live_tl(request: LiveTlPreviewRequest) -> dict[str, Any]:
    del request
    raise RuntimeError(
        "TL is blocked: ZWCAD ActiveX leader/MLeader style and text association cannot be fully verified"
    )


def execute_live_tl(_request: Any) -> LiveBatch13aResult:
    raise RuntimeError("TL cannot execute through the conservative ActiveX adapter")


def _sd_core(request: LiveSdPreviewRequest, execute: bool, fingerprint: str | None = None) -> SplitDimensionRequest:
    return SplitDimensionRequest(
        document_id=request.document_name,
        source_handle=request.source_handle,
        split_points=request.split_points,
        source_disposition=request.source_disposition,
        preserve_style=request.preserve_style,
        preserve_text_override=request.preserve_text_override,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def _validate_splits(source: DimensionSnapshot, points: tuple[Point3D, ...]) -> None:
    a, b = source.first_extension_origin, source.second_extension_origin
    dx, dy = b.x - a.x, b.y - a.y
    length2 = dx * dx + dy * dy
    if length2 <= 1e-12:
        raise ValueError("SD source has zero extension span")
    previous = 0.0
    for point in points:
        cross = abs((point.x - a.x) * dy - (point.y - a.y) * dx)
        t = ((point.x - a.x) * dx + (point.y - a.y) * dy) / length2
        if cross > 1e-7 * max(hypot(dx, dy), 1.0) or not previous < t < 1.0:
            raise ValueError("SD split points must be ordered strictly inside the source span")
        previous = t


def preview_live_sd(request: LiveSdPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveBatch13aAdapter(request.document_name)
    source = adapter.dimensions(
        (request.source_handle,), {request.source_handle.casefold(): request.dimension_line_point}
    )[0]
    if source.kind is not DimensionKind.ALIGNED:
        raise RuntimeError("SD rotated source is blocked because its rotation is absent from the Batch 13 contract")
    _validate_splits(source, request.split_points)
    plan = plan_split_dimension(_sd_core(request, False), (source,))
    body = {**request.model_dump(mode="json"), "expected_source": source.model_dump(mode="json")}
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def execute_live_sd(request: LiveSdExecuteRequest) -> LiveBatch13aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match SD")
    adapter = ZWCADLiveBatch13aAdapter(request.document_name)
    source = adapter.dimensions(
        (request.source_handle,), {request.source_handle.casefold(): request.dimension_line_point}
    )[0]
    if source != request.expected_source:
        raise ValueError("SD source changed after approval")
    _validate_splits(source, request.split_points)
    plan = plan_split_dimension(_sd_core(request, True, request.approval_fingerprint), (source,))
    doc = adapter.connect()
    objects = adapter.entity_objects()
    created = []
    doc.StartUndoMark()
    try:
        for segment in plan.segments:
            entity = doc.ModelSpace.AddDimAligned(
                adapter.vector(segment.first_point),
                adapter.vector(segment.second_point),
                adapter.vector(request.dimension_line_point),
            )
            entity.Layer = source.layer
            if segment.style is not None:
                entity.StyleName = segment.style
            entity.TextOverride = segment.text_override
            created.append(entity)
        if plan.erase_source:
            objects[source.handle.casefold()].Delete()
    finally:
        doc.EndUndoMark()
    handles = tuple(str(entity.Handle) for entity in created)
    erased = (source.handle,) if plan.erase_source else ()
    after = adapter.entity_objects()
    verified = all(handle.casefold() in after for handle in handles) and all(
        handle.casefold() not in after for handle in erased
    )
    verified = verified and all(
        "aligneddimension" in str(entity.ObjectName).casefold()
        and str(entity.Layer) == source.layer
        and str(entity.TextOverride) == segment.text_override
        and (segment.style is None or str(entity.StyleName) == segment.style)
        for entity, segment in zip(created, plan.segments, strict=True)
    )
    if not verified:
        raise RuntimeError("SD postcondition failed")
    return LiveBatch13aResult(
        document_name=str(doc.Name),
        command_alias="SD",
        created_handles=handles,
        erased_handles=erased,
        postcondition_verified=True,
    )


def _geometry_payload(request: BaseModel, states: tuple[LivePolylineState, ...], plan: BaseModel) -> dict[str, Any]:
    body = {**request.model_dump(mode="json"), "expected_geometry": _models(states)}
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def _execute_geometry(
    request: Any,
    alias: str,
    states: tuple[LivePolylineState, ...],
    creates: tuple[Any, ...],
    erase_handles: tuple[str, ...],
) -> LiveBatch13aResult:
    adapter = ZWCADLiveBatch13aAdapter(request.document_name)
    current = adapter.polylines(tuple(state.snapshot.handle for state in states))
    _same(current, states, alias)
    _require_lw_outputs(creates)
    for create in creates:
        adapter.validate_output_layer(create.layer)
    objects = adapter.entity_objects()
    doc = adapter.connect()
    created = []
    doc.StartUndoMark()
    try:
        for create in creates:
            created.append(adapter.lwpolyline(create.vertices, create.closed, create.layer))
        for handle in erase_handles:
            objects[handle.casefold()].Delete()
    finally:
        doc.EndUndoMark()
    handles = tuple(str(entity.Handle) for entity in created)
    after = adapter.entity_objects()
    verified = all(handle.casefold() in after for handle in handles) and all(
        handle.casefold() not in after for handle in erase_handles
    )
    created_states = adapter.polylines(handles)
    verified = verified and all(
        state.snapshot.layer == create.layer
        and state.snapshot.closed == create.closed
        and state.snapshot.vertices == create.vertices
        for state, create in zip(created_states, creates, strict=True)
    )
    if not verified:
        raise RuntimeError(f"{alias} postcondition failed")
    return LiveBatch13aResult(
        document_name=str(doc.Name),
        command_alias=alias,
        created_handles=handles,
        erased_handles=erase_handles,
        postcondition_verified=True,
    )


def _2dp_core(request: Live2dpPreviewRequest, execute: bool, fingerprint: str | None = None) -> ProjectionRequest:
    return ProjectionRequest(
        document_id=request.document_name,
        source_handles=request.source_handles,
        source_boundary_handle=request.source_boundary_handle,
        target_boundary_handle=request.target_boundary_handle,
        policy=request.policy,
        affine_matrix_4x4=request.affine_matrix_4x4,
        normalized_output_vertices=request.normalized_output_vertices,
        target_layer=request.target_layer,
        source_disposition=request.source_disposition,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_2dp(request: Live2dpPreviewRequest) -> dict[str, Any]:
    handles = tuple(
        dict.fromkeys((*request.source_handles, request.source_boundary_handle, request.target_boundary_handle))
    )
    adapter = ZWCADLiveBatch13aAdapter(request.document_name)
    adapter.validate_output_layer(request.target_layer)
    states = adapter.polylines(handles)
    plan = plan_projection(_2dp_core(request, False), tuple(state.snapshot for state in states))
    _require_lw_outputs(plan.creates)
    return _geometry_payload(request, states, plan)


def execute_live_2dp(request: Live2dpExecuteRequest) -> LiveBatch13aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match 2DP")
    plan = plan_projection(
        _2dp_core(request, True, request.approval_fingerprint),
        tuple(state.snapshot for state in request.expected_geometry),
    )
    return _execute_geometry(request, "2DP", request.expected_geometry, plan.creates, plan.erase_source_handles)


def _3tp_core(
    request: Live3tpPreviewRequest, execute: bool, fingerprint: str | None = None
) -> Polyline3DConvertRequest:
    return Polyline3DConvertRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        flatten_policy=request.flatten_policy,
        constant_z=request.constant_z,
        projected_vertices=request.projected_vertices,
        source_disposition=request.source_disposition,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_3tp(request: Live3tpPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveBatch13aAdapter(request.document_name)
    states = adapter.polylines(request.target_handles)
    if any("3dpolyline" not in state.object_name.casefold() for state in states):
        raise ValueError("3TP requires AcDb3dPolyline sources")
    plan = plan_3dpoly_to_lwpoly(_3tp_core(request, False), tuple(s.snapshot for s in states))
    _require_lw_outputs(plan.creates)
    return _geometry_payload(request, states, plan)


def execute_live_3tp(request: Live3tpExecuteRequest) -> LiveBatch13aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match 3TP")
    plan = plan_3dpoly_to_lwpoly(
        _3tp_core(request, True, request.approval_fingerprint),
        tuple(state.snapshot for state in request.expected_geometry),
    )
    return _execute_geometry(request, "3TP", request.expected_geometry, plan.creates, plan.erase_source_handles)


def _boo_core(request: LiveBooPreviewRequest, execute: bool, fingerprint: str | None = None) -> JoinPolylineRequest:
    return JoinPolylineRequest(
        document_id=request.document_name,
        ordered_handles=request.ordered_handles,
        reverse_handles=request.reverse_handles,
        tolerance=request.tolerance,
        close_result=request.close_result,
        target_layer=request.target_layer,
        source_disposition=request.source_disposition,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_boo(request: LiveBooPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveBatch13aAdapter(request.document_name)
    adapter.validate_output_layer(request.target_layer)
    states = adapter.polylines(request.ordered_handles)
    plan = plan_join_polylines(_boo_core(request, False), tuple(s.snapshot for s in states))
    _require_lw_outputs((plan.create,))
    return _geometry_payload(request, states, plan)


def execute_live_boo(request: LiveBooExecuteRequest) -> LiveBatch13aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match BOO")
    plan = plan_join_polylines(
        _boo_core(request, True, request.approval_fingerprint),
        tuple(state.snapshot for state in request.expected_geometry),
    )
    return _execute_geometry(request, "BOO", request.expected_geometry, (plan.create,), plan.erase_source_handles)


def _require_lw_outputs(creates: tuple[Any, ...]) -> None:
    for create in creates:
        if not create.vertices:
            raise ValueError("lightweight polyline output requires vertices")
        elevations = {round(vertex.z, 9) for vertex in create.vertices}
        if len(elevations) != 1:
            raise RuntimeError("planned geometry cannot be represented as a ZWCAD lightweight polyline")


def register_live_batch13a_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 13A geometry operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 13A geometry operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_lx", preview_live_lx, preview),
        ("xicad_preview_live_tl", preview_live_tl, preview),
        ("xicad_preview_live_sd", preview_live_sd, preview),
        ("xicad_execute_live_sd", execute_live_sd, execute),
        ("xicad_preview_live_2dp", preview_live_2dp, preview),
        ("xicad_execute_live_2dp", execute_live_2dp, execute),
        ("xicad_preview_live_3tp", preview_live_3tp, preview),
        ("xicad_execute_live_3tp", execute_live_3tp, execute),
        ("xicad_preview_live_boo", preview_live_boo, preview),
        ("xicad_execute_live_boo", execute_live_boo, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
