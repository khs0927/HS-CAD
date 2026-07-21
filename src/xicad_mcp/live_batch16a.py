from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from math import cos, radians, sin
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch14 import GeometrySnapshot
from .headless_core_batch16 import (
    BlockPatternRequest,
    CalendarRequest,
    CenterPolylineRequest,
    ColumnKind,
    ColumnRequest,
    ConcreteShape,
    ScheduleRequest,
    plan_beam_schedule,
    plan_block_pattern,
    plan_calendar,
    plan_center_polyline,
    plan_column,
    plan_column_schedule,
)
from .live_batch14a import ZWCADLiveBatch14aAdapter


def _hash(payload: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class _Preview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)


class LiveSchedulePreviewRequest(_Preview):
    request: ScheduleRequest


class LiveScheduleExecuteRequest(LiveSchedulePreviewRequest):
    command_alias: str = Field(pattern=r"^(BLI|CLI)$")
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBptPreviewRequest(_Preview):
    request: BlockPatternRequest


class LiveBptExecuteRequest(LiveBptPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveCalendarPreviewRequest(_Preview):
    request: CalendarRequest


class LiveCalendarExecuteRequest(LiveCalendarPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveCepPreviewRequest(_Preview):
    request: CenterPolylineRequest


class LiveCepExecuteRequest(LiveCepPreviewRequest):
    expected_geometry: tuple[GeometrySnapshot, GeometrySnapshot]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveColPreviewRequest(_Preview):
    request: ColumnRequest


class LiveColExecuteRequest(LiveColPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch16aResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    created_handles: tuple[str, ...] = ()
    structured_output: dict[str, Any] | None = None
    postcondition_verified: bool


class ZWCADLiveBatch16aAdapter(ZWCADLiveBatch14aAdapter):
    def validate_text_style(self, name: str) -> None:
        try:
            self.connect().TextStyles.Item(name)
        except Exception as exc:
            raise ValueError(f"text style not found: {name}") from exc

    def text(self, value: str, point: Point3D, height: float, layer: str, style: str | None = None) -> Any:
        entity = self.connect().ModelSpace.AddText(value, self.vector(point), height)
        entity.Layer = layer
        if style is not None:
            entity.StyleName = style
        return entity

    def lwpolyline(self, vertices: tuple[Point3D, ...], layer: str, closed: bool = False) -> Any:
        if len({round(point.z, 9) for point in vertices}) != 1:
            raise RuntimeError("lightweight polyline output requires constant elevation")
        import pythoncom
        import win32com.client

        values = [value for point in vertices for value in (point.x, point.y)]
        variant = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)
        entity = self.connect().ModelSpace.AddLightWeightPolyline(variant)
        entity.Elevation = vertices[0].z
        entity.Closed = closed
        entity.Layer = layer
        return entity

    def circle(self, center: Point3D, radius: float, layer: str) -> Any:
        entity = self.connect().ModelSpace.AddCircle(self.vector(center), radius)
        entity.Layer = layer
        return entity


def _body(document_name: str, request: BaseModel, expected: tuple[GeometrySnapshot, ...] = ()) -> dict[str, Any]:
    result: dict[str, Any] = {"document_name": document_name, "request": request.model_dump(mode="json")}
    if expected:
        result["expected_geometry"] = [item.model_dump(mode="json") for item in expected]
    return result


def _check_document(document_name: str, request: Any) -> None:
    if request.document_id.casefold() != document_name.casefold():
        raise ValueError("request document_id must match document_name")


def _approved(request: BaseModel, fingerprint: str) -> BaseModel:
    return request.model_copy(update={"dry_run": False, "approval": Approval(approved=True, fingerprint=fingerprint)})


def _validate_fingerprint(request: BaseModel, fingerprint: str, *, exclude: set[str] | None = None) -> None:
    payload = request.model_dump(mode="json", exclude=exclude or {"approval_fingerprint"})
    if fingerprint != _hash(payload):
        raise ValueError("approval fingerprint mismatch")


def _preview(
    document_name: str, request: BaseModel, plan: BaseModel, expected: tuple[GeometrySnapshot, ...] = ()
) -> dict[str, Any]:
    body = _body(document_name, request, expected)
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def preview_live_schedule(request: LiveSchedulePreviewRequest, command_alias: str) -> dict[str, Any]:
    _check_document(request.document_name, request.request)
    if command_alias not in {"BLI", "CLI"}:
        raise ValueError("schedule alias must be BLI or CLI")
    adapter = ZWCADLiveBatch16aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.grid_layer)
    adapter.validate_output_layer(request.request.text_layer)
    plan = (plan_beam_schedule if command_alias == "BLI" else plan_column_schedule)(request.request)
    body = {**_body(request.document_name, request.request), "command_alias": command_alias}
    return {**body, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(body)}


def preview_live_bli(request: LiveSchedulePreviewRequest) -> dict[str, Any]:
    return preview_live_schedule(request, "BLI")


def preview_live_cli(request: LiveSchedulePreviewRequest) -> dict[str, Any]:
    return preview_live_schedule(request, "CLI")


def execute_live_schedule(request: LiveScheduleExecuteRequest) -> LiveBatch16aResult:
    _check_document(request.document_name, request.request)
    _validate_fingerprint(request, request.approval_fingerprint)
    adapter = ZWCADLiveBatch16aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.grid_layer)
    adapter.validate_output_layer(request.request.text_layer)
    planner = plan_beam_schedule if request.command_alias == "BLI" else plan_column_schedule
    plan = planner(_approved(request.request, request.approval_fingerprint))
    created = []
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for start, end in (*plan.horizontal_lines, *plan.vertical_lines):
            created.append(adapter.line(start, end, plan.grid_layer))
        x_offsets = [0.0]
        for width in request.request.column_widths:
            x_offsets.append(x_offsets[-1] + width)
        for cell in plan.cells:
            point = Point3D(
                x=request.request.insertion_point.x + (x_offsets[cell.column] + x_offsets[cell.column + 1]) / 2,
                y=request.request.insertion_point.y - (cell.row + 0.5) * request.request.row_height,
                z=request.request.insertion_point.z,
            )
            created.append(adapter.text(cell.text, point, plan.text_height, plan.text_layer))
    finally:
        doc.EndUndoMark()
    return _verify_created(adapter, request.command_alias, created)


def execute_live_bli(request: LiveScheduleExecuteRequest) -> LiveBatch16aResult:
    if request.command_alias != "BLI":
        raise ValueError("BLI executor requires command_alias BLI")
    return execute_live_schedule(request)


def execute_live_cli(request: LiveScheduleExecuteRequest) -> LiveBatch16aResult:
    if request.command_alias != "CLI":
        raise ValueError("CLI executor requires command_alias CLI")
    return execute_live_schedule(request)


def preview_live_bpt(request: LiveBptPreviewRequest) -> dict[str, Any]:
    _check_document(request.document_name, request.request)
    return _preview(request.document_name, request.request, plan_block_pattern(request.request))


def execute_live_bpt(request: LiveBptExecuteRequest) -> LiveBatch16aResult:
    _check_document(request.document_name, request.request)
    _validate_fingerprint(request, request.approval_fingerprint)
    plan = plan_block_pattern(_approved(request.request, request.approval_fingerprint))
    return LiveBatch16aResult(
        document_name=request.document_name,
        command_alias="BPT",
        structured_output=plan.model_dump(mode="json"),
        postcondition_verified=True,
    )


def preview_live_calendar(request: LiveCalendarPreviewRequest) -> dict[str, Any]:
    _check_document(request.document_name, request.request)
    adapter = ZWCADLiveBatch16aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.layer)
    adapter.validate_text_style(request.request.text_style)
    return _preview(request.document_name, request.request, plan_calendar(request.request))


def execute_live_calendar(request: LiveCalendarExecuteRequest) -> LiveBatch16aResult:
    _check_document(request.document_name, request.request)
    _validate_fingerprint(request, request.approval_fingerprint)
    adapter = ZWCADLiveBatch16aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.layer)
    adapter.validate_text_style(request.request.text_style)
    plan = plan_calendar(_approved(request.request, request.approval_fingerprint))
    p, w, h = plan.insertion_point, plan.cell_width, plan.cell_height
    rows = len(plan.weeks)
    created = []
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for row in range(rows + 1):
            created.append(
                adapter.line(
                    Point3D(x=p.x, y=p.y - row * h, z=p.z), Point3D(x=p.x + 7 * w, y=p.y - row * h, z=p.z), plan.layer
                )
            )
        for column in range(8):
            created.append(
                adapter.line(
                    Point3D(x=p.x + column * w, y=p.y, z=p.z),
                    Point3D(x=p.x + column * w, y=p.y - rows * h, z=p.z),
                    plan.layer,
                )
            )
        created.append(adapter.text(plan.title, Point3D(x=p.x, y=p.y + h, z=p.z), h * 0.5, plan.layer, plan.text_style))
        for row, week in enumerate(plan.weeks):
            for column, day in enumerate(week):
                if day:
                    created.append(
                        adapter.text(
                            str(day),
                            Point3D(x=p.x + (column + 0.1) * w, y=p.y - (row + 0.7) * h, z=p.z),
                            h * 0.35,
                            plan.layer,
                            plan.text_style,
                        )
                    )
    finally:
        doc.EndUndoMark()
    return _verify_created(adapter, "CALENDAR", created)


def preview_live_cep(request: LiveCepPreviewRequest) -> dict[str, Any]:
    _check_document(request.document_name, request.request)
    adapter = ZWCADLiveBatch16aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.layer)
    states = adapter.geometry((request.request.first_handle, request.request.second_handle))
    plan = plan_center_polyline(request.request, states)
    for line in plan.output_lines:
        if len({round(point.z, 9) for point in line}) != 1:
            raise RuntimeError("CEP output cannot be represented as a lightweight polyline")
    return _preview(request.document_name, request.request, plan, states)


def execute_live_cep(request: LiveCepExecuteRequest) -> LiveBatch16aResult:
    _check_document(request.document_name, request.request)
    _validate_fingerprint(request, request.approval_fingerprint)
    adapter = ZWCADLiveBatch16aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.layer)
    current = adapter.geometry((request.request.first_handle, request.request.second_handle))
    if current != request.expected_geometry:
        raise ValueError("CEP geometry changed after approval")
    plan = plan_center_polyline(_approved(request.request, request.approval_fingerprint), current)
    created = _under_undo(adapter, lambda: [adapter.lwpolyline(line, plan.layer) for line in plan.output_lines])
    return _verify_created(adapter, "CEP", created)


def preview_live_col(request: LiveColPreviewRequest) -> dict[str, Any]:
    _check_document(request.document_name, request.request)
    adapter = ZWCADLiveBatch16aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.concrete_layer)
    if request.request.kind in {ColumnKind.SC, ColumnKind.SRC}:
        adapter.validate_output_layer(request.request.steel_layer)
    return _preview(request.document_name, request.request, plan_column(request.request))


def execute_live_col(request: LiveColExecuteRequest) -> LiveBatch16aResult:
    _check_document(request.document_name, request.request)
    _validate_fingerprint(request, request.approval_fingerprint)
    adapter = ZWCADLiveBatch16aAdapter(request.document_name)
    adapter.validate_output_layer(request.request.concrete_layer)
    if request.request.kind in {ColumnKind.SC, ColumnKind.SRC}:
        adapter.validate_output_layer(request.request.steel_layer)
    plan = plan_column(_approved(request.request, request.approval_fingerprint))

    def create() -> list[Any]:
        result = []
        for spec in plan.creates:
            if spec.kind is not ColumnKind.SC:
                if spec.concrete_shape is ConcreteShape.CIRCLE:
                    result.append(adapter.circle(spec.center, spec.concrete_width / 2, spec.concrete_layer))
                else:
                    result.append(
                        adapter.lwpolyline(
                            _rectangle(spec.center, spec.concrete_width, spec.concrete_depth), spec.concrete_layer, True
                        )
                    )
            if spec.steel_dimensions is not None:
                result.append(
                    adapter.lwpolyline(
                        _steel_outline(spec.center, *spec.steel_dimensions, spec.steel_rotation_degrees),
                        spec.steel_layer,
                        True,
                    )
                )
        return result

    return _verify_created(adapter, "COL", _under_undo(adapter, create))


def _rectangle(center: Point3D, width: float, depth: float) -> tuple[Point3D, ...]:
    return tuple(
        Point3D(x=center.x + x, y=center.y + y, z=center.z)
        for x, y in ((-width / 2, -depth / 2), (width / 2, -depth / 2), (width / 2, depth / 2), (-width / 2, depth / 2))
    )


def _steel_outline(
    center: Point3D, width: float, depth: float, web: float, flange: float, rotation: float
) -> tuple[Point3D, ...]:
    points = (
        (-width / 2, -depth / 2),
        (width / 2, -depth / 2),
        (width / 2, -depth / 2 + flange),
        (web / 2, -depth / 2 + flange),
        (web / 2, depth / 2 - flange),
        (width / 2, depth / 2 - flange),
        (width / 2, depth / 2),
        (-width / 2, depth / 2),
        (-width / 2, depth / 2 - flange),
        (-web / 2, depth / 2 - flange),
        (-web / 2, -depth / 2 + flange),
        (-width / 2, -depth / 2 + flange),
    )
    angle = radians(rotation)
    return tuple(
        Point3D(x=center.x + x * cos(angle) - y * sin(angle), y=center.y + x * sin(angle) + y * cos(angle), z=center.z)
        for x, y in points
    )


def _under_undo(adapter: ZWCADLiveBatch16aAdapter, operation: Callable[[], list[Any]]) -> list[Any]:
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        return operation()
    finally:
        doc.EndUndoMark()


def _verify_created(adapter: ZWCADLiveBatch16aAdapter, alias: str, created: list[Any]) -> LiveBatch16aResult:
    handles = tuple(str(entity.Handle) for entity in created)
    after = adapter.entity_objects()
    if not handles or not all(handle.casefold() in after for handle in handles):
        raise RuntimeError(f"{alias} postcondition failed")
    return LiveBatch16aResult(
        document_name=str(adapter.connect().Name),
        command_alias=alias,
        created_handles=handles,
        postcondition_verified=True,
    )


def register_live_batch16a_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 16A operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 16A operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_bli", preview_live_bli, preview),
        ("xicad_execute_live_bli", execute_live_bli, execute),
        ("xicad_preview_live_cli", preview_live_cli, preview),
        ("xicad_execute_live_cli", execute_live_cli, execute),
        ("xicad_preview_live_bpt", preview_live_bpt, preview),
        ("xicad_execute_live_bpt", execute_live_bpt, preview),
        ("xicad_preview_live_calendar", preview_live_calendar, preview),
        ("xicad_execute_live_calendar", execute_live_calendar, execute),
        ("xicad_preview_live_cep", preview_live_cep, preview),
        ("xicad_execute_live_cep", execute_live_cep, execute),
        ("xicad_preview_live_col", preview_live_col, preview),
        ("xicad_execute_live_col", execute_live_col, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
