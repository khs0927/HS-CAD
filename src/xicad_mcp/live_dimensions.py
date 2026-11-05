from __future__ import annotations

import hashlib
import json
from math import hypot, radians
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch2 import (
    DetachedTextSpec,
    DimensionOverrideDetachItem,
    DimensionOverrideDetachRequest,
    DimensionTextSnapshot,
    DivideDimensionRequest,
    JoinDimensionRequest,
    LinearDimensionSnapshot,
    LinearDimensionSpec,
    SourcePolicy,
    plan_dimension_override_detach,
    plan_divide_dimension,
    plan_join_dimensions,
)


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


class _LiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)


class LiveDtdPreviewRequest(_LiveRequest):
    items: tuple[DimensionOverrideDetachItem, ...] = Field(min_length=1)


class LiveDtdExecuteRequest(LiveDtdPreviewRequest):
    expected_dimensions: tuple[DimensionTextSnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveDividePreviewRequest(_LiveRequest):
    source_handle: str = Field(min_length=1)
    divisions: int = Field(ge=2, le=1000)
    source_policy: SourcePolicy
    allow_source_text_override: bool = False


class LiveDivideExecuteRequest(LiveDividePreviewRequest):
    expected_source: LinearDimensionSnapshot
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveJoinPreviewRequest(_LiveRequest):
    source_handles: tuple[str, ...] = Field(min_length=2)
    source_policy: SourcePolicy
    tolerance: float = Field(default=1e-6, gt=0, le=1.0)
    allow_gaps: bool = False


class LiveJoinExecuteRequest(LiveJoinPreviewRequest):
    expected_sources: tuple[LinearDimensionSnapshot, ...] = Field(min_length=2)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveDimensionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    changed_handles: tuple[str, ...]
    erased_handles: tuple[str, ...]
    postcondition_verified: bool


def _point(value: Any, *, property_name: str) -> Point3D:
    try:
        coordinates = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"ZWCAD returned invalid {property_name}") from exc
    if len(coordinates) != 3:
        raise RuntimeError(f"ZWCAD returned invalid {property_name}")
    return Point3D(x=coordinates[0], y=coordinates[1], z=coordinates[2])


class ZWCADLiveDimensionAdapter:
    """Small lazy COM boundary for the three deterministic dimension contracts."""

    def __init__(self, document_name: str) -> None:
        self.document_name = document_name
        self.app: Any | None = None
        self.doc: Any | None = None

    def connect(self) -> Any:
        if self.doc is not None:
            return self.doc
        import win32com.client

        self.app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
        matches = [doc for doc in self.app.Documents if str(doc.Name).casefold() == self.document_name.casefold()]
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one open document named {self.document_name!r}, found {len(matches)}")
        self.doc = matches[0]
        self.doc.Activate()
        return self.doc

    def objects(self) -> dict[str, Any]:
        doc = self.connect()
        return {str(entity.Handle).casefold(): entity for entity in doc.ModelSpace}

    def entity(self, handle: str) -> Any:
        entity = self.objects().get(handle.casefold())
        if entity is None:
            raise ValueError(f"entity handle not found: {handle}")
        return entity

    def read_dtd(self, handles: tuple[str, ...]) -> tuple[DimensionTextSnapshot, ...]:
        doc = self.connect()
        snapshots: list[DimensionTextSnapshot] = []
        for handle in handles:
            entity = self.entity(handle)
            if "dimension" not in str(entity.ObjectName).casefold():
                raise ValueError(f"DTD requires a dimension entity: {handle}")
            try:
                override = str(entity.TextOverride)
            except Exception as exc:
                raise RuntimeError(f"ZWCAD dimension does not expose TextOverride: {handle}") from exc
            snapshots.append(
                DimensionTextSnapshot(
                    handle=str(entity.Handle),
                    current_override=override,
                    layer=str(entity.Layer),
                    text_style=str(doc.ActiveTextStyle.Name),
                    text_height=float(doc.GetVariable("DIMTXT")),
                )
            )
        return tuple(snapshots)

    def read_linear(self, handle: str) -> LinearDimensionSnapshot:
        entity = self.entity(handle)
        object_name = str(entity.ObjectName).casefold()
        if "aligneddimension" not in object_name:
            raise ValueError(
                f"DVD/JD live execution currently supports aligned dimensions only: {handle} ({entity.ObjectName})"
            )
        try:
            return LinearDimensionSnapshot(
                handle=str(entity.Handle),
                extension_start=_point(entity.ExtLine1Point, property_name="ExtLine1Point"),
                extension_end=_point(entity.ExtLine2Point, property_name="ExtLine2Point"),
                # ActiveX exposes the third AddDimAligned point as TextPosition.
                dimension_line_point=_point(entity.TextPosition, property_name="TextPosition"),
                style_name=str(entity.StyleName),
                layer=str(entity.Layer),
                text_override=str(entity.TextOverride),
            )
        except Exception as exc:
            raise RuntimeError(f"ZWCAD aligned dimension is missing a required geometry property: {handle}") from exc

    def vector(self, point: Point3D) -> Any:
        import pythoncom
        import win32com.client

        return win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8,
            [point.x, point.y, point.z],
        )

    def create_dimension(self, spec: LinearDimensionSpec) -> Any:
        doc = self.connect()
        try:
            entity = doc.ModelSpace.AddDimAligned(
                self.vector(spec.extension_start),
                self.vector(spec.extension_end),
                self.vector(spec.dimension_line_point),
            )
            entity.StyleName = spec.style_name
            entity.Layer = spec.layer
            entity.TextOverride = spec.text_override
        except Exception as exc:
            raise RuntimeError("ZWCAD AddDimAligned live adapter failed") from exc
        return entity

    def create_text(self, spec: DetachedTextSpec) -> Any:
        doc = self.connect()
        try:
            entity = doc.ModelSpace.AddText(
                spec.text,
                self.vector(spec.insertion_point),
                spec.text_height,
            )
            entity.Layer = spec.layer
            entity.StyleName = spec.text_style
            entity.Rotation = radians(spec.rotation_degrees)
        except Exception as exc:
            raise RuntimeError("ZWCAD AddText live adapter failed") from exc
        return entity


def _same_snapshots(actual: tuple[BaseModel, ...], expected: tuple[BaseModel, ...]) -> bool:
    return [item.model_dump(mode="json") for item in actual] == [item.model_dump(mode="json") for item in expected]


def _point_matches(actual: Point3D, expected: Point3D) -> bool:
    return all(
        abs(a - b) <= 1e-9 for a, b in zip(actual.model_dump().values(), expected.model_dump().values(), strict=True)
    )


def _dimension_matches(actual: LinearDimensionSnapshot, expected: LinearDimensionSpec) -> bool:
    expected_offset = _line_offset(expected.extension_start, expected.extension_end, expected.dimension_line_point)
    actual_offset = _line_offset(actual.extension_start, actual.extension_end, actual.dimension_line_point)
    baseline = hypot(
        expected.extension_end.x - expected.extension_start.x,
        expected.extension_end.y - expected.extension_start.y,
    )
    return (
        _point_matches(actual.extension_start, expected.extension_start)
        and _point_matches(actual.extension_end, expected.extension_end)
        # ZWCAD exposes TextPosition, not the AddDimAligned dimension-line point,
        # and automatically nudges it by a few drawing units for text layout.
        and abs(actual_offset - expected_offset) <= max(5.0, baseline * 0.01)
        and actual.style_name == expected.style_name
        and actual.layer == expected.layer
        and actual.text_override == expected.text_override
    )


def _line_offset(start: Point3D, end: Point3D, point: Point3D) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    length = hypot(dx, dy)
    if length <= 1e-9:
        return 0.0
    return abs((point.x - start.x) * (-dy / length) + (point.y - start.y) * (dx / length))


def _text_matches(entity: Any, expected: DetachedTextSpec) -> bool:
    try:
        insertion = _point(entity.InsertionPoint, property_name="InsertionPoint")
        return (
            str(entity.TextString) == expected.text
            and str(entity.Layer) == expected.layer
            and str(entity.StyleName) == expected.text_style
            and abs(float(entity.Height) - expected.text_height) <= 1e-9
            and abs(float(entity.Rotation) - radians(expected.rotation_degrees)) <= 1e-9
            and _point_matches(insertion, expected.insertion_point)
        )
    except Exception:
        return False


def preview_live_dtd(request: LiveDtdPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveDimensionAdapter(request.document_name)
    snapshots = adapter.read_dtd(tuple(item.dimension_handle for item in request.items))
    plan = plan_dimension_override_detach(
        request=DimensionOverrideDetachRequest(
            document_id=request.document_name,
            items=request.items,
            dry_run=True,
        ),
        dimensions=snapshots,
    )
    payload = {**request.model_dump(mode="json"), "expected_dimensions": [s.model_dump(mode="json") for s in snapshots]}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_dtd(request: LiveDtdExecuteRequest) -> LiveDimensionResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact DTD request")
    adapter = ZWCADLiveDimensionAdapter(request.document_name)
    handles = tuple(item.dimension_handle for item in request.items)
    actual = adapter.read_dtd(handles)
    if not _same_snapshots(actual, request.expected_dimensions):
        raise ValueError("DTD dimension precondition no longer matches the approved snapshots")
    plan = plan_dimension_override_detach(
        DimensionOverrideDetachRequest(
            document_id=request.document_name,
            items=request.items,
            dry_run=False,
            approval=Approval(approved=True, fingerprint=request.approval_fingerprint),
        ),
        actual,
    )
    doc = adapter.connect()
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        for operation in plan.operations:
            dimension = adapter.entity(operation.dimension_handle)
            dimension.TextOverride = operation.replacement_override
            created.append(adapter.create_text(operation.detached_text))
    finally:
        doc.EndUndoMark()
    after = adapter.objects()
    created_handles = tuple(str(entity.Handle) for entity in created)
    changed = tuple(operation.dimension_handle for operation in plan.operations)
    verified = (
        all(handle.casefold() in after for handle in created_handles)
        and all(
            str(after[operation.dimension_handle.casefold()].TextOverride) == operation.replacement_override
            for operation in plan.operations
        )
        and all(
            _text_matches(after[handle.casefold()], operation.detached_text)
            for handle, operation in zip(created_handles, plan.operations, strict=True)
        )
    )
    if not verified:
        raise RuntimeError("DTD postcondition failed")
    return LiveDimensionResult(
        document_name=str(doc.Name),
        command_alias="DTD",
        created_handles=created_handles,
        changed_handles=changed,
        erased_handles=(),
        postcondition_verified=True,
    )


def preview_live_dvd(request: LiveDividePreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveDimensionAdapter(request.document_name)
    source = adapter.read_linear(request.source_handle)
    core_request = DivideDimensionRequest(
        document_id=request.document_name,
        source_handle=request.source_handle,
        divisions=request.divisions,
        source_policy=request.source_policy,
        allow_source_text_override=request.allow_source_text_override,
        dry_run=True,
    )
    plan = plan_divide_dimension(core_request, source)
    payload = {**request.model_dump(mode="json"), "expected_source": source.model_dump(mode="json")}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_dvd(request: LiveDivideExecuteRequest) -> LiveDimensionResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact DVD request")
    adapter = ZWCADLiveDimensionAdapter(request.document_name)
    actual = adapter.read_linear(request.source_handle)
    if not _same_snapshots((actual,), (request.expected_source,)):
        raise ValueError("DVD source precondition no longer matches the approved snapshot")
    core_request = DivideDimensionRequest(
        document_id=request.document_name,
        source_handle=request.source_handle,
        divisions=request.divisions,
        source_policy=request.source_policy,
        allow_source_text_override=request.allow_source_text_override,
        dry_run=False,
        approval=Approval(approved=True, fingerprint=request.approval_fingerprint),
    )
    plan = plan_divide_dimension(core_request, actual)
    doc = adapter.connect()
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        created = [adapter.create_dimension(spec) for spec in plan.output_dimensions]
        if request.source_policy is SourcePolicy.REPLACE:
            adapter.entity(plan.source_handle).Delete()
    finally:
        doc.EndUndoMark()
    after = adapter.objects()
    created_handles = tuple(str(entity.Handle) for entity in created)
    erased = (plan.source_handle,) if request.source_policy is SourcePolicy.REPLACE else ()
    verified = (
        all(handle.casefold() in after for handle in created_handles)
        and all(handle.casefold() not in after for handle in erased)
        and all(
            _dimension_matches(adapter.read_linear(handle), spec)
            for handle, spec in zip(created_handles, plan.output_dimensions, strict=True)
        )
    )
    if not verified:
        raise RuntimeError("DVD postcondition failed")
    return LiveDimensionResult(
        document_name=str(doc.Name),
        command_alias="DVD",
        created_handles=created_handles,
        changed_handles=(),
        erased_handles=erased,
        postcondition_verified=True,
    )


def preview_live_jd(request: LiveJoinPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveDimensionAdapter(request.document_name)
    sources = tuple(adapter.read_linear(handle) for handle in request.source_handles)
    core_request = JoinDimensionRequest(
        document_id=request.document_name,
        source_handles=request.source_handles,
        source_policy=request.source_policy,
        tolerance=request.tolerance,
        allow_gaps=request.allow_gaps,
        dry_run=True,
    )
    plan = plan_join_dimensions(core_request, sources)
    payload = {**request.model_dump(mode="json"), "expected_sources": [s.model_dump(mode="json") for s in sources]}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_jd(request: LiveJoinExecuteRequest) -> LiveDimensionResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact JD request")
    adapter = ZWCADLiveDimensionAdapter(request.document_name)
    actual = tuple(adapter.read_linear(handle) for handle in request.source_handles)
    if not _same_snapshots(actual, request.expected_sources):
        raise ValueError("JD source preconditions no longer match the approved snapshots")
    core_request = JoinDimensionRequest(
        document_id=request.document_name,
        source_handles=request.source_handles,
        source_policy=request.source_policy,
        tolerance=request.tolerance,
        allow_gaps=request.allow_gaps,
        dry_run=False,
        approval=Approval(approved=True, fingerprint=request.approval_fingerprint),
    )
    plan = plan_join_dimensions(core_request, actual)
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        created = adapter.create_dimension(plan.output_dimension)
        if request.source_policy is SourcePolicy.REPLACE:
            for handle in plan.source_handles:
                adapter.entity(handle).Delete()
    finally:
        doc.EndUndoMark()
    after = adapter.objects()
    created_handle = str(created.Handle)
    erased = plan.source_handles if request.source_policy is SourcePolicy.REPLACE else ()
    verified = (
        created_handle.casefold() in after
        and all(handle.casefold() not in after for handle in erased)
        and _dimension_matches(adapter.read_linear(created_handle), plan.output_dimension)
    )
    if not verified:
        raise RuntimeError("JD postcondition failed")
    return LiveDimensionResult(
        document_name=str(doc.Name),
        command_alias="JD",
        created_handles=(created_handle,),
        changed_handles=(),
        erased_handles=erased,
        postcondition_verified=True,
    )


def register_live_dimension_tools(mcp: FastMCP) -> None:
    preview_annotations = ToolAnnotations(
        title="Preview live xiCAD dimension mutation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute_annotations = ToolAnnotations(
        title="Execute live xiCAD dimension mutation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_dtd", preview_live_dtd, "Validate a DTD dimension-text detach plan."),
        ("xicad_execute_live_dtd", execute_live_dtd, "Execute an approved DTD dimension-text detach plan."),
        ("xicad_preview_live_dvd", preview_live_dvd, "Validate a DVD aligned-dimension division plan."),
        ("xicad_execute_live_dvd", execute_live_dvd, "Execute an approved DVD aligned-dimension division plan."),
        ("xicad_preview_live_jd", preview_live_jd, "Validate a JD aligned-dimension join plan."),
        ("xicad_execute_live_jd", execute_live_jd, "Execute an approved JD aligned-dimension join plan."),
    )
    for name, function, description in registrations:
        annotations = execute_annotations if "execute" in name else preview_annotations
        mcp.tool(name=name, description=description, annotations=annotations)(function)
