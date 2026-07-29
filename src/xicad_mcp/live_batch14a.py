from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch14 import (
    ExplodePolicy,
    GeometrySnapshot,
    KMarkRequest,
    LineExplodeRequest,
    LineExportRequest,
    SourceDisposition,
    plan_k_mark,
    plan_line_explode,
    plan_line_export,
)
from .live_batch11a import ZWCADLiveBatch11aAdapter


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)


class LiveKPreviewRequest(_Request):
    insertion_points: tuple[Point3D, ...] = Field(min_length=1)
    size: float = Field(gt=0)
    rotation_degrees: float = 0
    layer: str = Field(min_length=1)


class LiveKExecuteRequest(LiveKPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveLexPreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    origin: Point3D
    normalize_scale: bool
    include_layer: bool


class LiveLexExecuteRequest(LiveLexPreviewRequest):
    expected_geometry: tuple[GeometrySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveLxpPreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    policy: ExplodePolicy
    source_disposition: SourceDisposition
    target_layer: str = Field(min_length=1)


class LiveLxpExecuteRequest(LiveLxpPreviewRequest):
    expected_geometry: tuple[GeometrySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveBatch14aResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...] = ()
    erased_handles: tuple[str, ...] = ()
    exports: tuple[dict[str, Any], ...] = ()
    postcondition_verified: bool


class ZWCADLiveBatch14aAdapter(ZWCADLiveBatch11aAdapter):
    def validate_output_layer(self, name: str) -> None:
        try:
            layer = self.connect().Layers.Item(name)
        except Exception as exc:
            raise ValueError(f"output layer not found: {name}") from exc
        if bool(layer.Lock):
            raise ValueError(f"output layer is locked: {name}")
        if "|" in name:
            raise ValueError(f"xref-dependent output layer is not writable: {name}")

    def geometry(self, handles: tuple[str, ...]) -> tuple[GeometrySnapshot, ...]:
        objects = self.entity_objects()
        result = []
        for handle in handles:
            entity = objects.get(handle.casefold())
            if entity is None:
                raise ValueError(f"geometry not found: {handle}")
            name = str(entity.ObjectName)
            folded = name.casefold()
            if folded == "acdbline":
                vertices = (self.point(entity.StartPoint), self.point(entity.EndPoint))
                closed, width, elevation = False, 0.0, 0.0
            elif folded == "acdbpolyline":
                values = tuple(float(value) for value in entity.Coordinates)
                elevation = float(getattr(entity, "Elevation", 0.0))
                vertices = tuple(
                    Point3D(x=values[index], y=values[index + 1], z=elevation) for index in range(0, len(values), 2)
                )
                closed = bool(entity.Closed)
                width = float(getattr(entity, "ConstantWidth", 0.0))
            else:
                raise RuntimeError(f"unsupported Batch 14 geometry: {handle} ({name})")
            layer = str(entity.Layer)
            result.append(
                GeometrySnapshot(
                    handle=str(entity.Handle),
                    entity_type=name,
                    vertices=vertices,
                    layer=layer,
                    closed=closed,
                    constant_width=width,
                    elevation=elevation,
                    is_xref="|" in layer,
                    locked_layer=bool(self.connect().Layers.Item(layer).Lock),
                )
            )
        return tuple(result)

    def line(self, start: Point3D, end: Point3D, layer: str) -> Any:
        entity = self.connect().ModelSpace.AddLine(self.vector(start), self.vector(end))
        entity.Layer = layer
        return entity

    @staticmethod
    def point(value: Any) -> Point3D:
        return Point3D(x=float(value[0]), y=float(value[1]), z=float(value[2]))


def _approval(execute: bool, fingerprint: str | None = None) -> Approval:
    return Approval(approved=execute, fingerprint=fingerprint)


def _k_core(request: LiveKPreviewRequest, execute: bool, fingerprint: str | None = None) -> KMarkRequest:
    return KMarkRequest(
        document_id=request.document_name,
        insertion_points=request.insertion_points,
        size=request.size,
        rotation_degrees=request.rotation_degrees,
        layer=request.layer,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_k(request: LiveKPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveBatch14aAdapter(request.document_name)
    adapter.validate_output_layer(request.layer)
    plan = plan_k_mark(_k_core(request, False))
    body = request.model_dump(mode="json")
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def execute_live_k(request: LiveKExecuteRequest) -> LiveBatch14aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match K")
    adapter = ZWCADLiveBatch14aAdapter(request.document_name)
    adapter.validate_output_layer(request.layer)
    plan = plan_k_mark(_k_core(request, True, request.approval_fingerprint))
    doc = adapter.connect()
    created = []
    doc.StartUndoMark()
    try:
        for mark in plan.creates:
            for start, end in mark.strokes:
                created.append(adapter.line(start, end, mark.layer))
    finally:
        doc.EndUndoMark()
    return _verify_lines(
        adapter, "K", created, tuple(segment for mark in plan.creates for segment in mark.strokes), request.layer
    )


def _lex_core(request: LiveLexPreviewRequest, execute: bool, fingerprint: str | None = None) -> LineExportRequest:
    return LineExportRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        origin=request.origin,
        normalize_scale=request.normalize_scale,
        include_layer=request.include_layer,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_lex(request: LiveLexPreviewRequest) -> dict[str, Any]:
    states = ZWCADLiveBatch14aAdapter(request.document_name).geometry(request.target_handles)
    plan = plan_line_export(_lex_core(request, False), states)
    body = {**request.model_dump(mode="json"), "expected_geometry": [state.model_dump(mode="json") for state in states]}
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def execute_live_lex(request: LiveLexExecuteRequest) -> LiveBatch14aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match LEX")
    adapter = ZWCADLiveBatch14aAdapter(request.document_name)
    current = adapter.geometry(request.target_handles)
    if current != request.expected_geometry:
        raise ValueError("LEX geometry changed after approval")
    plan = plan_line_export(_lex_core(request, True, request.approval_fingerprint), current)
    return LiveBatch14aResult(
        document_name=str(adapter.connect().Name),
        command_alias="LEX",
        exports=tuple(item.model_dump(mode="json") for item in plan.exports),
        postcondition_verified=True,
    )


def _lxp_core(request: LiveLxpPreviewRequest, execute: bool, fingerprint: str | None = None) -> LineExplodeRequest:
    return LineExplodeRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        policy=request.policy,
        source_disposition=request.source_disposition,
        target_layer=request.target_layer,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_lxp(request: LiveLxpPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveBatch14aAdapter(request.document_name)
    adapter.validate_output_layer(request.target_layer)
    states = adapter.geometry(request.target_handles)
    plan = plan_line_explode(_lxp_core(request, False), states)
    body = {**request.model_dump(mode="json"), "expected_geometry": [state.model_dump(mode="json") for state in states]}
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def execute_live_lxp(request: LiveLxpExecuteRequest) -> LiveBatch14aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match LXP")
    adapter = ZWCADLiveBatch14aAdapter(request.document_name)
    adapter.validate_output_layer(request.target_layer)
    current = adapter.geometry(request.target_handles)
    if current != request.expected_geometry:
        raise ValueError("LXP geometry changed after approval")
    plan = plan_line_explode(_lxp_core(request, True, request.approval_fingerprint), current)
    objects = adapter.entity_objects()
    doc = adapter.connect()
    created = []
    doc.StartUndoMark()
    try:
        for segment in plan.creates:
            created.append(adapter.line(segment.start, segment.end, segment.layer))
        for handle in plan.delete_handles:
            objects[handle.casefold()].Delete()
    finally:
        doc.EndUndoMark()
    result = _verify_lines(
        adapter,
        "LXP",
        created,
        tuple((segment.start, segment.end) for segment in plan.creates),
        request.target_layer,
        plan.delete_handles,
    )
    return result


def _verify_lines(
    adapter: ZWCADLiveBatch14aAdapter,
    alias: str,
    created: list[Any],
    segments: tuple[tuple[Point3D, Point3D], ...],
    layer: str,
    erased: tuple[str, ...] = (),
) -> LiveBatch14aResult:
    handles = tuple(str(entity.Handle) for entity in created)
    after = adapter.entity_objects()
    verified = all(handle.casefold() in after for handle in handles) and all(
        handle.casefold() not in after for handle in erased
    )
    verified = verified and all(
        str(entity.ObjectName).casefold() == "acdbline"
        and str(entity.Layer) == layer
        and adapter.point(entity.StartPoint) == start
        and adapter.point(entity.EndPoint) == end
        for entity, (start, end) in zip(created, segments, strict=True)
    )
    if not verified:
        raise RuntimeError(f"{alias} postcondition failed")
    return LiveBatch14aResult(
        document_name=str(adapter.connect().Name),
        command_alias=alias,
        created_handles=handles,
        erased_handles=erased,
        postcondition_verified=True,
    )


def register_live_batch14a_tools(mcp: FastMCP) -> None:
    read_only = ToolAnnotations(
        title="Preview/read live xiCAD Batch 14A operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 14A geometry operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_k", preview_live_k, read_only),
        ("xicad_execute_live_k", execute_live_k, execute),
        ("xicad_preview_live_lex", preview_live_lex, read_only),
        ("xicad_execute_live_lex", execute_live_lex, read_only),
        ("xicad_preview_live_lxp", preview_live_lxp, read_only),
        ("xicad_execute_live_lxp", execute_live_lxp, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
