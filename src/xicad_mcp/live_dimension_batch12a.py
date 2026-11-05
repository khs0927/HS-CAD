from __future__ import annotations

import hashlib
import json
from math import pi
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch11 import DimensionSnapshot
from .headless_core_batch12 import (
    DimensionChainMode,
    DimensionScaleRequest,
    DimensionScaleScope,
    DimensionStyleEditRequest,
    DimensionStyleMergeRequest,
    DimensionStyleSnapshot,
    DimensionTextMoveDirection,
    DimensionTextMoveRequest,
    LinearOrientation,
    PolylineDimensionRequest,
    PolylineDimensionSnapshot,
    PolylineVertexPolicy,
    QuickDimensionRequest,
    QuickDimensionSource,
    TextCollisionGroup,
    plan_dimension_scale,
    plan_dimension_style_merge,
    plan_dimension_text_move,
    plan_polyline_dimensions,
    plan_quick_dimensions,
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


class LiveDplPreviewRequest(_Request):
    source_handle: str = Field(min_length=1)
    vertex_policy: PolylineVertexPolicy
    explicit_pairs: tuple[tuple[int, int], ...] = ()
    orientation: LinearOrientation
    dimension_line_point: Point3D
    style: str = Field(min_length=1)
    include_closing_segment: bool = False


class LiveDplExecuteRequest(LiveDplPreviewRequest):
    expected_source: PolylineDimensionSnapshot
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveDqPreviewRequest(_Request):
    source_handles: tuple[str, ...] = Field(min_length=1)
    chain_mode: DimensionChainMode
    orientation: LinearOrientation
    dimension_line_point: Point3D
    style: str = Field(min_length=1)
    deduplicate_points: bool = True


class LiveDqExecuteRequest(LiveDqPreviewRequest):
    expected_sources: tuple[QuickDimensionSource, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveDscPreviewRequest(_Request):
    scope: DimensionScaleScope
    scale: float = Field(gt=0)
    target_handles: tuple[str, ...] = ()
    current_style: str | None = None


class LiveDscExecuteRequest(LiveDscPreviewRequest):
    expected_style: str
    expected_scale: float = Field(ge=0)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveDsePreviewRequest(_Request):
    request: DimensionStyleEditRequest


class LiveStyleState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    is_xref: bool = False
    is_current: bool = False


class LiveDimensionAssignmentState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    handle: str
    style: str
    layer: str
    locked_layer: bool
    is_xref: bool
    nested: bool


class LiveDsmPreviewRequest(_Request):
    source_styles: tuple[str, ...] = Field(min_length=1)
    target_style: str = Field(min_length=1)
    include_nested: bool = False
    remove_source_styles: bool = False


class LiveDsmExecuteRequest(LiveDsmPreviewRequest):
    expected_styles: tuple[LiveStyleState, ...]
    expected_dimensions: tuple[LiveDimensionAssignmentState, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveDtmPreviewRequest(_Request):
    collision_groups: tuple[TextCollisionGroup, ...] = Field(min_length=1)
    direction: DimensionTextMoveDirection
    offset_factor: float = Field(gt=0)
    unit_direction: Point3D


class LiveDtmExecuteRequest(LiveDtmPreviewRequest):
    expected_dimensions: tuple[DimensionSnapshot, ...] = Field(min_length=2)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveDimension12aResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...] = ()
    created_handles: tuple[str, ...] = ()
    removed_styles: tuple[str, ...] = ()
    postcondition_verified: bool


class ZWCADLiveDimension12aAdapter(ZWCADLiveBatch11aAdapter):
    def _polyline_points(self, entity: Any) -> tuple[Point3D, ...]:
        name = str(entity.ObjectName).casefold()
        if name != "acdbpolyline":
            raise ValueError(f"DPL/DQ supports lightweight 2D polylines only: {entity.Handle}")
        values = tuple(float(value) for value in entity.Coordinates)
        if len(values) < 4 or len(values) % 2:
            raise RuntimeError(f"invalid polyline coordinates: {entity.Handle}")
        elevation = float(getattr(entity, "Elevation", 0.0))
        return tuple(Point3D(x=values[i], y=values[i + 1], z=elevation) for i in range(0, len(values), 2))

    def polyline(self, handle: str) -> PolylineDimensionSnapshot:
        entity = self.entity_objects().get(handle.casefold())
        if entity is None:
            raise ValueError(f"polyline not found: {handle}")
        layer = str(entity.Layer)
        return PolylineDimensionSnapshot(
            handle=str(entity.Handle),
            vertices=self._polyline_points(entity),
            closed=bool(entity.Closed),
            locked_layer=bool(self.connect().Layers.Item(layer).Lock),
            is_xref="|" in layer,
        )

    def quick_sources(self, handles: tuple[str, ...]) -> tuple[QuickDimensionSource, ...]:
        objects = self.entity_objects()
        result = []
        for handle in handles:
            entity = objects.get(handle.casefold())
            if entity is None:
                raise ValueError(f"DQ source not found: {handle}")
            name = str(entity.ObjectName).casefold()
            if name == "acdbline":
                points = (self._point(entity.StartPoint, "StartPoint"), self._point(entity.EndPoint, "EndPoint"))
            elif name == "acdbpolyline":
                points = self._polyline_points(entity)
            else:
                raise ValueError(f"DQ source type is unsupported: {handle} ({entity.ObjectName})")
            layer = str(entity.Layer)
            result.append(
                QuickDimensionSource(
                    handle=str(entity.Handle),
                    points=points,
                    locked_layer=bool(self.connect().Layers.Item(layer).Lock),
                    is_xref="|" in layer,
                )
            )
        return tuple(result)

    def styles(self) -> tuple[LiveStyleState, ...]:
        current = str(self.connect().ActiveDimStyle.Name).casefold()
        result = tuple(
            LiveStyleState(
                name=str(style.Name),
                is_xref="|" in str(style.Name),
                is_current=str(style.Name).casefold() == current,
            )
            for style in self.connect().DimStyles
        )
        return tuple(sorted(result, key=lambda item: item.name.casefold()))

    def assignment_dimensions(self) -> tuple[LiveDimensionAssignmentState, ...]:
        result = []
        doc = self.connect()
        for block in doc.Blocks:
            nested = not bool(block.IsLayout)
            for entity in block:
                if "dimension" not in str(entity.ObjectName).casefold():
                    continue
                layer = str(entity.Layer)
                result.append(
                    LiveDimensionAssignmentState(
                        handle=str(entity.Handle),
                        style=str(entity.StyleName),
                        layer=layer,
                        locked_layer=bool(doc.Layers.Item(layer).Lock),
                        is_xref="|" in layer or "|" in str(block.Name),
                        nested=nested,
                    )
                )
        return tuple(sorted(result, key=lambda item: item.handle.casefold()))


def _approval(execute: bool, fingerprint: str | None = None) -> Approval:
    return Approval(approved=execute, fingerprint=fingerprint)


def _same(actual: tuple[BaseModel, ...], expected: tuple[BaseModel, ...], alias: str) -> None:
    if _models(actual) != _models(expected):
        raise ValueError(f"{alias} snapshot no longer matches approval")


def _validate_style(adapter: ZWCADLiveDimension12aAdapter, style: str) -> None:
    try:
        adapter.connect().DimStyles.Item(style)
    except Exception as exc:
        raise ValueError(f"dimension style not found: {style}") from exc


def _create_dimension(adapter: ZWCADLiveDimension12aAdapter, spec: Any) -> Any:
    doc = adapter.connect()
    if spec.orientation is LinearOrientation.ALIGNED:
        entity = doc.ModelSpace.AddDimAligned(
            adapter.vector(spec.first_point),
            adapter.vector(spec.second_point),
            adapter.vector(spec.dimension_line_point),
        )
    else:
        angle = 0.0 if spec.orientation is LinearOrientation.HORIZONTAL else pi / 2
        entity = doc.ModelSpace.AddDimRotated(
            adapter.vector(spec.first_point),
            adapter.vector(spec.second_point),
            adapter.vector(spec.dimension_line_point),
            angle,
        )
    entity.StyleName = spec.style
    return entity


def _verify_created(created: list[Any], creates: tuple[Any, ...]) -> bool:
    return all(
        str(entity.StyleName) == spec.style
        and (
            ("aligneddimension" in str(entity.ObjectName).casefold())
            if spec.orientation is LinearOrientation.ALIGNED
            else ("rotateddimension" in str(entity.ObjectName).casefold())
        )
        for entity, spec in zip(created, creates, strict=True)
    )


def _dpl_core(
    request: LiveDplPreviewRequest, execute: bool, fingerprint: str | None = None
) -> PolylineDimensionRequest:
    return PolylineDimensionRequest(
        document_id=request.document_name,
        source_handle=request.source_handle,
        vertex_policy=request.vertex_policy,
        explicit_pairs=request.explicit_pairs,
        orientation=request.orientation,
        dimension_line_point=request.dimension_line_point,
        style=request.style,
        include_closing_segment=request.include_closing_segment,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_dpl(request: LiveDplPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveDimension12aAdapter(request.document_name)
    _validate_style(adapter, request.style)
    source = adapter.polyline(request.source_handle)
    plan = plan_polyline_dimensions(_dpl_core(request, False), (source,))
    body = {**request.model_dump(mode="json"), "expected_source": source.model_dump(mode="json")}
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def execute_live_dpl(request: LiveDplExecuteRequest) -> LiveDimension12aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match DPL")
    adapter = ZWCADLiveDimension12aAdapter(request.document_name)
    source = adapter.polyline(request.source_handle)
    if source != request.expected_source:
        raise ValueError("DPL polyline changed after approval")
    plan = plan_polyline_dimensions(_dpl_core(request, True, request.approval_fingerprint), (source,))
    doc = adapter.connect()
    created = []
    doc.StartUndoMark()
    try:
        created = [_create_dimension(adapter, spec) for spec in plan.creates]
    finally:
        doc.EndUndoMark()
    handles = tuple(str(x.Handle) for x in created)
    if not all(h.casefold() in adapter.entity_objects() for h in handles) or not _verify_created(created, plan.creates):
        raise RuntimeError("DPL postcondition failed")
    return LiveDimension12aResult(
        document_name=str(doc.Name), command_alias="DPL", created_handles=handles, postcondition_verified=True
    )


def _dq_core(request: LiveDqPreviewRequest, execute: bool, fingerprint: str | None = None) -> QuickDimensionRequest:
    return QuickDimensionRequest(
        document_id=request.document_name,
        source_handles=request.source_handles,
        chain_mode=request.chain_mode,
        orientation=request.orientation,
        dimension_line_point=request.dimension_line_point,
        style=request.style,
        deduplicate_points=request.deduplicate_points,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_dq(request: LiveDqPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveDimension12aAdapter(request.document_name)
    _validate_style(adapter, request.style)
    sources = adapter.quick_sources(request.source_handles)
    plan = plan_quick_dimensions(_dq_core(request, False), sources)
    body = {**request.model_dump(mode="json"), "expected_sources": _models(sources)}
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def execute_live_dq(request: LiveDqExecuteRequest) -> LiveDimension12aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match DQ")
    adapter = ZWCADLiveDimension12aAdapter(request.document_name)
    sources = adapter.quick_sources(request.source_handles)
    _same(sources, request.expected_sources, "DQ")
    plan = plan_quick_dimensions(_dq_core(request, True, request.approval_fingerprint), sources)
    doc = adapter.connect()
    created = []
    doc.StartUndoMark()
    try:
        created = [_create_dimension(adapter, spec) for spec in plan.creates]
    finally:
        doc.EndUndoMark()
    handles = tuple(str(x.Handle) for x in created)
    if not all(h.casefold() in adapter.entity_objects() for h in handles) or not _verify_created(created, plan.creates):
        raise RuntimeError("DQ postcondition failed")
    return LiveDimension12aResult(
        document_name=str(doc.Name), command_alias="DQ", created_handles=handles, postcondition_verified=True
    )


def preview_live_dsc(request: LiveDscPreviewRequest) -> dict[str, Any]:
    if request.scope is not DimensionScaleScope.CURRENT_STYLE:
        raise RuntimeError("DSC selected-dimension overall scale is not exposed reliably by ZWCAD ActiveX")
    adapter = ZWCADLiveDimension12aAdapter(request.document_name)
    doc = adapter.connect()
    style = str(doc.ActiveDimStyle.Name)
    if request.current_style is None or style.casefold() != request.current_style.casefold():
        raise ValueError("DSC current_style must match ActiveDimStyle")
    scale = float(doc.GetVariable("DIMSCALE"))
    core = DimensionScaleRequest(
        document_id=request.document_name,
        scope=request.scope,
        scale=request.scale,
        current_style=request.current_style,
        dry_run=True,
    )
    plan = plan_dimension_scale(core, ())
    body = {**request.model_dump(mode="json"), "expected_style": style, "expected_scale": scale}
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def execute_live_dsc(request: LiveDscExecuteRequest) -> LiveDimension12aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match DSC")
    adapter = ZWCADLiveDimension12aAdapter(request.document_name)
    doc = adapter.connect()
    if (
        str(doc.ActiveDimStyle.Name) != request.expected_style
        or abs(float(doc.GetVariable("DIMSCALE")) - request.expected_scale) > 1e-9
    ):
        raise ValueError("DSC style state changed")
    core = DimensionScaleRequest(
        document_id=request.document_name,
        scope=request.scope,
        scale=request.scale,
        current_style=request.current_style,
        dry_run=False,
        approval=_approval(True, request.approval_fingerprint),
    )
    plan = plan_dimension_scale(core, ())
    doc.StartUndoMark()
    try:
        doc.SetVariable("DIMSCALE", plan.style_scale_change[1])
    finally:
        doc.EndUndoMark()
    if abs(float(doc.GetVariable("DIMSCALE")) - request.scale) > 1e-9:
        raise RuntimeError("DSC postcondition failed")
    return LiveDimension12aResult(document_name=str(doc.Name), command_alias="DSC", postcondition_verified=True)


def preview_live_dse(request: LiveDsePreviewRequest) -> dict[str, Any]:
    raise RuntimeError("DSE is unavailable: ZWCAD ActiveX does not expose verifiable per-DimStyle property editing")


def execute_live_dse(_request: Any) -> LiveDimension12aResult:
    raise RuntimeError("DSE cannot execute without verifiable per-DimStyle property access")


def _planner_styles(states: tuple[LiveStyleState, ...]) -> tuple[DimensionStyleSnapshot, ...]:
    return tuple(
        DimensionStyleSnapshot(
            name=s.name,
            dimscale=1,
            text_style="Standard",
            text_height=1,
            arrow_size=1,
            extension_offset=0,
            baseline_spacing=1,
            decimal_places=0,
            is_xref=s.is_xref,
        )
        for s in states
    )


def _planner_dims(states: tuple[LiveDimensionAssignmentState, ...]) -> tuple[DimensionSnapshot, ...]:
    zero = Point3D(x=0, y=0, z=0)
    from .headless_core_batch11 import DimensionKind

    return tuple(
        DimensionSnapshot(
            handle=s.handle,
            kind=DimensionKind.ALIGNED,
            layer=s.layer,
            style=s.style,
            measurement=0,
            text_position=zero,
            default_text_position=zero,
            dimension_line_point=zero,
            first_extension_origin=zero,
            second_extension_origin=Point3D(x=1, y=0, z=0),
            first_extension_length=0,
            second_extension_length=0,
            dimscale=1,
            ltscale=1,
            object_scale=1,
            locked_layer=s.locked_layer,
            is_xref=s.is_xref,
        )
        for s in states
    )


def _dsm_core(
    request: LiveDsmPreviewRequest, execute: bool, fingerprint: str | None = None
) -> DimensionStyleMergeRequest:
    return DimensionStyleMergeRequest(
        document_id=request.document_name,
        source_styles=request.source_styles,
        target_style=request.target_style,
        include_nested=request.include_nested,
        remove_source_styles=request.remove_source_styles,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_dsm(request: LiveDsmPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveDimension12aAdapter(request.document_name)
    styles = adapter.styles()
    source_names = {name.casefold() for name in request.source_styles}
    if request.remove_source_styles and any(
        style.name.casefold() in source_names and (style.is_current or style.name.casefold() == "standard")
        for style in styles
    ):
        raise ValueError("DSM cannot remove the active or Standard dimension style")
    dims = adapter.assignment_dimensions()
    plan = plan_dimension_style_merge(
        _dsm_core(request, False),
        _planner_styles(styles),
        _planner_dims(dims),
        tuple(d.handle for d in dims if d.nested),
    )
    body = {**request.model_dump(mode="json"), "expected_styles": _models(styles), "expected_dimensions": _models(dims)}
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def execute_live_dsm(request: LiveDsmExecuteRequest) -> LiveDimension12aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match DSM")
    adapter = ZWCADLiveDimension12aAdapter(request.document_name)
    styles = adapter.styles()
    dims = adapter.assignment_dimensions()
    _same(styles, request.expected_styles, "DSM styles")
    _same(dims, request.expected_dimensions, "DSM dimensions")
    source_names = {name.casefold() for name in request.source_styles}
    if request.remove_source_styles and any(
        style.name.casefold() in source_names and (style.is_current or style.name.casefold() == "standard")
        for style in styles
    ):
        raise ValueError("DSM cannot remove the active or Standard dimension style")
    plan = plan_dimension_style_merge(
        _dsm_core(request, True, request.approval_fingerprint),
        _planner_styles(styles),
        _planner_dims(dims),
        tuple(d.handle for d in dims if d.nested),
    )
    objects = adapter.entity_objects()
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            objects[change.handle.casefold()].StyleName = change.replacement_style
        for name in plan.remove_styles:
            doc.DimStyles.Item(name).Delete()
    finally:
        doc.EndUndoMark()
    after_styles = {s.name.casefold() for s in adapter.styles()}
    if not all(str(objects[c.handle.casefold()].StyleName) == c.replacement_style for c in plan.changes) or any(
        n.casefold() in after_styles for n in plan.remove_styles
    ):
        raise RuntimeError("DSM postcondition failed")
    return LiveDimension12aResult(
        document_name=str(doc.Name),
        command_alias="DSM",
        changed_handles=tuple(c.handle for c in plan.changes),
        removed_styles=plan.remove_styles,
        postcondition_verified=True,
    )


def register_live_dimension_batch12a_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(title="Preview live xiCAD Batch 12A dimension operation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    execute = ToolAnnotations(title="Execute live xiCAD Batch 12A dimension operation", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
    registrations = (
        ("xicad_preview_live_dpl", preview_live_dpl, preview), ("xicad_execute_live_dpl", execute_live_dpl, execute),
        ("xicad_preview_live_dq", preview_live_dq, preview), ("xicad_execute_live_dq", execute_live_dq, execute),
        ("xicad_preview_live_dsc", preview_live_dsc, preview), ("xicad_execute_live_dsc", execute_live_dsc, execute),
        ("xicad_preview_live_dse", preview_live_dse, preview),
        ("xicad_preview_live_dsm", preview_live_dsm, preview), ("xicad_execute_live_dsm", execute_live_dsm, execute),
        ("xicad_preview_live_dtm", preview_live_dtm, preview), ("xicad_execute_live_dtm", execute_live_dtm, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)


def _dtm_core(
    request: LiveDtmPreviewRequest, execute: bool, fingerprint: str | None = None
) -> DimensionTextMoveRequest:
    return DimensionTextMoveRequest(
        document_id=request.document_name,
        collision_groups=request.collision_groups,
        direction=request.direction,
        offset_factor=request.offset_factor,
        unit_direction=request.unit_direction,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def _dtm_handles(request: LiveDtmPreviewRequest) -> tuple[str, ...]:
    return tuple(handle for group in request.collision_groups for handle in group.handles)


def preview_live_dtm(request: LiveDtmPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveDimension12aAdapter(request.document_name)
    dims = adapter.dimensions(_dtm_handles(request))
    plan = plan_dimension_text_move(_dtm_core(request, False), dims)
    body = {**request.model_dump(mode="json"), "expected_dimensions": _models(dims)}
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def execute_live_dtm(request: LiveDtmExecuteRequest) -> LiveDimension12aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match DTM")
    adapter = ZWCADLiveDimension12aAdapter(request.document_name)
    dims = adapter.dimensions(_dtm_handles(request))
    _same(dims, request.expected_dimensions, "DTM")
    plan = plan_dimension_text_move(_dtm_core(request, True, request.approval_fingerprint), dims)
    objects = adapter.entity_objects()
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            objects[change.handle.casefold()].TextPosition = adapter.vector(change.replacement_position)
    finally:
        doc.EndUndoMark()
    after = adapter.dimensions(_dtm_handles(request))
    by_handle = {d.handle.casefold(): d for d in after}
    if not all(by_handle[c.handle.casefold()].text_position == c.replacement_position for c in plan.changes):
        raise RuntimeError("DTM postcondition failed")
    return LiveDimension12aResult(
        document_name=str(doc.Name),
        command_alias="DTM",
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )
